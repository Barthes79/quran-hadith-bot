import re
import time
import uuid
from collections import defaultdict, deque
from telegram import (
    Update, InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes
from database import (
    search_nahj, search_raw, hydrate_results, search_quran, get_quran_ayahs,
    quran_ayah_count, get_nahj_item,
)
from services.quran_api import get_ayah
from text_utils import normalize_for_search, to_persian_digits
from handlers.nahj import NAHJ_MENU_LABELS, NAHJ_ITEM_LABELS
from handlers.azan_announce import AZAN_SETUP_TOKEN, build_azan_setup_inline_result

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


# کوئری خاصِ اشتراک مستقیم یک حدیث (دکمه‌ی «📤 اشتراک» زیر هر حدیث، که
# switch_inline_query=f"h{hadith_id}" می‌فرستد)
HADITH_SHARE_RE = re.compile(r"^h(\d+)$")


# ==========================================
# Rate limit سمت کاربر برای جستجوی سنگین inline
# ==========================================
# چون تلگرام برای *هر کاراکترِ تایپ‌شده* یک inline query جدید می‌فرستد (نه فقط
# وقتی کاربر Enter بزند)، و هر کوئری یک جستجوی کامل FTS با سقف MAX_RESULTS
# اجرا می‌کند (و اگر نتیجه خالی برگردد، fuzzy matching روی کل ایندکس)، بدون
# محدودیت نرخ، یک کاربر (با تایپ سریع یا اسپم/اسکریپت) می‌تواند CPU سرور را
# قفل کند. این throttle ساده، جستجوهای سنگینِ هر کاربر را به حداکثر
# _RATE_LIMIT_MAX کوئری در هر _RATE_LIMIT_WINDOW ثانیه محدود می‌کند؛ کوئری‌های
# مازاد بدون اجرای جستجو، با نتیجه‌ی خالی پاسخ داده می‌شوند (کاربر همچنان
# پاسخ می‌گیرد، فقط بدون نتیجه، تا وقتی کندتر تایپ کند).
_RATE_LIMIT_WINDOW = 3.0  # ثانیه
_RATE_LIMIT_MAX = 6       # حداکثر جستجوی سنگین مجاز در این بازه، به ازای هر کاربر
_user_query_times: dict = defaultdict(deque)
_rate_limit_calls = 0


def _is_rate_limited(user_id: int) -> bool:
    global _rate_limit_calls
    now = time.monotonic()
    times = _user_query_times[user_id]
    while times and now - times[0] > _RATE_LIMIT_WINDOW:
        times.popleft()

    limited = len(times) >= _RATE_LIMIT_MAX
    if not limited:
        times.append(now)

    # جاروب دوره‌ای سبک برای جلوگیری از رشد بی‌پایان دیکشنری با کاربرهایی
    # که فقط یک‌بار کوئری زده‌اند و صف‌شان خالی شده است؛ نیازی به دقت لحظه‌ای
    # نیست، فقط برای پاک‌سازی حافظه در طول زمان.
    _rate_limit_calls += 1
    if _rate_limit_calls % 500 == 0:
        stale = [uid for uid, q in _user_query_times.items() if not q]
        for uid in stale:
            _user_query_times.pop(uid, None)

    return limited


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
        from handlers.hadith import format_hadith
        title = f"📿 حدیث — {row['narrator'] or 'معصومین'}"
        description = _snippet(row["translation_text"])
        content = format_hadith(row)
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


# ==========================================
# تشخیص «کجا جستجو شود» از کلمه‌ی اول کوئری
# ==========================================
# کاربر باید اول بنویسد کجا بگردیم، بعد موضوع: «حکمت صبر»، «نامه صبر»،
# «خطبه صبر»، «نهج صبر» (کل نهج‌البلاغه) یا «قرآن صبر». کلمه‌ی اول بعد از
# normalize_for_search مقایسه می‌شود (نیم‌فاصله حذف، آ→ا، ي→ی ...)، پس
# «حکمت‌ها»، «قرآن»، «قران» و «نهج‌البلاغه» همگی درست تشخیص داده می‌شوند.
_SCOPE_WORDS = {
    "حکمت": ("nahj", "hekmat"),
    "حکمتها": ("nahj", "hekmat"),
    "نامه": ("nahj", "letter"),
    "نامهها": ("nahj", "letter"),
    "خطبه": ("nahj", "khutbah"),
    "خطبهها": ("nahj", "khutbah"),
    "حدیث": ("hadith", None),
    "احادیث": ("hadith", None),
    "روایت": ("hadith", None),
    "نهج": ("nahj", None),
    "نهجالبلاغه": ("nahj", None),
    "قران": ("quran", None),
    "القران": ("quran", None),
    "quran": ("quran", None),
    "قرءان": ("quran", None),
    "قرانکریم": ("quran", None),
    "قرآنکریم": ("quran", None),
    "ایه": ("quran", None),
    "ایات": ("quran", None),
}

_SCOPE_FA = {
    ("nahj", "hekmat"): "حکمت‌های نهج‌البلاغه",
    ("nahj", "letter"): "نامه‌های نهج‌البلاغه",
    ("nahj", "khutbah"): "خطبه‌های نهج‌البلاغه",
    ("nahj", None): "نهج‌البلاغه",
    ("quran", None): "قرآن",
    ("hadith", None): "احادیث",
}

_LATIN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _parse_scope(query_text: str):
    """(kind, category, term) برمی‌گرداند؛ اگر کلمه‌ی اول محدوده نبود None."""
    tokens = normalize_for_search(query_text).split()
    if not tokens:
        return None
    scope = _SCOPE_WORDS.get(tokens[0])
    if not scope:
        return None
    rest = tokens[1:]
    # «نهج البلاغه صبر» (با فاصله) — «البلاغه» را کنار بگذار
    if scope == ("nahj", None) and rest and rest[0] in ("البلاغه", "بلاغه"):
        rest = rest[1:]
    # «قرآن کریم صبر» (با فاصله) — «کریم» را کنار بگذار
    if scope[0] == "quran" and rest and rest[0] == "کریم":
        rest = rest[1:]
    return scope[0], scope[1], " ".join(rest)


def _bot_mention(context) -> str:
    username = getattr(context.bot, "username", None)
    return f"@{username}" if username else "@نام_ربات"


def _info_result(title: str, description: str, content: str):
    """یک کارت راهنما/پیام در لیست نتایج (برای وقتی جستجوی واقعی نداریم)."""
    return InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title=title,
        description=description,
        input_message_content=InputTextMessageContent(content[:4096]),
    )


