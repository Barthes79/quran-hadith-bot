# -*- coding: utf-8 -*-
"""
نقطه‌ی ورودی واحد برای اعلام رویدادهای گیمیفیکیشن از داخل handlerهای
موجود ربات.

استفاده در هر handler موجود، فقط با اضافه‌کردن یک خط (بدون تغییر منطق
فعلی آن handler):

    from gamification.events import dispatch_event
    from gamification.config import EVENT_HADITH_VIEWED

    await dispatch_event(EVENT_HADITH_VIEWED, user_id, reference_id=hadith_id)

این تابع خودش تصمیم می‌گیرد XP بدهد یا نه (بر اساس Anti-Abuse)، شمارنده‌ی
فعالیت مربوطه را افزایش می‌دهد، و برای رویداد ورود روزانه، streak را هم
لمس می‌کند. تمام این کار async-safe نیست به این معنا که خودِ عملیات
دیتابیس sync است (هماهنگ با سبک فعلی database.py که همه‌جا sync است)؛
اما تابع را async تعریف کرده‌ایم تا در آینده اگر لازم شد به‌سادگی به
executor جداگانه منتقل شود بدون تغییر امضای فراخوانی در handlerها.
"""

from . import db
from .xp import award_xp
from .streak import touch_daily_streak
from .missions import progress_missions
from .config import (
    EVENT_DAILY_LOGIN, EVENT_HADITH_VIEWED, EVENT_QURAN_VIEWED,
    EVENT_NAHJ_VIEWED, EVENT_MAFATIH_VIEWED, EVENT_QUIZ_STARTED,
    EVENT_QUIZ_CORRECT, EVENT_MISSION_COMPLETE, EVENT_SALAVAT_SENT,
)

# نگاشت هر نوع رویداد به ستون شمارنده‌ی فعالیتِ مربوطه در gamification_profile
_ACTIVITY_COUNTERS = {
    EVENT_HADITH_VIEWED: "total_hadith_read",
    EVENT_QURAN_VIEWED: "total_quran_read",
    EVENT_QUIZ_STARTED: "total_quiz_played",
    EVENT_MISSION_COMPLETE: "total_missions_completed",
    EVENT_SALAVAT_SENT: "total_salavat_sent",
}

# رویدادهایی که می‌توانند پیشرفت مأموریت (daily/weekly) را جلو ببرند.
# condition_type در جدول missions باید دقیقاً یکی از این مقادیر باشد.
_MISSION_TRACKED_EVENTS = {
    EVENT_HADITH_VIEWED, EVENT_QURAN_VIEWED, EVENT_NAHJ_VIEWED,
    EVENT_MAFATIH_VIEWED, EVENT_QUIZ_CORRECT,
}


async def dispatch_event(event_type: str, user_id: int, reference_id=None,
                          idempotency_key: str = None) -> dict:
    """
    رویداد را پردازش می‌کند: XP می‌دهد (اگر مجاز باشد)، شمارنده‌ی فعالیت
    را افزایش می‌دهد، در صورت لزوم streak را لمس می‌کند، و پیشرفت
    مأموریت‌های مرتبط را جلو می‌برد.

    خروجی همان دیکشنری award_xp است به‌علاوه‌ی کلید "completed_missions"
    (لیست مأموریت‌هایی که همین الان تکمیل شدند) تا handler فراخواننده در
    صورت تمایل بتواند به کاربر پیام «سطح جدید» یا «مأموریت تکمیل شد»
    نشان دهد.
    """
    result = award_xp(user_id, event_type, reference_id=reference_id,
                       idempotency_key=idempotency_key)

    result["completed_missions"] = []

    if result["awarded"]:
        counter_col = _ACTIVITY_COUNTERS.get(event_type)
        if counter_col:
            db.increment_activity_counter(user_id, counter_col)

        if event_type in _MISSION_TRACKED_EVENTS:
            result["completed_missions"] = progress_missions(user_id, event_type)

    if event_type == EVENT_DAILY_LOGIN:
        touch_daily_streak(user_id)

    return result
