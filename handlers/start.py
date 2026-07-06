from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from config import DEFAULT_TRANSLATIONS
from database import get_user_translation, set_user_translation


def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📖 قرآن کریم", callback_data="menu_quran"),
         InlineKeyboardButton("📿 احادیث معصومین", callback_data="menu_hadith")],
        [InlineKeyboardButton("🔍 جستجو", callback_data="menu_search"),
         InlineKeyboardButton("⭐ علاقه‌مندی‌های من", callback_data="menu_favorites")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="menu_settings")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def clear_keyboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور کمکی برای پاک کردن هر کیبورد ثابت (Reply Keyboard) قدیمی."""
    msg = await update.message.reply_text("کیبورد پاک شد ✅", reply_markup=ReplyKeyboardRemove())


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ابتدا هر کیبورد ثابت (Reply Keyboard) قدیمی که ممکن است از قبل روی این چت
    # باقی مانده باشد را پاک می‌کنیم. این پیام تقریباً نامرئی است.
    cleanup_msg = await update.message.reply_text("⏳", reply_markup=ReplyKeyboardRemove())
    try:
        await cleanup_msg.delete()
    except Exception:
        pass

    text = (
        "🌙 به ربات قرآن و احادیث معصومین خوش آمدید.\n\n"
        "می‌توانید آیات قرآن را همراه با ترجمه و تفسیر مطالعه کنید، "
        "یا احادیث موضوعی از معصومین (ع) را جستجو کنید.\n\n"
        "همچنین می‌توانید این ربات را به گروه خود اضافه کنید تا از قابلیت‌های "
        "پست روزانه و جستجوی درون‌گروهی بهره‌مند شوید."
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "menu_quran":
        from handlers.quran import show_surah_list
        await show_surah_list(update, context, page=0)

    elif query.data == "menu_hadith":
        from handlers.hadith import show_topics
        await show_topics(update, context)

    elif query.data == "menu_search":
        await query.edit_message_text(
            "🔍 برای جستجو، کافیست عبارت مورد نظرتان را مستقیماً برای من ارسال کنید "
            "(مثلاً «صبر» یا «2:255» برای آیه‌ی خاص).\n\n"
            "همچنین در هر گروه یا چت می‌توانید بنویسید:\n"
            "`@نام_ربات صبر`\nتا نتایج بدون خروج از چت نمایش داده شود.",
            parse_mode="Markdown",
        )

    elif query.data == "menu_favorites":
        from handlers.hadith import show_favorites
        await show_favorites(update, context)

    elif query.data == "menu_settings":
        await show_settings(update, context)

    elif query.data == "menu_back":
        await query.edit_message_text("منوی اصلی:", reply_markup=main_menu_keyboard())


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    current = get_user_translation(user_id)

    buttons = []
    for key, code in DEFAULT_TRANSLATIONS.items():
        label = {
            "makarem": "ترجمه مکارم شیرازی",
            "ansarian": "ترجمه انصاریان",
            "fooladvand": "ترجمه فولادوند",
        }.get(key, key)
        mark = "✅ " if key == current else ""
        buttons.append([InlineKeyboardButton(f"{mark}{label}", callback_data=f"set_translation_{key}")])

    buttons.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="menu_back")])

    await query.edit_message_text(
        "⚙️ تنظیمات ترجمه‌ی پیش‌فرض شما:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def set_translation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("ترجمه بروزرسانی شد ✅")
    translation_key = query.data.replace("set_translation_", "")
    set_user_translation(query.from_user.id, translation_key)
    await show_settings(update, context)
