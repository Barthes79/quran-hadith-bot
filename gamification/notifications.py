# -*- coding: utf-8 -*-
"""
پیام‌های کوتاه اطلاع‌رسانی برای رویدادهای گیمیفیکیشن (Level Up، تکمیل
مأموریت، باز شدن Achievement).

طراحی عمداً passive است: این فایل خودش پیام نمی‌فرستد، فقط بر اساس
خروجی dispatch_event یک متن کوتاه (یا None اگر چیزی برای گفتن نیست)
می‌سازد. هر handler که dispatch_event را صدا می‌زند، خودش تصمیم می‌گیرد
این متن را چطور و کجا نشان دهد (toast در query.answer، یا پیام جدا) —
این‌طوری هیچ‌کدام از handlerهای موجود مجبور به تغییر ساختار پیام اصلی‌شان
نمی‌شوند و نوتیفیکیشن کاملاً افزودنی (additive) باقی می‌ماند.
"""

from text_utils import to_persian_digits
from .config import get_level_title


def build_event_notification(result: dict) -> str | None:
    """از خروجی dispatch_event یک پیام کوتاه فارسی می‌سازد، یا None."""
    parts = []

    if result.get("leveled_up"):
        level = result["new_level"]
        parts.append(f"🎉 سطح جدید: {to_persian_digits(level)} — {get_level_title(level)}")

    for mission in result.get("completed_missions", []):
        parts.append(f"🎯 مأموریت «{mission['title']}» تکمیل شد! +{to_persian_digits(mission['xp_reward'])} XP")

    if not parts:
        return None
    return "\n".join(parts)
