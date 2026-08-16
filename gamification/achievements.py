# -*- coding: utf-8 -*-
"""
سیستم Achievement.

مشابه missions.py، تعریف‌ها در دیتابیس نگه داشته می‌شوند (قابل مدیریت
توسط ادمین). condition_type به یکی از ستون‌های شمارنده در
gamification_profile یا به current_streak/longest_streak اشاره می‌کند.
"""

from database import get_connection
from .db import get_profile


def seed_default_achievements():
    """دستاوردهای پیش‌فرض را می‌سازد (idempotent، بر اساس UNIQUE code)."""
    defaults = [
        # (code, name, description, icon, condition_type, condition_value, xp_reward, is_secret)
        ("quran_friend", "یار قرآن", "مطالعه ۱۰۰ محتوای قرآنی", "📖",
         "total_quran_read", 100, 50, 0),
        ("hadith_seeker", "جوینده حدیث", "مطالعه ۱۰۰ حدیث", "📚",
         "total_hadith_read", 100, 50, 0),
        ("curious_mind", "ذهن جستجوگر", "۱۰۰ پاسخ درست در آزمون", "🧠",
         "quiz_correct_total", 100, 50, 0),
        ("steadfast", "ثابت‌قدم", "۳۰ روز استمرار پیاپی", "🔥",
         "current_streak", 30, 60, 0),
        ("always_present", "همراه همیشگی", "۱۰۰ روز فعالیت (بهترین استمرار)", "🌙",
         "longest_streak", 100, 100, 0),
    ]
    conn = get_connection()
    cur = conn.cursor()
    for code, name, desc, icon, cond_type, cond_value, xp, secret in defaults:
        cur.execute(
            """INSERT OR IGNORE INTO achievements
               (code, name, description, icon, condition_type, condition_value, xp_reward, is_secret, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (code, name, desc, icon, cond_type, cond_value, xp, secret),
        )
    conn.commit()
    conn.close()


def _current_value(profile: dict, condition_type: str) -> int:
    if condition_type == "quiz_correct_total":
        # از quiz_user_stats می‌آید نه از gamification_profile؛ جدا محاسبه می‌شود
        return None
    return profile.get(condition_type, 0) or 0


def check_and_unlock_achievements(user_id: int) -> list:
    """دستاوردهایی که کاربر شرایطشان را دارد ولی هنوز باز نکرده، باز
    می‌کند. خروجی: لیست دستاوردهای تازه‌باز‌شده."""
    profile = get_profile(user_id)
    conn = get_connection()
    cur = conn.cursor()

    quiz_correct_total = cur.execute(
        "SELECT total_correct FROM quiz_user_stats WHERE user_id = ?", (user_id,)
    ).fetchone()
    quiz_correct_total = quiz_correct_total["total_correct"] if quiz_correct_total else 0

    achievements = cur.execute("SELECT * FROM achievements WHERE active = 1").fetchall()
    already = {
        row["achievement_id"] for row in
        cur.execute("SELECT achievement_id FROM user_achievements WHERE user_id = ?", (user_id,)).fetchall()
    }

    newly_unlocked = []
    for ach in achievements:
        if ach["id"] in already:
            continue
        if ach["condition_type"] == "quiz_correct_total":
            current = quiz_correct_total
        else:
            current = _current_value(profile, ach["condition_type"])
            if current is None:
                continue

        if current >= ach["condition_value"]:
            cur.execute(
                "INSERT OR IGNORE INTO user_achievements (user_id, achievement_id) VALUES (?, ?)",
                (user_id, ach["id"]),
            )
            newly_unlocked.append(dict(ach))

    conn.commit()
    conn.close()

    for ach in newly_unlocked:
        from .xp import grant_bonus_xp
        grant_bonus_xp(
            user_id, ach["xp_reward"], "achievement_unlock", ach["code"],
            idempotency_key=f"achievement_xp:{user_id}:{ach['code']}",
        )

    return newly_unlocked


def get_user_achievements(user_id: int) -> dict:
    conn = get_connection()
    unlocked = conn.execute(
        """SELECT a.code, a.name, a.description, a.icon, ua.unlocked_at
           FROM user_achievements ua JOIN achievements a ON a.id = ua.achievement_id
           WHERE ua.user_id = ? ORDER BY ua.unlocked_at DESC""",
        (user_id,),
    ).fetchall()
    locked = conn.execute(
        """SELECT a.code, a.name, a.description, a.icon FROM achievements a
           WHERE a.active = 1 AND a.is_secret = 0 AND a.id NOT IN
                 (SELECT achievement_id FROM user_achievements WHERE user_id = ?)""",
        (user_id,),
    ).fetchall()
    conn.close()
    return {"unlocked": [dict(r) for r in unlocked], "locked": [dict(r) for r in locked]}
