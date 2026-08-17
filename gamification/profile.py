# -*- coding: utf-8 -*-
"""ساخت متن پروفایل گیمیفیکیشن کاربر."""

from . import db
from .levels import level_progress
from text_utils import to_persian_digits


def _progress_bar(percent: int, width: int = 10) -> str:
    filled = round(width * percent / 100)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def build_profile_text(user_id: int) -> str:
    profile = db.get_profile(user_id)
    progress = level_progress(profile["xp"])

    bar = _progress_bar(progress["percent"])

    lines = [
        "👤 پروفایل من",
        "",
        f"🏅 سطح {to_persian_digits(progress['level'])} — {progress['title']}",
        f"⭐ {to_persian_digits(progress['xp'])} XP",
        "",
        f"{bar} {to_persian_digits(progress['percent'])}٪",
    ]

    if not progress["is_max_level"]:
        lines.append(f"({to_persian_digits(progress['xp_for_next_level'])} XP تا سطح بعد)")

    lines += [
        "",
        f"🔥 استمرار: {to_persian_digits(profile['current_streak'])} روز",
        f"🏆 بهترین استمرار: {to_persian_digits(profile['longest_streak'])} روز",
        "",
        f"📖 قرآن: {to_persian_digits(profile['total_quran_read'])}",
        f"📚 حدیث: {to_persian_digits(profile['total_hadith_read'])}",
        f"🧠 آزمون: {to_persian_digits(profile['total_quiz_played'])}",
        f"🌹 صلوات‌های XP‌دار: {to_persian_digits(profile['total_salavat_sent'])} (برای مجموع واقعی صلوات از /salavat استفاده کنید)",
        f"🎯 مأموریت‌های تکمیل‌شده: {to_persian_digits(profile['total_missions_completed'])}",
    ]

    return "\n".join(lines)
