# -*- coding: utf-8 -*-
"""
لایه‌ی دسترسی به دیتابیس برای پنل ادمین گیمیفیکیشن.

عملیات CRUD روی missions/achievements + مشاهده‌ی XP و تراکنش‌های یک
کاربر خاص، بدون نیاز به تغییر کد (طبق نیازمندی «Admin Panel»).
"""

from database import get_connection
from .config import ANTI_ABUSE_RULES


def get_user_admin_summary(user_id: int) -> dict | None:
    """پروفایل کامل + ۱۰ تراکنش آخر XP یک کاربر، برای بازبینی توسط ادمین."""
    conn = get_connection()
    profile = conn.execute(
        "SELECT * FROM gamification_profile WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not profile:
        conn.close()
        return None
    transactions = conn.execute(
        """SELECT event_type, xp, reference_id, created_at FROM xp_transactions
           WHERE user_id = ? ORDER BY created_at DESC LIMIT 10""",
        (user_id,),
    ).fetchall()
    conn.close()
    return {"profile": dict(profile), "transactions": [dict(t) for t in transactions]}


# ---------------------------------------------------------------------------
# Missions CRUD
# ---------------------------------------------------------------------------

def list_missions() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM missions ORDER BY mission_type, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_mission(code: str, mission_type: str, title: str,
                    condition_type: str, condition_value: int, xp_reward: int) -> tuple[bool, str]:
    if mission_type not in ("daily", "weekly"):
        return False, "نوع مأموریت باید daily یا weekly باشد."
    if condition_type not in ANTI_ABUSE_RULES:
        valid = ", ".join(ANTI_ABUSE_RULES.keys())
        return False, f"condition_type نامعتبر است. مقادیر مجاز: {valid}"
    if condition_value <= 0 or xp_reward < 0:
        return False, "condition_value باید مثبت و xp_reward نامنفی باشد."

    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO missions (code, mission_type, title, condition_type, condition_value, xp_reward, active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (code, mission_type, title, condition_type, condition_value, xp_reward),
        )
        conn.commit()
        return True, "مأموریت ساخته شد."
    except Exception as e:
        return False, f"خطا (احتمالاً code تکراری است): {e}"
    finally:
        conn.close()


def set_mission_active(code: str, active: bool) -> bool:
    conn = get_connection()
    cur = conn.execute("UPDATE missions SET active = ? WHERE code = ?", (1 if active else 0, code))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


# ---------------------------------------------------------------------------
# Achievements CRUD
# ---------------------------------------------------------------------------

def list_achievements() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM achievements ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_achievement(code: str, name: str, description: str, icon: str,
                        condition_type: str, condition_value: int, xp_reward: int,
                        is_secret: bool = False) -> tuple[bool, str]:
    if condition_value <= 0 or xp_reward < 0:
        return False, "condition_value باید مثبت و xp_reward نامنفی باشد."

    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO achievements
               (code, name, description, icon, condition_type, condition_value, xp_reward, is_secret, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (code, name, description, icon, condition_type, condition_value, xp_reward, 1 if is_secret else 0),
        )
        conn.commit()
        return True, "دستاورد ساخته شد."
    except Exception as e:
        return False, f"خطا (احتمالاً code تکراری است): {e}"
    finally:
        conn.close()


def set_achievement_active(code: str, active: bool) -> bool:
    conn = get_connection()
    cur = conn.execute("UPDATE achievements SET active = ? WHERE code = ?", (1 if active else 0, code))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


# ---------------------------------------------------------------------------
# Abuse monitoring (نمای ساده‌ی رویدادهای رد‌شده به‌خاطر Anti-Abuse نداریم
# چون رد شدن‌ها اصلاً در xp_transactions ثبت نمی‌شوند - این خودش به‌قصد است
# تا آن جدول فقط حاوی XPهای واقعاً اعطاشده باشد. برای مانیتورینگ سطح بالاتر
# می‌توان تعداد پیام‌های هر کاربر در بازه‌ی زمانی کوتاه را بررسی کرد.)
# ---------------------------------------------------------------------------

def get_top_xp_earners_today(limit: int = 10) -> list:
    """کاربرانی که امروز بیشترین XP را گرفته‌اند؛ برای رصد سریع رفتار غیرعادی."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT user_id, SUM(xp) AS xp_today, COUNT(*) AS events_today
           FROM xp_transactions
           WHERE date(created_at) = date('now')
           GROUP BY user_id
           ORDER BY xp_today DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
