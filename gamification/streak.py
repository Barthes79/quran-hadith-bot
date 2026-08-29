# -*- coding: utf-8 -*-
"""
سیستم Streak روزانه.

بر اساس تاریخ (نه ساعت دقیق) در منطقه‌ی زمانی GAMIFICATION_TIMEZONE
محاسبه می‌شود. فراخوانی چندباره‌ی touch_daily_streak() در یک روز، فقط
بار اول streak را افزایش می‌دهد؛ بارهای بعدی هیچ تغییری نمی‌دهند
(idempotent نسبت به «روز»).
"""

import datetime

from . import db
from .config import GAMIFICATION_TIMEZONE


def _today_str() -> str:
    return datetime.datetime.now(GAMIFICATION_TIMEZONE).date().isoformat()


def touch_daily_streak(user_id: int) -> dict:
    """
    باید یک‌بار در روز، در اولین فعالیت کاربر، فراخوانی شود (مثلاً از
    داخل رویداد USER_DAILY_LOGIN). خروجی:
        {"changed": bool, "current_streak": int, "longest_streak": int,
         "is_new_record": bool}
    """
    today = _today_str()
    profile = db.get_profile(user_id)
    last_date = profile.get("last_activity_date")
    current = profile.get("current_streak") or 0
    longest = profile.get("longest_streak") or 0

    if last_date == today:
        # امروز قبلاً ثبت شده؛ کاری نکن
        return {"changed": False, "current_streak": current,
                "longest_streak": longest, "is_new_record": False}

    if last_date:
        try:
            last_dt = datetime.date.fromisoformat(last_date)
            today_dt = datetime.date.fromisoformat(today)
            gap_days = (today_dt - last_dt).days
        except ValueError:
            gap_days = None
    else:
        gap_days = None

    if gap_days == 1:
        new_streak = current + 1
    else:
        # روز اول فعالیت، یا یک یا چند روز از دست رفته → streak از نو
        new_streak = 1

    new_longest = max(longest, new_streak)
    is_new_record = new_longest > longest

    db.update_streak(
        user_id=user_id,
        current_streak=new_streak,
        longest_streak=new_longest,
        last_activity_date=today,
        first_activity_date=today,
    )

    return {"changed": True, "current_streak": new_streak,
            "longest_streak": new_longest, "is_new_record": is_new_record}
