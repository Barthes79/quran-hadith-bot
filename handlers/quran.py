import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.quran_api import get_surah_list, get_ayah, get_audio_url
from database import get_user_translation, add_favorite, get_ayah_tafsir, set_ayah_tafsir
from config import ADMIN_IDS
from handlers.ownership import register_owner, GROUP_CHAT_TYPES

PAGE_SIZE = 10
AYAH_PAGE_SIZE = 96  # تعداد شماره آیه در هر صفحه از لیست آیات یک سوره
AYAHS_PER_ROW = 8

# هم‌راستا با سیستم طراحی handlers/start.py؛ عمداً این‌جا هم تعریف شده
# (نه import از start.py) تا هیچ وابستگی بین‌ماژولیِ جدیدی ساخته نشود.
DIVIDER = "━━━━━━━━━━━━━━"

# ==========================================================================
# جستجوی آیه با نام فارسی سوره (مثلاً «بقره 25» یا «سوره بقره آیه 25»)
# ==========================================================================

# برای هر سوره چند تلفظ/نگارش رایج فارسی ثبت شده تا هرکدام را کاربر تایپ کند
# شناسایی شود. لازم نیست همه‌ی حالت‌ها اینجا باشد؛ رایج‌ترین‌ها کافی است.
SURAH_NAME_ALIASES = {
    1: ["فاتحه", "الفاتحه", "حمد", "فاتحة الکتاب"],
    2: ["بقره", "البقره"],
    3: ["آل عمران", "ال عمران", "عمران"],
    4: ["نساء", "النساء"],
    5: ["مائده", "مایده", "المائده"],
    6: ["انعام", "الانعام"],
    7: ["اعراف", "الاعراف"],
    8: ["انفال", "الانفال"],
    9: ["توبه", "التوبه", "برائت", "براءت"],
    10: ["یونس"],
    11: ["هود"],
    12: ["یوسف"],
    13: ["رعد", "الرعد"],
    14: ["ابراهیم"],
    15: ["حجر", "الحجر"],
    16: ["نحل", "النحل"],
    17: ["اسراء", "الاسراء", "بنی اسرائیل", "بنی اسراییل"],
    18: ["کهف", "الکهف"],
    19: ["مریم"],
    20: ["طه"],
    21: ["انبیاء", "الانبیاء", "انبیا"],
    22: ["حج", "الحج"],
    23: ["مومنون", "المومنون", "مؤمنون"],
    24: ["نور", "النور"],
    25: ["فرقان", "الفرقان"],
    26: ["شعراء", "الشعراء", "شعرا"],
    27: ["نمل", "النمل"],
    28: ["قصص", "القصص"],
    29: ["عنکبوت", "العنکبوت"],
    30: ["روم", "الروم"],
    31: ["لقمان"],
    32: ["سجده", "السجده"],
    33: ["احزاب", "الاحزاب"],
    34: ["سبا", "سباء", "سبأ"],
    35: ["فاطر"],
    36: ["یس", "یاسین"],
    37: ["صافات", "الصافات"],
    38: ["ص"],
    39: ["زمر", "الزمر"],
    40: ["غافر", "مومن", "المومن"],
    41: ["فصلت"],
    42: ["شوری", "الشوری"],
    43: ["زخرف", "الزخرف"],
    44: ["دخان", "الدخان"],
    45: ["جاثیه", "الجاثیه"],
    46: ["احقاف", "الاحقاف"],
    47: ["محمد"],
    48: ["فتح", "الفتح"],
    49: ["حجرات", "الحجرات"],
    50: ["ق"],
    51: ["ذاریات", "الذاریات"],
    52: ["طور", "الطور"],
    53: ["نجم", "النجم"],
    54: ["قمر", "القمر"],
    55: ["رحمن", "الرحمن"],
    56: ["واقعه", "الواقعه"],
    57: ["حدید", "الحدید"],
    58: ["مجادله", "المجادله"],
    59: ["حشر", "الحشر"],
    60: ["ممتحنه", "الممتحنه"],
    61: ["صف", "الصف"],
    62: ["جمعه", "الجمعه"],
    63: ["منافقون", "المنافقون"],
    64: ["تغابن", "التغابن"],
    65: ["طلاق", "الطلاق"],
    66: ["تحریم", "التحریم"],
    67: ["ملک", "الملک"],
    68: ["قلم", "القلم"],
    69: ["حاقه", "الحاقه"],
    70: ["معارج", "المعارج"],
    71: ["نوح"],
    72: ["جن", "الجن"],
    73: ["مزمل", "المزمل"],
    74: ["مدثر", "المدثر"],
    75: ["قیامه", "قیامت", "القیامه"],
    76: ["انسان", "الانسان", "دهر", "الدهر"],
    77: ["مرسلات", "المرسلات"],
    78: ["نبا", "النبا"],
    79: ["نازعات", "النازعات"],
    80: ["عبس"],
    81: ["تکویر", "التکویر"],
    82: ["انفطار", "الانفطار"],
    83: ["مطففین", "المطففین"],
    84: ["انشقاق", "الانشقاق"],
    85: ["بروج", "البروج"],
    86: ["طارق", "الطارق"],
    87: ["اعلی", "الاعلی"],
    88: ["غاشیه", "الغاشیه"],
    89: ["فجر", "الفجر"],
    90: ["بلد", "البلد"],
    91: ["شمس", "الشمس"],
    92: ["لیل", "اللیل"],
    93: ["ضحی", "الضحی"],
    94: ["شرح", "انشراح", "الشرح", "الانشراح"],
    95: ["تین", "التین"],
    96: ["علق", "العلق"],
    97: ["قدر", "القدر"],
    98: ["بینه", "البینه"],
    99: ["زلزله", "الزلزله"],
    100: ["عادیات", "العادیات"],
    101: ["قارعه", "القارعه"],
    102: ["تکاثر", "التکاثر"],
    103: ["عصر", "العصر"],
    104: ["همزه", "الهمزه"],
    105: ["فیل", "الفیل"],
    106: ["قریش"],
    107: ["ماعون", "الماعون"],
    108: ["کوثر", "الکوثر"],
    109: ["کافرون", "الکافرون"],
    110: ["نصر", "النصر"],
    111: ["مسد", "ابی لهب", "المسد"],
    112: ["اخلاص", "توحید", "الاخلاص"],
    113: ["فلق", "الفلق"],
    114: ["ناس", "الناس"],
}

