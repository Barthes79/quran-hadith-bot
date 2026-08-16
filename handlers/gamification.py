# -*- coding: utf-8 -*-
"""هندلرهای نمایش مأموریت‌ها، دستاوردها و رتبه‌بندی."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import register_user
from text_utils import to_persian_digits
from gamification.missions import get_today_missions
from gamification.achievements import check_and_unlock_achievements, get_user_achievements
from gamification.leaderboard import get_global_leaderboard, get_weekly_leaderboard, get_user_global_rank


def _back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 بازگشت به خانه", callback_data="menu_main")]])


def _missions_text(user_id: int) -> str:
    data = get_today_missions(user_id)
    lines = ["🎯 مأموریت‌های امروز", ""]

    if not data["daily"]:
        lines.append("فعلاً مأموریتی تعریف نشده.")
    for m in data["daily"]:
        mark = "✅" if m["completed"] else "▫️"
        lines.append(
            f"{mark} {m['title']} "
            f"({to_persian_digits(m['progress'])}/{to_persian_digits(m['condition_value'])}) "
            f"+{to_persian_digits(m['xp_reward'])} XP"
        )

    lines += ["", "📅 مأموریت‌های این هفته", ""]
    for m in data["weekly"]:
        mark = "✅" if m["completed"] else "▫️"
        lines.append(
            f"{mark} {m['title']} "
            f"({to_persian_digits(m['progress'])}/{to_persian_digits(m['condition_value'])}) "
            f"+{to_persian_digits(m['xp_reward'])} XP"
        )

    return "\n".join(lines)


async def missions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username)
    await update.message.reply_text(_missions_text(user.id), reply_markup=_back_keyboard())


async def missions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await query.edit_message_text(_missions_text(user_id), reply_markup=_back_keyboard())


def _achievements_text(user_id: int) -> str:
    check_and_unlock_achievements(user_id)  # به‌روزرسانی قبل از نمایش
    data = get_user_achievements(user_id)

    lines = [f"🏅 دستاوردهای من ({to_persian_digits(len(data['unlocked']))})", ""]
    if data["unlocked"]:
        for a in data["unlocked"]:
            lines.append(f"{a['icon']} {a['name']} — {a['description']}")
    else:
        lines.append("هنوز دستاوردی باز نکرده‌اید.")

    if data["locked"]:
        lines += ["", "🔒 دستاوردهای در انتظار", ""]
        for a in data["locked"]:
            lines.append(f"▫️ {a['name']} — {a['description']}")

    return "\n".join(lines)


async def achievements_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username)
    await update.message.reply_text(_achievements_text(user.id), reply_markup=_back_keyboard())


async def achievements_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await query.edit_message_text(_achievements_text(user_id), reply_markup=_back_keyboard())


_MEDALS = {0: "🥇", 1: "🥈", 2: "🥉"}


def _leaderboard_text(user_id: int) -> str:
    global_top = get_global_leaderboard(10)
    weekly_top = get_weekly_leaderboard(10)
    rank = get_user_global_rank(user_id)

    lines = ["🏆 رتبه‌بندی جهانی", ""]
    for i, row in enumerate(global_top):
        prefix = _MEDALS.get(i, f"{to_persian_digits(i + 1)}.")
        lines.append(f"{prefix} کاربر {row['user_id']} — {to_persian_digits(row['xp'])} XP")

    lines += ["", "📅 برترین‌های این هفته", ""]
    if weekly_top:
        for i, row in enumerate(weekly_top):
            prefix = _MEDALS.get(i, f"{to_persian_digits(i + 1)}.")
            lines.append(f"{prefix} کاربر {row['user_id']} — {to_persian_digits(row['xp'])} XP")
    else:
        lines.append("هنوز فعالیتی در این هفته ثبت نشده.")

    if rank:
        lines += ["", f"📍 رتبه‌ی شما در جدول جهانی: #{to_persian_digits(rank)}"]

    return "\n".join(lines)


async def leaderboard_gamification_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username)
    await update.message.reply_text(_leaderboard_text(user.id), reply_markup=_back_keyboard())


async def leaderboard_gamification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await query.edit_message_text(_leaderboard_text(user_id), reply_markup=_back_keyboard())