def _how_to_result(context):
    bot = _bot_mention(context)
    content = (
        "🔍 برای جستجو، اول بنویسید کجا بگردم، بعد موضوع را:\n\n"
        f"• {bot} حکمت صبر ← فقط در حکمت‌های نهج‌البلاغه\n"
        f"• {bot} نامه صبر ← فقط در نامه‌های نهج‌البلاغه\n"
        f"• {bot} خطبه صبر ← فقط در خطبه‌های نهج‌البلاغه\n"
        f"• {bot} نهج صبر ← در کل نهج‌البلاغه\n"
        f"• {bot} قرآن صبر ← در آیات و ترجمه‌های قرآن\n"
        f"• {bot} حدیث صبر ← در احادیث"
    )
    return _info_result(
        "❗ اول بنویسید کجا جستجو شود",
        "مثلاً: حکمت صبر  |  نامه صبر  |  قرآن صبر  |  حدیث صبر",
        content,
    )


def _need_term_result(kind: str, category, context):
    where = _SCOPE_FA[(kind, category)]
    first_word = {
        ("nahj", "hekmat"): "حکمت", ("nahj", "letter"): "نامه",
        ("nahj", "khutbah"): "خطبه", ("nahj", None): "نهج", ("quran", None): "قرآن",
        ("hadith", None): "حدیث",
    }[(kind, category)]
    return _info_result(
        f"✍️ موضوع جستجو در {where} را بنویسید",
        f"مثلاً: {first_word} صبر",
        f"برای جستجو در {where}، بعد از «{first_word}» موضوع را بنویسید.\nمثال: {_bot_mention(context)} {first_word} صبر",
    )


def _not_found_result(term: str, kind: str, category):
    where = _SCOPE_FA[(kind, category)]
    return _info_result(
        f"نتیجه‌ای برای «{term}» در {where} پیدا نشد",
        "عبارت دیگری را امتحان کنید",
        f"نتیجه‌ای برای «{term}» در {where} پیدا نشد.",
    )


def _build_quran_result(row):
    ayah_fa = to_persian_digits(row["ayah"])
    header = f"📖 {row['surah_name']} — آیه {ayah_fa}"
    translation = row["translation"] or ""
    content = f"{header}\n━━━━━━━━━━━━━━\n\n{row['arabic']}\n\n🔹 ترجمه:\n{translation}"
    return InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title=header,
        description=_snippet(translation),
        input_message_content=InputTextMessageContent(content[:4096]),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("📖 مشاهده در ربات", callback_data=f"ayah_{row['surah']}_{row['ayah']}")]]
        ),
    )