_PERSIAN_ARABIC_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _to_ascii_digits(s: str) -> str:
    return s.translate(_PERSIAN_ARABIC_DIGITS)


def _normalize_surah_name(name: str) -> str:
    """یکسان‌سازی نام سوره برای مقایسه: حروف عربی/فارسی مشابه، اعراب، فاصله‌ها."""
    name = _to_ascii_digits(name).strip()
    name = name.replace("ي", "ی").replace("ك", "ک").replace("ة", "ه").replace("ۀ", "ه")
    name = re.sub(r"[\u064B-\u0652\u0670\u200c]", " ", name)  # اعراب + نیم‌فاصله
    name = re.sub(r"\s+", " ", name).strip()
    return name


SURAH_NAME_TO_NUMBER = {}
for _num, _aliases in SURAH_NAME_ALIASES.items():
    for _alias in _aliases:
        SURAH_NAME_TO_NUMBER[_normalize_surah_name(_alias)] = _num

# «سوره» / «سوره‌ی» در ابتدا و «آیه»/«ایه» قبل از شماره، اختیاری هستند
_SURAH_AYAH_PATTERN = re.compile(
    r"^(?:سوره\s*(?:ی|ء)?\s+)?(?P<name>[^\d]+?)\s*(?:آیه|ایه|ايه)?\s*"
    r"(?P<num>[0-9۰-۹٠-٩]+)\s*$"
)




