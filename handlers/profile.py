from telegram import Update
from telegram.ext import ContextTypes
from database import register_user, get_user_stats


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username)
    stats = get_user_stats(user.id)

    text = (
        "👤 پروفایل شما\n\n"
        f"🆔 شناسه: {user.id}\n"
        f"⭐ علاقه‌مندی‌ها: {stats['favorites']}\n"
        f"🏆 امتیاز کوییز: {stats['score']}\n\n"
        "برای دیدن ذخیره‌های خود از دستور /favorites استفاده کنید ⭐"
    )

    await update.message.reply_text(text)