async def _answer(update, results, next_offset="", personal=False):
    try:
        await update.inline_query.answer(
            results, cache_time=1, is_personal=personal, next_offset=next_offset
        )
    except Exception:
        # اگر کاربر خیلی سریع تایپ کرده و این کوئری منقضی شده (کوئری جدیدتری
        # جایگزینش شده)، تلگرام خطای "query too old" می‌دهد؛ بی‌خطر است.
        pass


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    کاربر در هر چت/گروهی می‌نویسد: @نام_ربات <محدوده> <موضوع>
        حکمت صبر  ← فقط حکمت‌های نهج‌البلاغه
        نامه صبر  ← فقط نامه‌ها
        خطبه صبر  ← فقط خطبه‌ها
        نهج صبر   ← کل نهج‌البلاغه
        قرآن صبر  ← آیات و ترجمه‌های قرآن
        حدیث صبر  ← احادیث
    اگر کلمه‌ی اول یکی از این محدوده‌ها نباشد، هیچ جستجویی انجام نمی‌شود و فقط
    یک کارت راهنما نشان داده می‌شود. (استثناها: لینک مستقیم آیه مثل 2:255،
    اشتراک مستقیم حدیث h<id>، و توکن راه‌اندازی اذان.)
    با اسکرول‌کردن نتایج، صفحه‌ی بعد (تا سقف MAX_RESULTS) خودکار لود می‌شود.
    """
    query_text = update.inline_query.query.strip()

    # کوئری خاصِ راه‌اندازی «اعلام اذان در گروه» (از دکمه‌ی
    # switch_inline_query_chosen_chat توی منوی اوقات شرعی می‌آید)
    if query_text == AZAN_SETUP_TOKEN:
        await _answer(update, [build_azan_setup_inline_result()], personal=True)
        return

    if not query_text:
        await _answer(update, [])
        return

    # اشتراک مستقیم یک حدیث خاص (دکمه‌ی «📤 اشتراک»): کوئری اینلاین به‌شکل
    # "h<شناسه>" می‌رسد، نه یک عبارت جستجوی معمولی.
    share_match = HADITH_SHARE_RE.match(query_text)
    if share_match:
        from database import get_hadith_by_id
        row = get_hadith_by_id(int(share_match.group(1)))
        results = []
        if row:
            try:
                results.append(_build_result({"type": "hadith", "row": row}))
            except Exception:
                pass
        await _answer(update, results)
        return

    offset_raw = update.inline_query.offset
    offset = int(offset_raw) if offset_raw.isdigit() else 0

    # لینک مستقیم آیه (مثل 2:255) — جستجوی متنی نیست، پس نیازی به پیشوند ندارد
    if ":" in query_text and query_text.replace(":", "").isdigit():
        results = []
        if offset == 0:
            surah, _, ayah = query_text.partition(":")
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
        await _answer(update, results)
        return

    parsed = _parse_scope(query_text)

    # محدوده مشخص نشده → هیچ نتیجه‌ای از محتوا نشان نده، فقط راهنما
    if parsed is None:
        await _answer(update, [_how_to_result(context)] if offset == 0 else [])
        return

    kind, category, term = parsed

    # محدوده مشخص شده ولی موضوعی ننوشته
    if not term:
        await _answer(update, [_need_term_result(kind, category, context)] if offset == 0 else [])
        return

    # فقط جستجوهای واقعی (سنگین) rate limit می‌شوند، نه کارت‌های راهنما
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is not None and _is_rate_limited(user_id):
        await _answer(update, [], personal=True)
        return

    results = []

    if kind == "nahj":
        # «حکمت 5» / «نامه ۳۱» / «خطبه 192» → رفتن مستقیم به همان مورد
        digits = term.translate(_LATIN_DIGITS)
        if category and digits.isdigit():
            row = get_nahj_item(category, int(digits))
            if row:
                results.append(_build_result({"type": "nahj", "row": row}))
            else:
                results.append(_not_found_result(term, kind, category))
            await _answer(update, results if offset == 0 else [])
            return

        all_raw = search_nahj(term, category, limit=MAX_RESULTS)
        page_items = hydrate_results(all_raw[offset: offset + PAGE_SIZE])
        for item in page_items:
            try:
                results.append(_build_result(item))
            except Exception:
                # اگر یک آیتم به هر دلیلی مشکل فرمت داشت، کل نتایج را خراب نکند
                continue
        total = len(all_raw)

    elif kind == "hadith":
        all_raw = search_raw(term, limit=MAX_RESULTS, types=["hadith"])
        for item in hydrate_results(all_raw[offset: offset + PAGE_SIZE]):
            try:
                results.append(_build_result(item))
            except Exception:
                continue
        total = len(all_raw)

    else:  # quran
        if quran_ayah_count() == 0:
            await _answer(update, [_info_result(
                "⏳ جستجوی قرآن هنوز آماده نیست",
                "چند دقیقه دیگر دوباره امتحان کنید",
                "جستجوی متنی قرآن در حال آماده‌سازی است؛ چند دقیقه دیگر دوباره امتحان کنید.",
            )] if offset == 0 else [])
            return

        all_keys = search_quran(term, limit=MAX_RESULTS)
        for row in get_quran_ayahs(all_keys[offset: offset + PAGE_SIZE]):
            try:
                results.append(_build_quran_result(row))
            except Exception:
                continue
        total = len(all_keys)

    if not results and offset == 0:
        results.append(_not_found_result(term, kind, category))

    next_offset = str(offset + PAGE_SIZE) if offset + PAGE_SIZE < total else ""
    await _answer(update, results, next_offset=next_offset)
