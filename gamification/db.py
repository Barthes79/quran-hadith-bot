# -*- coding: utf-8 -*-
"""
لایه‌ی دسترسی به دیتابیس برای گیمیفیکیشن.

عمداً از همان الگوی پروژه (sqlite3 خام، get_connection از database.py)
استفاده می‌شود تا سبک کد با بقیه‌ی پروژه یکدست بماند و وابستگی جدیدی
اضافه نشود.
"""

import datetime

from database import get_connection


def _ensure_profile(cur, user_id: int):
    """اگر پروفایل گیمیفیکیشن کاربر وجود نداشت، با مقادیر پیش‌فرض می‌سازد."""
    cur.execute(
        "INSERT OR IGNORE INTO gamification_profile (user_id) VALUES (?)",
        (user_id,),
    )


def get_profile(user_id: int) -> dict | None:
    conn = get_connection()
    cur = conn.cursor()
    _ensure_profile(cur, user_id)
    conn.commit()
    row = cur.execute(
        "SELECT * FROM gamification_profile WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def last_event_time(user_id: int, event_type: str, reference_id: str | None, per_item: bool):
    """آخرین زمانی که این کاربر برای این نوع رویداد (یا این آیتم مشخص،
    اگر per_item باشد) XP گرفته را برمی‌گرداند، یا None."""
    conn = get_connection()
    if per_item and reference_id is not None:
        row = conn.execute(
            """SELECT created_at FROM xp_transactions
               WHERE user_id = ? AND event_type = ? AND reference_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (user_id, event_type, str(reference_id)),
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT created_at FROM xp_transactions
               WHERE user_id = ? AND event_type = ?
               ORDER BY created_at DESC LIMIT 1""",
            (user_id, event_type),
        ).fetchone()
    conn.close()
    return row["created_at"] if row else None


def count_events_today(user_id: int, event_type: str, day_key: str) -> int:
    """تعداد رویدادهای این نوع که امروز (day_key) برای این کاربر XP داده‌اند."""
    conn = get_connection()
    row = conn.execute(
        """SELECT COUNT(*) AS c FROM xp_transactions
           WHERE user_id = ? AND event_type = ? AND date(created_at) = date(?)""",
        (user_id, event_type, day_key),
    ).fetchone()
    conn.close()
    return row["c"] if row else 0


def insert_xp_transaction(user_id: int, event_type: str, xp: int,
                           reference_id: str | None, idempotency_key: str) -> bool:
    """
    یک تراکنش XP ثبت می‌کند و XP کل پروفایل را atomic آپدیت می‌کند.
    اگر idempotency_key از قبل ثبت شده باشد (رویداد تکراری)، هیچ کاری
    نمی‌کند و False برمی‌گرداند.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        _ensure_profile(cur, user_id)
        cur.execute(
            """INSERT INTO xp_transactions (user_id, event_type, xp, reference_id, idempotency_key)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, event_type, xp, str(reference_id) if reference_id is not None else None,
             idempotency_key),
        )
        cur.execute(
            "UPDATE gamification_profile SET xp = xp + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (xp, user_id),
        )
        conn.commit()
        return True
    except Exception:
        # idempotency_key تکراری → UNIQUE constraint خطا می‌دهد؛ یعنی این
        # رویداد قبلاً ثبت شده، پس به‌درستی نادیده گرفته می‌شود.
        conn.rollback()
        return False
    finally:
        conn.close()


def set_level(user_id: int, level: int):
    conn = get_connection()
    conn.execute(
        "UPDATE gamification_profile SET level = ? WHERE user_id = ?",
        (level, user_id),
    )
    conn.commit()
    conn.close()


def update_streak(user_id: int, current_streak: int, longest_streak: int,
                   last_activity_date: str, first_activity_date: str = None):
    conn = get_connection()
    cur = conn.cursor()
    _ensure_profile(cur, user_id)
    if first_activity_date:
        cur.execute(
            """UPDATE gamification_profile
               SET current_streak = ?, longest_streak = ?, last_activity_date = ?,
                   first_activity_date = COALESCE(first_activity_date, ?)
               WHERE user_id = ?""",
            (current_streak, longest_streak, last_activity_date, first_activity_date, user_id),
        )
    else:
        cur.execute(
            """UPDATE gamification_profile
               SET current_streak = ?, longest_streak = ?, last_activity_date = ?
               WHERE user_id = ?""",
            (current_streak, longest_streak, last_activity_date, user_id),
        )
    conn.commit()
    conn.close()


