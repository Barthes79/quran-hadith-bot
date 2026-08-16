# -*- coding: utf-8 -*-
"""
محاسبه‌ی Level بر اساس XP.

سه مدل قبل از انتخاب فرمول نهایی مقایسه شدند:

۱) خطی (XP_required = base * level):
   ساده، اما در سطوح بالا (مثلاً سطح ۸۰ به ۸۱) تفاوتی با سطوح پایین
   (سطح ۱ به ۲) ندارد؛ باعث می‌شود پیشرفت در سطوح بالا هیجان‌انگیز نباشد.

۲) توانی با پایه‌ی ثابت (XP_required = base^level):
   خیلی زود (حدود سطح ۱۵-۲۰) به اعداد غیرقابل‌دسترس در دنیای واقعی می‌رسد؛
   برای یک ربات مذهبی با استفاده‌ی روزانه، این باعث ناامیدی کاربر می‌شود.

۳) توان ۱.۵ (XP_required = base * level^1.5)  ← انتخاب نهایی
   رشد نه خیلی کند (خطی) و نه خیلی تند (توانی)؛ سطوح اولیه سریع باز
   می‌شوند (انگیزه‌ی شروع) و سطوح بالاتر به‌تدریج سخت‌تر می‌شوند (حس
   دستاورد واقعی)، بدون اینکه به مرزهای غیرمنطقی برسد.
"""

from .config import LEVEL_BASE_XP, LEVEL_EXPONENT, MAX_LEVEL, get_level_title


def xp_required_for_level(level: int) -> int:
    """حداقل XP کل لازم برای رسیدن به این level (level=1 همیشه صفر است)."""
    if level <= 1:
        return 0
    return int(LEVEL_BASE_XP * (level ** LEVEL_EXPONENT))


def calculate_level(total_xp: int) -> int:
    """بر اساس XP کل، شماره‌ی level فعلی را برمی‌گرداند."""
    level = 1
    while level < MAX_LEVEL and total_xp >= xp_required_for_level(level + 1):
        level += 1
    return level


def level_progress(total_xp: int) -> dict:
    """
    اطلاعات کامل پیشرفت کاربر در level فعلی‌اش را برمی‌گرداند: مناسب
    برای رسم progress bar در پروفایل.
    """
    level = calculate_level(total_xp)
    current_floor = xp_required_for_level(level)
    next_floor = xp_required_for_level(level + 1) if level < MAX_LEVEL else current_floor

    span = next_floor - current_floor
    into_level = total_xp - current_floor
    percent = 100 if span <= 0 else min(100, int(into_level * 100 / span))

    return {
        "level": level,
        "title": get_level_title(level),
        "xp": total_xp,
        "xp_into_level": max(0, into_level),
        "xp_for_next_level": max(0, next_floor - total_xp),
        "level_span_xp": span,
        "percent": percent,
        "is_max_level": level >= MAX_LEVEL,
    }
