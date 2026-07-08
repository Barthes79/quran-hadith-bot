from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_favorites, get_hadith_by_id


async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("📿 احادیث", callback_data="favorites_hadith")],
        [InlineKeyboardButton("📖 قرآن", callback_data="favorites_quran")],
    ]
    await update.message.reply_text(
        "⭐ علاقه‌مندی‌ها\n\nدسته مورد نظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(buttons),
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
            text += (
                f"📿 {hadith['arabic_text']}\n\n"
                f"📖 ترجمه:\n{hadith['translation_text']}\n"
            )
            if hadith["tafsir_text"]:
                text += f"\n📝 شرح:\n{hadith['tafsir_text']}\n"
            text += "\n────────────\n\n"

    await query.edit_message_text(text or "📿 موردی پیدا نشد.")


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
        text += f"📖 آیه: {r['item_ref']}\n\n────────────\n\n"

    await query.edit_message_text(text)
