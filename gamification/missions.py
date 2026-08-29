# -*- coding: utf-8 -*-
"""
موتور مأموریت‌های روزانه و هفتگی.

تعریف مأموریت‌ها در دیتابیس (جدول missions) نگه داشته می‌شود تا ادمین
بتواند بدون تغییر کد، مأموریت اضافه/غیرفعال کند (طبق نیازمندی «Admin
Panel»). این فایل فقط منطق عمومیِ محاسبه‌ی پیشرفت و تکمیل را دارد.

condition_type های پشتیبانی‌شده (باید دقیقاً با یکی از انواع رویداد در
gamification.config مطابقت داشته باشند):
    hadith_viewed, quran_viewed, nahj_viewed, mafatih_viewed, quiz_correct

منطق: هر بار dispatch_event برای یکی از این رویدادها اجرا و XP آن
awarded می‌شود، progress_missions() هم فراخوانی می‌شود تا پیشرفت
مأموریت‌های فعال (روزانه/هفتگی) کاربر برای آن نوع رویداد را یک واحد
جلو ببرد. توجه: پیشرفت مأموریت مستقل از موفقیت/شکست Anti-Abuse در خودِ
XP نیست — یعنی اگر آن رویداد به‌خاطر Anti-Abuse رد شده، پیشرفت مأموریت
هم افزایش پیدا نمی‌کند؛ این عمداً است تا مأموریت هم قابل exploit نباشد.
"""

import datetime

from database import get_connection
from .config import GAMIFICATION_TIMEZONE
from .db import _ensure_profile, increment_activity_counter


def _today_str() -> str:
    return datetime.datetime.now(GAMIFICATION_TIMEZONE).date().isoformat()


def _week_key() -> str:
    now = datetime.datetime.now(GAMIFICATION_TIMEZONE)
    iso = now.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _date_key_for(mission_type: str) -> str:
    return _today_str() if mission_type == "daily" else _week_key()


def seed_default_missions():
    """در صورت خالی بودن جدول missions، چند مأموریت پیش‌فرض می‌سازد.
    idempotent است (بر اساس UNIQUE بودن code)."""
    defaults = [
        # (code, type, title, condition_type, condition_value, xp_reward)
        ("daily_read_quran", "daily", "📖 یک محتوای قرآنی مطالعه کن", "quran_viewed", 1, 20),
        ("daily_read_hadith", "daily", "📚 دو حدیث بخوان", "hadith_viewed", 2, 20),
        ("daily_quiz", "daily", "🧠 یک پاسخ درست در آزمون بده", "quiz_correct", 1, 30),
        ("weekly_read_quran", "weekly", "📖 مطالعه ۲۰ محتوای قرآنی", "quran_viewed", 20, 60),
        ("weekly_read_hadith", "weekly", "📚 مطالعه ۱۵ حدیث", "hadith_viewed", 15, 60),
        ("weekly_quiz", "weekly", "🧠 ۱۰ پاسخ درست در آزمون", "quiz_correct", 10, 80),
    ]
    conn = get_connection()
    cur = conn.cursor()
    for code, mtype, title, cond_type, cond_value, xp in defaults:
        cur.execute(
            """INSERT OR IGNORE INTO missions
               (code, mission_type, title, condition_type, condition_value, xp_reward, active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (code, mtype, title, cond_type, cond_value, xp),
        )
    conn.commit()
    conn.close()


def _active_missions_for_condition(condition_type: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM missions WHERE active = 1 AND condition_type = ?",
        (condition_type,),
    ).fetchall()
    conn.close()
    return rows


def progress_missions(user_id: int, condition_type: str, amount: int = 1) -> list:
    """
    برای هر مأموریت فعال که condition_type اش با این رویداد مطابقت
    دارد، پیشرفت کاربر را amount واحد جلو می‌برد. اگر با این پیشرفت
    مأموریت تازه تکمیل شود، XP آن اضافه و در خروجی گزارش می‌شود.

    خروجی: لیستی از دیکشنری‌های مأموریت‌هایی که همین الان تکمیل شدند
    (برای نمایش پیام «مأموریت تکمیل شد» به کاربر).
    """
    # وارد کردن اینجا (نه بالای فایل) برای پرهیز از import چرخه‌ای با xp.py
    from .xp import grant_bonus_xp

    missions = _active_missions_for_condition(condition_type)
    if not missions:
        return []

    completed_now = []
    conn = get_connection()
    cur = conn.cursor()
    _ensure_profile(cur, user_id)

    for mission in missions:
        date_key = _date_key_for(mission["mission_type"])
        cur.execute(
            """INSERT OR IGNORE INTO user_missions (user_id, mission_id, date_key, progress, completed)
               VALUES (?, ?, ?, 0, 0)""",
            (user_id, mission["id"], date_key),
        )
        row = cur.execute(
            """SELECT progress, completed FROM user_missions
               WHERE user_id = ? AND mission_id = ? AND date_key = ?""",
            (user_id, mission["id"], date_key),
        ).fetchone()

        if row["completed"]:
            continue  # قبلاً تکمیل شده؛ چیزی برای انجام نیست

        new_progress = min(mission["condition_value"], row["progress"] + amount)
        just_completed = new_progress >= mission["condition_value"]

        cur.execute(
            """UPDATE user_missions SET progress = ?, completed = ?,
               completed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE completed_at END
               WHERE user_id = ? AND mission_id = ? AND date_key = ?""",
            (new_progress, 1 if just_completed else 0, just_completed,
             user_id, mission["id"], date_key),
        )

        if just_completed:
            completed_now.append(dict(mission))

    conn.commit()
    conn.close()

    # XP مأموریت‌های تکمیل‌شده را جداگانه (بعد از commit بالا) اعطا می‌کنیم
    # چون award_xp خودش یک اتصال دیتابیس مستقل باز می‌کند.
    for mission in completed_now:
        idempotency_key = f"mission:{user_id}:{mission['id']}:{_date_key_for(mission['mission_type'])}"
        result = grant_bonus_xp(user_id, mission["xp_reward"], "mission_complete",
                                 mission["code"], idempotency_key=idempotency_key)
        if result["awarded"]:
            increment_activity_counter(user_id, "total_missions_completed")

    return completed_now


def get_today_missions(user_id: int) -> dict:
    """مأموریت‌های روزانه و هفتگیِ فعلی کاربر را با پیشرفت برمی‌گرداند.
    برای نمایش در دستور «🎯 مأموریت‌ها» استفاده می‌شود."""
    conn = get_connection()
    result = {"daily": [], "weekly": []}
    for mission_type in ("daily", "weekly"):
        date_key = _date_key_for(mission_type)
        rows = conn.execute(
            """SELECT m.code, m.title, m.condition_value, m.xp_reward,
                      COALESCE(um.progress, 0) AS progress,
                      COALESCE(um.completed, 0) AS completed
               FROM missions m
               LEFT JOIN user_missions um
                 ON um.mission_id = m.id AND um.user_id = ? AND um.date_key = ?
               WHERE m.active = 1 AND m.mission_type = ?
               ORDER BY m.id""",
            (user_id, date_key, mission_type),
        ).fetchall()
        result[mission_type] = [dict(r) for r in rows]
    conn.close()
    return result
