import uuid
from telegram import (
    Update, InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes
from database import search_raw, hydrate_results
from services.quran_api import get_ayah
from handlers.nahj import NAHJ_MENU_LABELS, NAHJ_ITEM_LABELS

MAFATIH_CATEGORY_FA = {
    "daily": "🕋 اعمال روزانه",
    "ziyarat": "🕌 زیارت",
    "weekly": "📅 اعمال هفتگی",
    "monthly": "🌙 اعمال ماهانه",
    "munajat": "💬 مناجات",
    "special": "✨ مناسبت خاص",
}

# تلگرام حداکثر ۵۰ نتیجه در هر پاسخ اینلاین قبول می‌کند؛ برای دیدن نتایج بعدی
# کاربر باید در لیست نتایج اسکرول کند تا batch بعدی خودکار لود شود (offset‌محور)
PAGE_SIZE = 50
# سقف کل نتایجی که برای یک عبارت واکشی می‌کنیم. چون کل محتوای فعلی دیتابیس
# (حدیث+نهج+مفاتیح) در حد چند صد ردیف است، این سقف عملاً یعنی «همه‌ی نتایج»؛
# فقط به‌عنوان یک سقف ایمنی برای واژه‌های بی‌نهایت پرتکرار نگه داشته شده.
MAX_RESULTS = 500

# پیام‌های تلگرام حداکثر ۴۰۹۶ کاراکتر می‌پذیرند. برای حدیث (که معمولاً کوتاه
# است) اگر رد شد، متن را می‌بریم و دکمه‌ی «مشاهده کامل» می‌گذاریم.
HADITH_CONTENT_LIMIT = 3800
# برای نهج‌البلاغه/مفاتیح (که اغلب طولانی‌اند و در بات صفحه‌بندی دارند) به‌جای
# دامپ متن کامل در پیام اینلاین، فقط یک پیش‌نمایش کوتاه می‌فرستیم و همیشه دکمه‌ی
# «مشاهده کامل» را می‌گذاریم که کاربر را به نسخه‌ی صفحه‌بندی‌شده‌ی خود ربات می‌برد
PREVIEW_LENGTH = 500


def _snippet(text: str, length: int = 100) -> str:
    if not text:
        return ""
    text = text.strip()
    return text if len(text) <= length else text[:length].rstrip() + "…"


def _build_result(item: dict):
    """یک آیتم استانداردشده (خروجی search_all) را به نتیجه‌ی اینلاین تلگرام تبدیل می‌کند."""
    reply_markup = None

    if item["type"] == "hadith":
        row = item["row"]
        title = f"📿 حدیث — {row['narrator'] or 'معصومین'}"
        description = _snippet(row["translation_text"])
        content = f"{row['arabic_text']}\n\n🔹 ترجمه:\n{row['translation_text']}"
        if row["source_book"]:
            content += f"\n\n📚 منبع: {row['source_book']}"
        if len(content) > HADITH_CONTENT_LIMIT:
            content = content[:HADITH_CONTENT_LIMIT].rstrip() + "…"
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("📖 مشاهده کامل", callback_data=f"hadithview_{row['id']}")]]
            )

    elif item["type"] == "nahj":
        row = item["row"]
        category = row["category"]
        item_label = NAHJ_ITEM_LABELS.get(category, "")
        cat_label = NAHJ_MENU_LABELS.get(category, "🕌 نهج‌البلاغه")
        title_suffix = f" — {row['title']}" if row["title"] else ""
        title = f"{cat_label} — {item_label} {row['number']}{title_suffix}"
        description = _snippet(row["translation_text"])
        content = _snippet(row["translation_text"], PREVIEW_LENGTH)
        content += "\n\n📖 برای مشاهده‌ی متن کامل (همراه عربی و امکان ورق‌زدن) روی دکمه‌ی زیر بزنید 👇"
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📖 مشاهده کامل", callback_data=f"nahjitem_{category}_{row['number']}")]]
        )

    else:  # mafatih
        row = item["row"]
        cat_label = MAFATIH_CATEGORY_FA.get(row["category"], "📿 مفاتیح‌الجنان")
        title = f"{cat_label} — {row['title']}"
        preview_source = row["translation_text"] or row["arabic_text"]
        description = _snippet(preview_source)
        content = _snippet(preview_source, PREVIEW_LENGTH)
        content += "\n\n📖 برای مشاهده‌ی متن کامل (همراه صوت/تصویر در صورت وجود) روی دکمه‌ی زیر بزنید 👇"
        identifier = row["slug"] if row["slug"] else row["id"]
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📖 مشاهده کامل", callback_data=f"mafitem_{identifier}")]]
        )

    return InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title=title,
        description=description,
        input_message_content=InputTextMessageContent(content[:4096]),
        reply_markup=reply_markup,
    )


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    کاربر در هر چت/گروهی می‌نویسد: @نام_ربات عبارت
    و نتایج جستجوی یکپارچه (حدیث + نهج‌البلاغه + مفاتیح‌الجنان + آیه در صورت فرمت شماره)
    نمایش داده می‌شود. این جستجو نسبت به تفاوت حروف عربی/فارسی، اعراب، و غلط‌های
    تایپی رایج مقاوم است. با اسکرول‌کردن نتایج در تلگرام، صفحه‌ی بعدی (تا سقف
    MAX_RESULTS) خودکار لود می‌شود.
    """
    query_text = update.inline_query.query.strip()

    if not query_text:
        try:
            await update.inline_query.answer([], cache_time=1, is_personal=False)
        except Exception:
            pass
        return

    offset_raw = update.inline_query.offset
    offset = int(offset_raw) if offset_raw.isdigit() else 0

    results = []

    # لینک مستقیم آیه فقط در صفحه‌ی اول نشان داده می‌شود (برای جلوگیری از تکرار در صفحات بعدی)
    if offset == 0 and ":" in query_text and query_text.replace(":", "").isdigit():
        surah, ayah = query_text.split(":")
        try:
            data = await get_ayah(int(surah), int(ayah))
            if data and data.get("arabic"):
                content = f"{data['arabic']}\n\n🔹 ترجمه:\n{data['translation']}"
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title=f"📖 آیه {surah}:{ayah}",
                        description=_snippet(data["translation"], 80),
                        input_message_content=InputTextMessageContent(content),
                    )
                )
        except Exception:
            pass

    # جستجوی یکپارچه‌ی محتوا (حدیث + نهج‌البلاغه + مفاتیح‌الجنان) — فقط شناسه‌ها
    # (سریع، چون فقط از ایندکس FTS می‌خواند)؛ فقط همان صفحه‌ای که الان لازم
    # داریم را کامل واکشی می‌کنیم، نه کل MAX_RESULTS را — وگرنه با نتایج زیاد
    # واکشی کامل چند صد آیتم طول می‌کشد و پاسخ از مهلت تلگرام (~۱۰ ثانیه) رد می‌شود.
    all_raw = search_raw(query_text, limit=MAX_RESULTS)
    page_raw = all_raw[offset: offset + PAGE_SIZE]
    page_items = hydrate_results(page_raw)

    for item in page_items:
        try:
            results.append(_build_result(item))
        except Exception:
            # اگر یک آیتم به هر دلیلی مشکل فرمت داشت، کل نتایج را خراب نکند
            continue

    next_offset = str(offset + PAGE_SIZE) if offset + PAGE_SIZE < len(all_raw) else ""

    try:
        await update.inline_query.answer(results, cache_time=1, is_personal=False, next_offset=next_offset)
    except Exception:
        # اگر کاربر خیلی سریع تایپ کرده و این کوئری منقضی شده (کوئری جدیدتری
        # جایگزینش شده)، تلگرام خطای "query too old" می‌دهد؛ بی‌خطر است و
        # نیازی به لاگ کردن به‌عنوان خطای بحرانی نیست.
        pass
