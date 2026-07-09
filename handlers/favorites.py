from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_favorites, get_hadith_by_id, get_nahj_item, get_mafatih_by_id
from services.quran_api import get_ayah


async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("📿 احادیث", callback_data="favorites_hadith")],
        [InlineKeyboardButton("📖 قرآن", callback_data="favorites_quran")],
        [InlineKeyboardButton("🕌 نهج‌البلاغه", callback_data="favorites_nahj")],
        [InlineKeyboardButton("📗 مفاتیح‌الجنان", callback_data="favorites_mafatih")],
        [InlineKeyboardButton("⬅️ منوی اصلی", callback_data="menu_back")],
    ]
    text = "⭐ علاقه‌مندی‌ها\n\nدسته مورد نظر را انتخاب کنید:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(buttons)
        )


async def favorites_hadith_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    rows = get_favorites(query.from_user.id)
    hadith_rows = [r for r in rows if r["item_type"] == "hadith"]

    if not hadith_rows:
        await query.edit_message_text("📿 هنوز حدیثی در علاقه‌مندی‌ها ذخیره نکرده‌اید.")
        return

    text = "📿 علاقه‌مندی‌های احادیث شما:\n\n"
    for r in hadith_rows[:10]:
        hadith = get_hadith_by_id(int(r["item_ref"]))
        if hadith:
            text += f"📿 {hadith['arabic_text']}\n\n"
            text += f"📖 ترجمه:\n{hadith['translation_text']}\n"
            if hadith["tafsir_text"]:
                text += f"\n📝 شرح:\n{hadith['tafsir_text']}\n"
            text += "\n────────────\n\n"

    buttons = [[InlineKeyboardButton("⬅️ بازگشت", callback_data="favorites_back")]]
    await query.edit_message_text(text or "📿 موردی پیدا نشد.", reply_markup=InlineKeyboardMarkup(buttons))


async def favorites_quran_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    rows = get_favorites(query.from_user.id)
    ayahs = [r for r in rows if r["item_type"] == "ayah"]

    if not ayahs:
        await query.edit_message_text("📖 هنوز آیه‌ای در علاقه‌مندی‌ها ذخیره نکرده‌اید.")
        return

    text = "📖 علاقه‌مندی‌های قرآن شما:\n\n"

    for r in ayahs[:10]:
        try:
            surah, ayah = map(int, r["item_ref"].split(":"))
            data = await get_ayah(surah, ayah)
            if data:
                text += "📖 آیه قرآن:\n\n"
                text += f"{data.get('arabic', '')}\n\n"
                text += f"📖 ترجمه:\n{data.get('translation', '')}\n"
                text += "\n────────────\n\n"
            else:
                text += f"📖 آیه ذخیره شده: {r['item_ref']}\n\n────────────\n\n"
        except Exception:
            text += f"📖 آیه ذخیره شده: {r['item_ref']}\n\n────────────\n\n"

    buttons = [[InlineKeyboardButton("⬅️ بازگشت", callback_data="favorites_back")]]
    await query.edit_message_text(text or "📖 موردی پیدا نشد.", reply_markup=InlineKeyboardMarkup(buttons))


async def favorites_nahj_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    from handlers.nahj import NAHJ_MENU_LABELS, NAHJ_ITEM_LABELS

    rows = get_favorites(query.from_user.id)
    nahj_rows = [r for r in rows if r["item_type"] == "nahj"]

    if not nahj_rows:
        await query.edit_message_text(
            "🕌 هنوز موردی از نهج‌البلاغه در علاقه‌مندی‌ها ذخیره نکرده‌اید.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ بازگشت", callback_data="favorites_back")]]
            ),
        )
        return

    text = "🕌 علاقه‌مندی‌های نهج‌البلاغه‌ی شما:\n\n"
    for r in nahj_rows[:10]:
        try:
            category, number = r["item_ref"].split(":")
            number = int(number)
        except ValueError:
            continue
        item = get_nahj_item(category, number)
        if item:
            item_label = NAHJ_ITEM_LABELS.get(category, category)
            title = f" — {item['title']}" if item["title"] else ""
            text += f"{NAHJ_MENU_LABELS.get(category, category)} — {item_label} {number}{title}\n\n"
            text += f"{item['arabic_text']}\n\n"
            text += f"📖 ترجمه:\n{item['translation_text']}\n"
            if item["tafsir_text"]:
                text += f"\n📝 شرح:\n{item['tafsir_text']}\n"
            text += "\n────────────\n\n"

    buttons = [[InlineKeyboardButton("⬅️ بازگشت", callback_data="favorites_back")]]
    await query.edit_message_text(text or "🕌 موردی پیدا نشد.", reply_markup=InlineKeyboardMarkup(buttons))


async def favorites_mafatih_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    rows = get_favorites(query.from_user.id)
    maf_rows = [r for r in rows if r["item_type"] == "mafatih"]

    if not maf_rows:
        await query.edit_message_text(
            "📗 هنوز موردی از مفاتیح‌الجنان در علاقه‌مندی‌ها ذخیره نکرده‌اید.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ بازگشت", callback_data="favorites_back")]]
            ),
        )
        return

    text = "📗 علاقه‌مندی‌های مفاتیح‌الجنان شما:\n\n"
    for r in maf_rows[:10]:
        try:
            item = get_mafatih_by_id(int(r["item_ref"]))
        except ValueError:
            continue
        if item:
            text += f"📗 {item['title']}\n\n"
            text += f"{item['arabic_text']}\n\n"
            if item["translation_text"]:
                text += f"🔹 ترجمه:\n{item['translation_text']}\n"
            if item["tafsir_text"]:
                text += f"\n📝 توضیح:\n{item['tafsir_text']}\n"
            text += "\n────────────\n\n"

    buttons = [[InlineKeyboardButton("⬅️ بازگشت", callback_data="favorites_back")]]
    await query.edit_message_text(text or "📗 موردی پیدا نشد.", reply_markup=InlineKeyboardMarkup(buttons))


async def favorites_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await favorites_command(update, context)
