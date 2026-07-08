from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from database import get_favorites, get_hadith_by_id


async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_favorites(update.effective_user.id)
    if not rows:
        await update.message.reply_text("⭐ هنوز چیزی ذخیره نکرده‌اید.")
        return

    text = "⭐ علاقه‌مندی‌های شما:\n\n"
    count = 0

    for r in rows[:10]:
        if r["item_type"] == "hadith":
            hadith = get_hadith_by_id(int(r["item_ref"]))
            if hadith:
                count += 1
                text += (
                    f"📿 {hadith['arabic_text']}\n\n"
                    f"📖 ترجمه:\n{hadith['translation_text']}\n"
                )
                if hadith["tafsir_text"]:
                    text += f"\n📝 شرح:\n{hadith['tafsir_text']}\n"
                text += "\n────────────\n\n"
        else:
            text += f"📖 آیه: {r['item_ref']}\n\n────────────\n\n"

    if count == 0:
        text += "موردی برای نمایش وجود ندارد."

    await update.message.reply_text(text)


async def show_favorite_hadith(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    hadith_id = int(query.data.split("_")[-1])
    hadith = get_hadith_by_id(hadith_id)
    if not hadith:
        await query.edit_message_text("این حدیث پیدا نشد.")
        return

    text = (
        f"📿 حدیث ذخیره‌شده:\n\n"
        f"{hadith['arabic_text']}\n\n"
        f"📖 ترجمه:\n{hadith['translation_text']}"
    )
    if hadith['tafsir_text']:
        text += f"\n\n📝 شرح:\n{hadith['tafsir_text']}"

    await query.edit_message_text(text)