async def show_surah_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    surahs = await get_surah_list()

    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_items = surahs[start:end]

    buttons = []
    row = []
    for s in page_items:
        label = f"{s['number']}. {s['name']}"
        row.append(InlineKeyboardButton(label, callback_data=f"surah_{s['number']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"surah_page_{page-1}"))
    if end < len(surahs):
        nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"surah_page_{page+1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("🔍 جستجو در قرآن", callback_data="quran_search_info")])
    buttons.append([InlineKeyboardButton("🏠 بازگشت به خانه", callback_data="menu_back")])

    text = (
        "📖 *قرآن کریم*\n"
        "یکی از سوره‌ها را انتخاب کنید\n"
        f"{DIVIDER}"
    )
    markup = InlineKeyboardMarkup(buttons)

    if query:
        await query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")


async def surah_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.replace("surah_page_", ""))
    await show_surah_list(update, context, page=page)


async def quran_search_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌ی «🔍 جستجو در قرآن». برخلاف احادیث/نهج‌البلاغه/مفاتیح، متن آیات
    از یک API خارجی خونده می‌شه (نه از دیتابیس محلی)، پس جستجوی متنی در
    محتوای آیات فعلاً امکان‌پذیر نیست؛ به‌جاش راهنمای رفتن مستقیم به یک آیه
    (که قبلاً هم در هر بخشی از ربات کار می‌کند) نشون داده می‌شه."""
    query = update.callback_query
    await query.answer()
    text = (
        "🔍 *جستجو در قرآن کریم*\n"
        "برای رفتن مستقیم به یک آیه، همین الان یکی از این شکل‌ها را بنویسید\n"
        f"{DIVIDER}\n\n"
        "• 2:255  ← سوره ۲، آیه ۲۵۵\n"
        "• بقره 255  ← سوره بقره، آیه ۲۵۵\n"
        "• سوره بقره آیه 255\n\n"
        "فعلاً جستجوی متنی در محتوای آیات پشتیبانی نمی‌شود؛ فقط جست‌وجو بر اساس نام سوره و شماره‌ی آیه امکان‌پذیر است."
    )
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ بازگشت", callback_data="menu_quran")]]
        ),
        parse_mode="Markdown",
    )


async def show_ayah_list(update: Update, context: ContextTypes.DEFAULT_TYPE, surah: int, page: int = 0):
    query = update.callback_query
    surahs = await get_surah_list()
    surah_info = next((s for s in surahs if s["number"] == surah), None)
    total_ayahs = surah_info["numberOfAyahs"] if surah_info else 286
    surah_name = surah_info["name"] if surah_info else surah

    start = page * AYAH_PAGE_SIZE + 1
    end = min(start + AYAH_PAGE_SIZE - 1, total_ayahs)

    buttons = []
    row = []
    for n in range(start, end + 1):
        row.append(InlineKeyboardButton(str(n), callback_data=f"ayah_{surah}_{n}"))
        if len(row) == AYAHS_PER_ROW:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"ayahlist_{surah}_{page-1}"))
    if end < total_ayahs:
        nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"ayahlist_{surah}_{page+1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("⬅️ لیست سوره‌ها", callback_data="menu_quran")])

    text = (
        f"📖 سوره {surah_name} — {total_ayahs} آیه\n"
        f"{DIVIDER}\n\n"
        "شماره‌ی آیه‌ای که می‌خواهید را انتخاب کنید:"
    )
    markup = InlineKeyboardMarkup(buttons)

    if query:
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


async def ayah_list_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, surah, page = query.data.split("_")
    await show_ayah_list(update, context, int(surah), page=int(page))


async def surah_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    surah_number = int(query.data.replace("surah_", ""))
    await show_ayah_list(update, context, surah_number, page=0)


def ayah_navigation_keyboard(surah: int, ayah: int, total_ayahs: int):
    buttons = []
    nav_row = []
    if ayah > 1:
        nav_row.append(InlineKeyboardButton("◀️ آیه قبل", callback_data=f"ayah_{surah}_{ayah-1}"))
    if ayah < total_ayahs:
        nav_row.append(InlineKeyboardButton("آیه بعد ▶️", callback_data=f"ayah_{surah}_{ayah+1}"))
    buttons.append(nav_row)

    buttons.append([
        #InlineKeyboardButton("📝 تفسیر", callback_data=f"tafsir_{surah}_{ayah}"),
        InlineKeyboardButton("🔊 پخش تلاوت", callback_data=f"audio_{surah}_{ayah}"),
    ])
    buttons.append([InlineKeyboardButton("⭐ افزودن به علاقه‌مندی‌ها", callback_data=f"fav_ayah_{surah}_{ayah}")])
    buttons.append([
        InlineKeyboardButton("🔢 لیست آیات", callback_data=f"ayahlist_{surah}_0"),
        InlineKeyboardButton("⬅️ لیست سوره‌ها", callback_data="menu_quran"),
    ])
    return InlineKeyboardMarkup(buttons)


async def show_ayah(update: Update, context: ContextTypes.DEFAULT_TYPE, surah: int, ayah: int):
    query = update.callback_query
    user_id = query.from_user.id if query else update.effective_user.id
    translation_key = get_user_translation(user_id)

    surahs = await get_surah_list()
    surah_info = next((s for s in surahs if s["number"] == surah), None)
    total_ayahs = surah_info["numberOfAyahs"] if surah_info else 286

    data = await get_ayah(surah, ayah, translation_key)
    if not data or not data.get("arabic"):
        text = "متاسفانه در دریافت این آیه مشکلی پیش آمد. لطفاً دوباره تلاش کنید."
    else:
        surah_name = surah_info["name"] if surah_info else surah
        text = (
            f"📖 {surah_name} — آیه {ayah}\n"
            f"{DIVIDER}\n\n"
            f"{data['arabic']}\n\n"
            f"🔹 ترجمه:\n{data['translation']}"
        )

    markup = ayah_navigation_keyboard(surah, ayah, total_ayahs)

    if query:
        await query.edit_message_text(text, reply_markup=markup)
    else:
        sent = await update.message.reply_text(text, reply_markup=markup)
        # اگر این پیام در پاسخ به تایپ مستقیم در گروه ساخته شده (مثلاً «بقره 5»)،
        # فقط همان کاربر باید بتواند دکمه‌های زیر آن را استفاده کند.
        if update.effective_chat and update.effective_chat.type in GROUP_CHAT_TYPES:
            register_owner(update.effective_chat.id, sent.message_id, update.effective_user.id)


async def ayah_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, surah, ayah = query.data.split("_")
    await show_ayah(update, context, int(surah), int(ayah))


async def fav_ayah_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, _, surah, ayah = query.data.split("_")
    add_favorite(query.from_user.id, "ayah", f"{surah}:{ayah}")
    await query.answer("به علاقه‌مندی‌ها اضافه شد ⭐")


async def audio_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("در حال آماده‌سازی صوت...")
    _, surah, ayah = query.data.split("_")
    surah, ayah = int(surah), int(ayah)

    data = await get_ayah(surah, ayah)
    if not data or not data.get("number"):
        await query.message.reply_text("متاسفانه در دریافت صوت این آیه مشکلی پیش آمد.")
        return

    audio_url = get_audio_url(data["number"])
    try:
        await context.bot.send_audio(
            chat_id=update.effective_chat.id,
            audio=audio_url,
            title=f"تلاوت سوره {surah} آیه {ayah}",
            performer="مشاری راشد العفاسی",
        )
    except Exception:
        await query.message.reply_text(
            f"مشکلی در پخش صوت پیش آمد. می‌توانید مستقیم از این لینک گوش دهید:\n{audio_url}"
        )


async def tafsir_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, surah, ayah = query.data.split("_")
    surah, ayah = int(surah), int(ayah)

    row = get_ayah_tafsir(surah, ayah)
    if row:
        text = f"📝 تفسیر آیه {ayah} سوره {surah}:\n\n{row['tafsir_text']}"
        if row["source"]:
            text += f"\n\n📚 منبع: {row['source']}"
    else:
        text = (
            f"📝 هنوز تفسیری برای آیه {ayah} سوره {surah} ثبت نشده است.\n"
            "ادمین می‌تواند با دستور /addqtafsir آن را اضافه کند."
        )
    await query.message.reply_text(text)


# ---------------- دستور ادمین برای افزودن/ویرایش تفسیر یک آیه ----------------
# فرمت: /addqtafsir سوره:آیه متن تفسیر
# مثال: /addqtafsir 2:255 این آیه معروف به آیة الکرسی است و به توحید و قدرت خداوند اشاره دارد.

async def add_quran_tafsir_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه‌ی این دستور را ندارید.")
        return

    parts = update.message.text.split(" ", 2)
    if len(parts) < 3:
        await update.message.reply_text(
            "فرمت صحیح استفاده:\n"
            "/addqtafsir سوره:آیه متن تفسیر\n\n"
            "مثال:\n"
            "/addqtafsir 2:255 این آیه معروف به آیة الکرسی است و به توحید و قدرت خداوند اشاره دارد."
        )
        return

    ref = parts[1]
    if not re.match(r"^\d+:\d+$", ref):
        await update.message.reply_text("فرمت سوره:آیه درست نیست. مثال درست: 2:255")
        return

    surah, ayah = ref.split(":")
    tafsir_text = parts[2].strip()

    set_ayah_tafsir(int(surah), int(ayah), tafsir_text)
    await update.message.reply_text(f"✅ تفسیر آیه {ayah} سوره {surah} با موفقیت ثبت/به‌روزرسانی شد.")


async def ayah_direct_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE, ref: str):
    """برای زمانی که کاربر مستقیم می‌نویسد مثلا 2:255"""
    try:
        surah, ayah = ref.split(":")
        surah, ayah = int(surah), int(ayah)
    except ValueError:
        return False
    await show_ayah(update, context, surah, ayah)
    return True


async def surah_name_ayah_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """برای زمانی که کاربر با نام فارسی سوره می‌نویسد، مثلاً «بقره 25»،
    «سوره بقره 25» یا «سوره بقره آیه 25». اگر متن با این الگو مطابقت نداشت
    یا نام سوره شناسایی نشد، False برمی‌گرداند تا جستجوی حدیث ادامه پیدا کند."""
    text = text.strip()
    if not text:
        return False

    match = _SURAH_AYAH_PATTERN.match(text)
    if not match:
        return False

    raw_name = match.group("name").strip()
    raw_num = _to_ascii_digits(match.group("num"))
    if not raw_name or not raw_num.isdigit():
        return False

    ayah_num = int(raw_num)
    if ayah_num <= 0:
        return False

    surah_number = SURAH_NAME_TO_NUMBER.get(_normalize_surah_name(raw_name))
    if not surah_number:
        return False

    await show_ayah(update, context, surah_number, ayah_num)
    return True
