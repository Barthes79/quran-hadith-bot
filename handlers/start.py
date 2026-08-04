from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from config import DEFAULT_TRANSLATIONS
from database import get_user_translation, set_user_translation

# ─────────────────────────────────────────────────────────────
#  Design system یکپارچه‌ی این فایل:
#   • جداکننده‌ی ظریف «━━━━━━━━━━━━━━» زیر هر Header
#   • تیتر هر صفحه Bold + یک Emoji نقش‌دار
#   • یک خط توضیح کوتاه زیر تیتر (نه بیشتر)
#   • دکمه‌ی بازگشت همیشه در پایین‌ترین ردیف
#   • parse_mode="Markdown" روی تمام reply/edit این فایل تا Bold رندر شود
#  هیچ callback_data ای نسبت به نسخه‌ی قبلی حذف/تغییرنام نشده است.
# ─────────────────────────────────────────────────────────────

DIVIDER = "━━━━━━━━━━━━━━"


def main_menu_keyboard():
    """صفحه‌ی خانه: ۳ محور اصلیِ نیت کاربر + راهنما.
    ⭐ ذخیره‌های من و ⚙️ تنظیمات برای کاهش cognitive load به زیرمنوی
    «🧠 تجربه شخصی من» منتقل شدند؛ callback_data هر دو (menu_favorites,
    menu_settings) دست‌نخورده باقی مانده و صرفاً از یک لایه پایین‌تر
    صدا زده می‌شوند، پس هیچ handler ای نیاز به تغییر ندارد."""
    keyboard = [
        [InlineKeyboardButton("📖 قرائت و معارف", callback_data="menu_pillar_reading")],
        [InlineKeyboardButton("🎧 معنویت روزانه", callback_data="menu_pillar_daily")],
        [InlineKeyboardButton("🧠 تجربه شخصی من", callback_data="menu_pillar_personal")],
        [InlineKeyboardButton("📚 راهنما", callback_data="menu_help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def pillar_reading_keyboard():
    """زیرمنوی «قرائت و معارف»: قرآن، حدیث، نهج‌البلاغه، مفاتیح‌الجنان."""
    keyboard = [
        [InlineKeyboardButton("📖 قرآن کریم", callback_data="menu_quran"),
         InlineKeyboardButton("📿 احادیث معصومین", callback_data="menu_hadith")],
        [InlineKeyboardButton("🕌 نهج‌البلاغه", callback_data="menu_nahj"),
         InlineKeyboardButton("📗 مفاتیح‌الجنان", callback_data="menu_mafatih")],
        [InlineKeyboardButton("🏠 بازگشت به خانه", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def pillar_daily_keyboard():
    """زیرمنوی «معنویت روزانه»: مداحی/مولودی و اوقات شرعی/اذان."""
    keyboard = [
        [InlineKeyboardButton("🎙 مداحی و مولودی", callback_data="menu_madahi")],
        [InlineKeyboardButton("🕋 اوقات شرعی و اذان", callback_data="menu_prayer")],
        [InlineKeyboardButton("🏠 بازگشت به خانه", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def pillar_personal_keyboard():
    """زیرمنوی «تجربه شخصی من»: آزمون، ذخیره‌ها، تنظیمات.
    دکمه‌ی آزمون مستقیماً callback_data="quizmenu" را صدا می‌زند که از قبل
    در main.py به‌صورت مستقل ثبت شده (quiz_menu_callback)، پس نیازی به
    تغییر main.py یا quiz.py نیست."""
    keyboard = [
        [InlineKeyboardButton("🧠 آزمون", callback_data="quizmenu")],
        [InlineKeyboardButton("⭐ ذخیره‌های من", callback_data="menu_favorites")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="menu_settings")],
        [InlineKeyboardButton("🏠 بازگشت به خانه", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


HOME_TEXT = (
    "🌙 *همراه قرآن و اهل‌بیت*\n"
    "فضایی آرام برای قرآن، حدیث و معارف اهل‌بیت\n"
    f"{DIVIDER}\n\n"
    "📖 *قرائت و معارف*\n"
    "قرآن، حدیث، نهج‌البلاغه و مفاتیح‌الجنان\n\n"
    "🎧 *معنویت روزانه*\n"
    "مداحی، مولودی و اوقات شرعی\n\n"
    "🧠 *تجربه شخصی من*\n"
    "آزمون، ذخیره‌ها و تنظیمات\n"
    f"{DIVIDER}\n"
    "یکی از بخش‌ها را انتخاب کنید 👇"
)

READING_TEXT = (
    "📖 *قرائت و معارف*\n"
    "قرآن، حدیث و میراث گران‌بهای اهل‌بیت\n"
    f"{DIVIDER}\n"
    "بخش مورد نظر را انتخاب کنید 👇"
)

DAILY_TEXT = (
    "🎧 *معنویت روزانه*\n"
    "آرامشی برای گوش و دل، در طول روز\n"
    f"{DIVIDER}\n"
    "بخش مورد نظر را انتخاب کنید 👇"
)

PERSONAL_TEXT = (
    "🧠 *تجربه شخصی من*\n"
    "فضای اختصاصی شما در ربات\n"
    f"{DIVIDER}\n"
    "بخش مورد نظر را انتخاب کنید 👇"
)


async def clear_keyboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور کمکی برای پاک کردن هر کیبورد ثابت (Reply Keyboard) قدیمی."""
    msg = await update.message.reply_text("کیبورد پاک شد ✅", reply_markup=ReplyKeyboardRemove())


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["search_mode"] = False
    context.user_data["id_search_mode"] = False
    cleanup_msg = await update.message.reply_text("⏳", reply_markup=ReplyKeyboardRemove())
    try:
        await cleanup_msg.delete()
    except Exception:
        pass

    await update.message.reply_text(
        HOME_TEXT, reply_markup=main_menu_keyboard(), parse_mode="Markdown"
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass

    # با انتخاب هر بخشی از منوی اصلی، از حالت جستجوی آزادِ بخش قبلی (اگر
    # فعال بود) خارج می‌شویم؛ این‌طوری متن‌های بعدی کاربر دوباره به همون
    # بخش جدید (مثل حدیث موضوعی، نهج‌البلاغه و ...) به‌جای جستجوی بخش قبلی
    # فرستاده می‌شوند. جستجو دیگه یک دکمه‌ی سراسری در منوی اصلی نیست؛ هر
    # بخش (احادیث/نهج‌البلاغه/مفاتیح‌الجنان) دکمه‌ی «🔍 جستجو» مخصوص خودش رو
    # داخل منوی همون بخش داره (search_start_callback در handlers/hadith.py).
    context.user_data["search_mode"] = False
    context.user_data["search_scope"] = None
    context.user_data["id_search_mode"] = False

    if query.data == "menu_quran":
        from handlers.quran import show_surah_list
        await show_surah_list(update, context, page=0)

    elif query.data == "menu_hadith":
        from handlers.hadith import show_topics
        await show_topics(update, context)

    elif query.data == "menu_favorites":
        from handlers.favorites import favorites_command
        await favorites_command(update, context)

    elif query.data == "menu_nahj":
        from handlers.nahj import show_nahj_menu
        await show_nahj_menu(update, context)

    elif query.data == "menu_mafatih":
        from handlers.mafatih import mafatih_menu_callback
        await mafatih_menu_callback(update, context)

    elif query.data == "menu_prayer":
        from handlers.prayer import prayer_back_callback
        await prayer_back_callback(update, context)

    elif query.data == "menu_madahi":
        from handlers.madahi import madahi_menu_callback
        await madahi_menu_callback(update, context)

    # سه محور اصلیِ صفحه‌ی خانه؛ هرکدام یک زیرمنو نشان می‌دهند که به همان
    # callback_dataهای قدیمی (menu_quran, menu_hadith, ...) وصل است.
    elif query.data == "menu_pillar_reading":
        await query.edit_message_text(
            READING_TEXT, reply_markup=pillar_reading_keyboard(), parse_mode="Markdown"
        )

    elif query.data == "menu_pillar_daily":
        await query.edit_message_text(
            DAILY_TEXT, reply_markup=pillar_daily_keyboard(), parse_mode="Markdown"
        )

    elif query.data == "menu_pillar_personal":
        await query.edit_message_text(
            PERSONAL_TEXT, reply_markup=pillar_personal_keyboard(), parse_mode="Markdown"
        )

    # menu_main و menu_back هر دو از فایل‌های مختلف (mafatih.py، hadith.py،
    # nahj.py، quran.py، prayer.py، madahi.py، help.py، favorites.py)
    # صدا زده می‌شوند؛ هر دو دقیقاً به همین صفحه‌ی خانه‌ی یکسان برمی‌گردند
    # تا کاربر با دو برچسبِ متفاوت برای یک مقصد گیج نشود.
    elif query.data in ("menu_main", "menu_back"):
        await query.edit_message_text(
            HOME_TEXT, reply_markup=main_menu_keyboard(), parse_mode="Markdown"
        )

    elif query.data == "menu_settings":
        await show_settings(update, context)

    elif query.data == "menu_help":
        from handlers.help import help_command
        await help_command(update, context)


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    current = get_user_translation(user_id)

    buttons = []
    for key, code in DEFAULT_TRANSLATIONS.items():
        label = {
            "makarem": "مکارم شیرازی",
            "ansarian": "انصاریان",
            "fooladvand": "فولادوند",
        }.get(key, key)
        mark = "✅ " if key == current else "○ "
        buttons.append([InlineKeyboardButton(f"{mark}{label}", callback_data=f"set_translation_{key}")])

    buttons.append([InlineKeyboardButton("⬅️ بازگشت به خانه", callback_data="menu_back")])

    settings_text = (
        "⚙️ *تنظیمات ترجمه*\n"
        "ترجمه‌ی پیش‌فرض برای نمایش آیات را انتخاب کنید:\n"
        f"{DIVIDER}"
    )

    await query.edit_message_text(
        settings_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


async def set_translation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("ترجمه بروزرسانی شد ✅")
    translation_key = query.data.replace("set_translation_", "")
    set_user_translation(query.from_user.id, translation_key)
    await show_settings(update, context)
