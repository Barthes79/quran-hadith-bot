import uuid
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes
from database import search_all
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

# سقف تعداد نتیجه‌ای که در هر اینلاین‌کوئری برمی‌گردانیم (سرعت + خوانایی)
RESULT_LIMIT = 15


def _snippet(text: str, length: int = 100) -> str:
    if not text:
        return ""
    text = text.strip()
    return text if len(text) <= length else text[:length].rstrip() + "…"


def _build_result(item: dict) -> InlineQueryResultArticle:
    """یک آیتم استانداردشده (خروجی search_all) را به نتیجه‌ی اینلاین تلگرام تبدیل می‌کند."""
    if item["type"] == "hadith":
        row = item["row"]
        title = f"📿 حدیث — {row['narrator'] or 'معصومین'}"
        description = _snippet(row["translation_text"])
        content = f"{row['arabic_text']}\n\n🔹 ترجمه:\n{row['translation_text']}"
        if row["source_book"]:
            content += f"\n\n📚 منبع: {row['source_book']}"

    elif item["type"] == "nahj":
        row = item["row"]
        category = row["category"]
        item_label = NAHJ_ITEM_LABELS.get(category, "")
        cat_label = NAHJ_MENU_LABELS.get(category, "🕌 نهج‌البلاغه")
        title_suffix = f" — {row['title']}" if row["title"] else ""
        title = f"{cat_label} — {item_label} {row['number']}{title_suffix}"
        description = _snippet(row["translation_text"])
        content_parts = []
        if row["arabic_text"]:
            content_parts.append(row["arabic_text"])
        content_parts.append(row["translation_text"])
        content = "\n\n".join(content_parts)

    else:  # mafatih
        row = item["row"]
        cat_label = MAFATIH_CATEGORY_FA.get(row["category"], "📿 مفاتیح‌الجنان")
        title = f"{cat_label} — {row['title']}"
        description = _snippet(row["translation_text"] or row["arabic_text"])
        content_parts = []
        if row["arabic_text"]:
            content_parts.append(row["arabic_text"])
        if row["translation_text"]:
            content_parts.append(f"🔹 ترجمه:\n{row['translation_text']}")
        content = "\n\n".join(content_parts)

    return InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title=title,
        description=description,
        input_message_content=InputTextMessageContent(content[:4096]),
    )


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    کاربر در هر چت/گروهی می‌نویسد: @نام_ربات عبارت
    و نتایج جستجوی یکپارچه (حدیث + نهج‌البلاغه + مفاتیح‌الجنان + آیه در صورت فرمت شماره)
    نمایش داده می‌شود. این جستجو نسبت به تفاوت حروف عربی/فارسی، اعراب، و غلط‌های
    تایپی رایج مقاوم است.
    """
    query_text = update.inline_query.query.strip()
    results = []

    if not query_text:
        await update.inline_query.answer(results, cache_time=1, is_personal=False)
        return

    # اگر فرمت شماره آیه بود (مثلا 2:255)
    if ":" in query_text and query_text.replace(":", "").isdigit():
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

    # جستجوی یکپارچه‌ی محتوا (حدیث + نهج‌البلاغه + مفاتیح‌الجنان)
    items = search_all(query_text, limit=RESULT_LIMIT)
    for item in items:
        try:
            results.append(_build_result(item))
        except Exception:
            # اگر یک آیتم به هر دلیلی مشکل فرمت داشت، کل نتایج را خراب نکند
            continue

    await update.inline_query.answer(results, cache_time=1, is_personal=False)