def increment_activity_counter(user_id: int, column: str, amount: int = 1):
    """ستون‌های شمارنده‌ی total_hadith_read/total_quran_read/... را افزایش می‌دهد.
    نام ستون از یک لیست سفید داخلی گرفته می‌شود تا هیچ‌گاه ورودی خام کاربر
    مستقیم وارد SQL نشود."""
    allowed = {
        "total_hadith_read", "total_quran_read",
        "total_quiz_played", "total_missions_completed",
        "total_salavat_sent",
    }
    if column not in allowed:
        raise ValueError(f"ستون غیرمجاز: {column}")
    conn = get_connection()
    cur = conn.cursor()
    _ensure_profile(cur, user_id)
    cur.execute(
        f"UPDATE gamification_profile SET {column} = {column} + ? WHERE user_id = ?",
        (amount, user_id),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# شخصیت همراه: کبوتر 🕊️ (نام، سطح کلی، سوخت/دون، یخچال، پوینتِ آماده‌ی برداشت)
# ---------------------------------------------------------------------------

def get_pigeon_state(user_id: int) -> dict:
    """نام، سطح کلی، سوخت فعلی، یخچال، پوینتِ آماده‌ی برداشت، و آخرین
    زمان سینک تولیدِ کبوتر کاربر را برمی‌گرداند."""
    conn = get_connection()
    cur = conn.cursor()
    _ensure_profile(cur, user_id)
    conn.commit()
    row = cur.execute(
        """SELECT pigeon_name, pigeon_seed, nazri_fridge, pigeon_global_level,
                  pigeon_pending_points, pigeon_last_synced_at
           FROM gamification_profile WHERE user_id = ?""",
        (user_id,),
    ).fetchone()
    conn.close()
    if not row:
        return {
            "pigeon_name": None, "pigeon_seed": 0, "nazri_fridge": 0,
            "pigeon_global_level": 1, "pigeon_pending_points": 0,
            "pigeon_last_synced_at": None,
        }
    return dict(row)


def set_pigeon_name(user_id: int, name: str):
    conn = get_connection()
    cur = conn.cursor()
    _ensure_profile(cur, user_id)
    cur.execute(
        "UPDATE gamification_profile SET pigeon_name = ? WHERE user_id = ?",
        (name, user_id),
    )
    conn.commit()
    conn.close()


def add_to_fridge(user_id: int, amount: int):
    """مقدار داده‌شده (مثلاً «دونِ» یه آیتم نذری) رو به یخچال کاربر اضافه می‌کنه."""
    conn = get_connection()
    cur = conn.cursor()
    _ensure_profile(cur, user_id)
    cur.execute(
        "UPDATE gamification_profile SET nazri_fridge = nazri_fridge + ? WHERE user_id = ?",
        (amount, user_id),
    )
    conn.commit()
    conn.close()


def sync_pigeon_production(user_id: int, seed: float, fridge: int, pending: float, synced_at: str):
    """نتیجه‌ی محاسبه‌ی تولید passive رو (سوخت مصرف‌شده، یخچالِ خالی‌شده،
    پوینتِ اضافه‌شده به pending، و زمانِ سینک) یک‌جا ذخیره می‌کنه."""
    conn = get_connection()
    cur = conn.cursor()
    _ensure_profile(cur, user_id)
    cur.execute(
        """UPDATE gamification_profile
           SET pigeon_seed = ?, nazri_fridge = ?, pigeon_pending_points = ?,
               pigeon_last_synced_at = ?
           WHERE user_id = ?""",
        (seed, fridge, pending, synced_at, user_id),
    )
    conn.commit()
    conn.close()


def set_pigeon_pending(user_id: int, pending: float):
    """بعد از برداشت، باقی‌مانده‌ی اعشاریِ pending (بخشی که هنوز به
    عددِ صحیح نرسیده) رو ذخیره می‌کنه."""
    conn = get_connection()
    cur = conn.cursor()
    _ensure_profile(cur, user_id)
    cur.execute(
        "UPDATE gamification_profile SET pigeon_pending_points = ? WHERE user_id = ?",
        (pending, user_id),
    )
    conn.commit()
    conn.close()


def set_pigeon_level(user_id: int, level: int):
    conn = get_connection()
    cur = conn.cursor()
    _ensure_profile(cur, user_id)
    cur.execute(
        "UPDATE gamification_profile SET pigeon_global_level = ? WHERE user_id = ?",
        (level, user_id),
    )
    conn.commit()
    conn.close()


def spend_points(user_id: int, amount: int) -> bool:
    """
    اگه کیف‌پول (ستون xp) کافی باشه، amount رو ازش کم می‌کنه و True
    برمی‌گردونه؛ وگرنه بدون هیچ تغییری False. چک‌کردنِ موجودی و کم‌کردن
    هر دو تو یه تراکنش انجام می‌شه تا race condition (مثلاً دو تا خرید
    همزمان) باعث نشه موجودی منفی بشه.
    """
    if amount <= 0:
        return False
    conn = get_connection()
    cur = conn.cursor()
    try:
        _ensure_profile(cur, user_id)
        row = cur.execute(
            "SELECT xp FROM gamification_profile WHERE user_id = ?", (user_id,)
        ).fetchone()
        current = row["xp"] if row else 0
        if current < amount:
            conn.rollback()
            return False
        cur.execute(
            "UPDATE gamification_profile SET xp = xp - ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (amount, user_id),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()
