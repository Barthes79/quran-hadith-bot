# -*- coding: utf-8 -*-
"""
Leaderboard: رتبه‌بندی جهانی، هفتگی، و (در آینده) گروهی.

برای نسخه‌ی اول، از کوئری مستقیم روی gamification_profile با ایندکس
روی ستون xp استفاده می‌شود (نه اسکن کامل جدول)؛ چون تعداد کاربران یک
ربات تلگرامی معمولاً در محدوده‌ای است که این کوئری با ایندکس سریع
می‌ماند. جدول leaderboard_snapshots برای آینده (اگر تعداد کاربران خیلی
زیاد شد) از قبل در schema آماده شده و می‌تواند بعداً با یک job دوره‌ای
پر شود، بدون تغییر در امضای توابع این فایل.
"""

from database import get_connection


def ensure_xp_index():
    """ایندکس روی ستون xp برای leaderboardهای سریع. idempotent."""
    conn = get_connection()
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gamification_profile_xp ON gamification_profile(xp DESC)")
    conn.commit()
    conn.close()


def get_global_leaderboard(limit: int = 10):
    conn = get_connection()
    rows = conn.execute(
        "SELECT user_id, xp, level FROM gamification_profile ORDER BY xp DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_weekly_leaderboard(limit: int = 10):
    """جمع XP کسب‌شده در ۷ روز اخیر، از روی xp_transactions (نه کل XP کاربر)."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT user_id, SUM(xp) AS xp
           FROM xp_transactions
           WHERE created_at >= datetime('now', '-7 days')
           GROUP BY user_id
           ORDER BY xp DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_global_rank(user_id: int) -> int | None:
    conn = get_connection()
    row = conn.execute(
        """SELECT COUNT(*) + 1 AS rank FROM gamification_profile
           WHERE xp > (SELECT xp FROM gamification_profile WHERE user_id = ?)""",
        (user_id,),
    ).fetchone()
    conn.close()
    return row["rank"] if row else None
