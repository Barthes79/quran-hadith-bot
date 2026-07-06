from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.quran_api import get_surah_list, get_ayah
from database import get_user_translation, add_favorite

PAGE_SIZE = 10


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

    buttons.append([InlineKeyboardButton("⬅️ منوی اصلی", callback_data="menu_back")])

    text = "📖 یک سوره را انتخاب کنید:"
    markup = InlineKeyboardMarkup(buttons)

    if query:
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


async def surah_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.replace("surah_page_", ""))
    await show_surah_list(update, context, page=page)


async def surah_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    surah_number = int(query.data.replace("surah_", ""))
    await show_ayah(update, context, surah_number, 1)


def ayah_navigation_keyboard(surah: int, ayah: int, total_ayahs: int):
    buttons = []
    nav_row = []
    if ayah > 1:
        nav_row.append(InlineKeyboardButton("◀️ آیه قبل", callback_data=f"ayah_{surah}_{ayah-1}"))
    if ayah < total_ayahs:
        nav_row.append(InlineKeyboardButton("آیه بعد ▶️", callback_data=f"ayah_{surah}_{ayah+1}"))
    buttons.append(nav_row)

    buttons.append([
        InlineKeyboardButton("📝 تفسیر", callback_data=f"tafsir_{surah}_{ayah}"),
        InlineKeyboardButton("⭐ افزودن به علاقه‌مندی‌ها", callback_data=f"fav_ayah_{surah}_{ayah}"),
    ])
    buttons.append([InlineKeyboardButton("⬅️ لیست سوره‌ها", callback_data="menu_quran")])
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
            f"📖 سوره {surah_name} - آیه {ayah}\n\n"
            f"{data['arabic']}\n\n"
            f"🔹 ترجمه:\n{data['translation']}"
        )

    markup = ayah_navigation_keyboard(surah, ayah, total_ayahs)

    if query:
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


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


async def tafsir_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    فعلا تفسیر به صورت نمونه پیاده‌سازی شده. در فاز بعد باید به دیتابیس
    تفسیر (مثلاً تفسیر نمونه یا المیزان) وصل شود.
    """
    query = update.callback_query
    await query.answer()
    _, surah, ayah = query.data.split("_")
    await query.message.reply_text(
        f"📝 تفسیر آیه {ayah} سوره {surah} به‌زودی از منبع تفسیری اضافه خواهد شد.\n"
        "(این بخش نیاز به اتصال به دیتابیس تفسیر دارد که در فاز بعدی پروژه تکمیل می‌شود.)"
    )


async def ayah_direct_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE, ref: str):
    """برای زمانی که کاربر مستقیم می‌نویسد مثلا 2:255"""
    try:
        surah, ayah = ref.split(":")
        surah, ayah = int(surah), int(ayah)
    except ValueError:
        return False
    await show_ayah(update, context, surah, ayah)
    return True
