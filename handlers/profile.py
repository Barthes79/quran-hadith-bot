from telegram import Update
from telegram.ext import ContextTypes
from database import register_user, get_user_stats
from gamification.profile import build_profile_text


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username)
    stats = get_user_stats(user.id)

    text = (
        build_profile_text(user.id)
        + "\n\n"
        + f"⭐ علاقه‌مندی‌ها: {stats['favorites']}\n"
        + f"🎮 امتیاز آزمون: {stats['score']}\n\n"
        + "برای دیدن ذخیره‌های خود از دستور /favorites استفاده کنید ⭐"
    )

    await update.message.reply_text(text)
