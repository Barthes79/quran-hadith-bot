# -*- coding: utf-8 -*-
"""
موتور XP: نقطه‌ی واحد و امن برای دادن امتیاز داخلی (XP) بابت هر رویداد.

هر فراخوانی award_xp() این مراحل را طی می‌کند:
  ۱. بررسی Anti-Abuse (cooldown + سقف روزانه) — طبق ANTI_ABUSE_RULES
  ۲. ساخت idempotency_key و تلاش برای ثبت تراکنش (سطح دیتابیس هم از
     تکرار جلوگیری می‌کند؛ این دو لایه با هم race condition را هم پوشش
     می‌دهند، نه فقط چک ساده‌ی قبل از insert)
  ۳. تشخیص Level Up (در صورت رخ‌دادن)

یادآوری: XP فقط امتیاز داخلی سیستم است، نه ثواب شرعی.
"""

import time
import uuid
import datetime

from . import db
from .config import ANTI_ABUSE_RULES, XP_REWARDS, GAMIFICATION_TIMEZONE
from .levels import calculate_level


def _now_tehran() -> datetime.datetime:
    return datetime.datetime.now(GAMIFICATION_TIMEZONE)


def _check_anti_abuse(user_id: int, event_type: str, reference_id) -> tuple[bool, str]:
    """بررسی می‌کند آیا این رویداد مجاز به گرفتن XP است.
    خروجی: (مجاز است؟, دلیل رد در صورت رد شدن)"""
    rules = ANTI_ABUSE_RULES.get(event_type)
    if not rules:
        return True, ""

    now = _now_tehran()

    # کول‌داون
    cooldown = rules.get("cooldown_seconds", 0)
    if cooldown > 0:
        last = db.last_event_time(user_id, event_type, reference_id, rules.get("per_item_cooldown", False))
        if last:
            try:
                last_dt = datetime.datetime.fromisoformat(last)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=datetime.timezone.utc)
                elapsed = (datetime.datetime.now(datetime.timezone.utc) - last_dt.astimezone(datetime.timezone.utc)).total_seconds()
                if elapsed < cooldown:
                    return False, "cooldown"
            except (ValueError, TypeError):
                pass  # اگر فرمت تاریخ غیرمنتظره بود، رد نکن، اجازه بده سقف روزانه تصمیم بگیره

    # سقف روزانه
    daily_cap = rules.get("daily_cap")
    if daily_cap is not None:
        count = db.count_events_today(user_id, event_type, now.isoformat())
        if count >= daily_cap:
            return False, "daily_cap"

    return True, ""


def award_xp(user_id: int, event_type: str, reference_id=None,
             idempotency_key: str = None) -> dict:
    """
    XP بابت یک رویداد می‌دهد؛ اگر Anti-Abuse رد کند یا رویداد تکراری
    باشد، هیچ XP داده نمی‌شود.

    idempotency_key: اگر فراخواننده خودش کلید یکتا دارد (مثلاً شناسه‌ی
    آپدیت تلگرام) باید همان را بدهد تا حتی در صورت retry شدن کل درخواست
    (نه فقط کلیک مجدد کاربر) هم XP دوبار ثبت نشود. اگر داده نشود، یک
    کلید بر اساس user+event+reference+زمان (با دقت ثانیه) ساخته می‌شود
    که جلوی دو کلیک خیلی نزدیک به هم را می‌گیرد.

    خروجی:
        {"awarded": bool, "xp": int, "reason": str,
         "leveled_up": bool, "new_level": int|None}
    """
    xp_amount = XP_REWARDS.get(event_type, 0)
    if xp_amount <= 0:
        return {"awarded": False, "xp": 0, "reason": "no_reward_defined",
                "leveled_up": False, "new_level": None}

    allowed, reason = _check_anti_abuse(user_id, event_type, reference_id)
    if not allowed:
        return {"awarded": False, "xp": 0, "reason": reason,
                "leveled_up": False, "new_level": None}

    if not idempotency_key:
        idempotency_key = f"{user_id}:{event_type}:{reference_id}:{int(time.time())}"

    profile_before = db.get_profile(user_id)
    xp_before = profile_before["xp"] if profile_before else 0

    inserted = db.insert_xp_transaction(user_id, event_type, xp_amount, reference_id, idempotency_key)
    if not inserted:
        return {"awarded": False, "xp": 0, "reason": "duplicate_event",
                "leveled_up": False, "new_level": None}

    xp_after = xp_before + xp_amount
    level_before = calculate_level(xp_before)
    level_after = calculate_level(xp_after)

    leveled_up = level_after > level_before
    if leveled_up:
        db.set_level(user_id, level_after)

    return {
        "awarded": True,
        "xp": xp_amount,
        "reason": "ok",
        "leveled_up": leveled_up,
        "new_level": level_after if leveled_up else None,
    }


def grant_bonus_xp(user_id: int, xp_amount: int, event_type: str, reference_id: str,
                    idempotency_key: str) -> dict:
    """
    برای پاداش‌های یک‌بارمصرف (مثل XP دستاورد/مأموریت) که خودشان شرط
    unlock/تکمیل را دارند و نیازی به Anti-Abuse جداگانه ندارند. برخلاف
    award_xp، از ANTI_ABUSE_RULES رد نمی‌شود؛ ولی idempotency (سطح
    دیتابیس، از طریق UNIQUE روی idempotency_key) کاملاً رعایت می‌شود.
    """
    if xp_amount <= 0:
        return {"awarded": False, "xp": 0, "reason": "no_reward",
                "leveled_up": False, "new_level": None}

    profile_before = db.get_profile(user_id)
    xp_before = profile_before["xp"] if profile_before else 0

    inserted = db.insert_xp_transaction(user_id, event_type, xp_amount, reference_id, idempotency_key)
    if not inserted:
        return {"awarded": False, "xp": 0, "reason": "duplicate_event",
                "leveled_up": False, "new_level": None}

    xp_after = xp_before + xp_amount
    level_before = calculate_level(xp_before)
    level_after = calculate_level(xp_after)
    leveled_up = level_after > level_before
    if leveled_up:
        db.set_level(user_id, level_after)

    return {"awarded": True, "xp": xp_amount, "reason": "ok",
            "leveled_up": leveled_up, "new_level": level_after if leveled_up else None}
