# -*- coding: utf-8 -*-
"""
منطق شخصیت همراه: کبوتر 🕊️

سه رفتار اصلی:
  - «صلوات» در پیوی → صلوات پوینت با کول‌داون ۵ دقیقه (EVENT_SALAVAT_SENT)
  - «نذری» در پیوی → یه آیتم نذری رندوم با کول‌داون ۱ ساعته (EVENT_NAZRI_RECEIVED)،
    که هم XP می‌ده هم می‌ره تو یخچال کاربر
  - «کبوترم» → کارت وضعیت کبوتر (نام، دون، مقام، سطح) + دکمه‌ی تغذیه از یخچال

توجه: این ماژول فقط متن آماده برمی‌گرداند؛ ارسال پیام/دکمه به تلگرام در
handlers/pigeon.py انجام می‌شود تا لایه‌ی منطق از لایه‌ی تلگرام جدا بماند
(همون الگویی که gamification/profile.py و بقیه‌ی ماژول‌ها استفاده می‌کنند).
"""

import random

from . import db
from .xp import award_xp, award_variable_xp, seconds_until_next
from .levels import level_progress
from .config import (
    EVENT_SALAVAT_SENT, EVENT_NAZRI_RECEIVED,
    NAZRI_ITEMS, MAX_LEVEL, get_pigeon_rank, pigeon_seed_capacity,
)
from text_utils import to_persian_digits

DEFAULT_PIGEON_NAME = "کبوتر"


def _format_cooldown(seconds: int) -> str:
    """ثانیه را به شکل mm:ss با ارقام فارسی نمایش می‌دهد (مثلاً «۴:۵۵»)."""
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    secs_str = to_persian_digits(f"{secs:02d}")
    return f"{to_persian_digits(minutes)}:{secs_str}"


def handle_salavat_points(user_id: int) -> str:
    """پیام مربوط به کلمه‌ی «صلوات» در پیوی رو می‌سازه."""
    result = award_xp(user_id, EVENT_SALAVAT_SENT)

    if result["awarded"]:
        profile = db.get_profile(user_id)
        total = profile["xp"] if profile else result["xp"]
        remaining = seconds_until_next(user_id, EVENT_SALAVAT_SENT)
        total_str = to_persian_digits(f"{total:,}")
        lines = [
            "🕊️ اللهم صل علی محمد و آل محمد",
            "",
            f"🎉 {to_persian_digits(result['xp'])} صلوات پوینت گرفتی!",
            f"💰 صلوات پوینت‌هات: {total_str} 🪙",
            f"⏳ بعد از {_format_cooldown(remaining)} می‌تونی دوباره صلوات بفرستی.",
        ]
        if result["leveled_up"]:
            lines.append(f"\n🎊 تبریک! کبوترت رفت سطح {to_persian_digits(result['new_level'])}!")
        return "\n".join(lines)

    if result["reason"] == "cooldown":
        remaining = seconds_until_next(user_id, EVENT_SALAVAT_SENT)
        return f"⏳ صبر کن {_format_cooldown(remaining)} دیگه، بعد دوباره صلوات بفرست 🌹"

    if result["reason"] == "daily_cap":
        return "🌙 امروز به سقف صلوات پوینت رسیدی؛ فردا دوباره تلاش کن 🌹"

    return "🌹 صلوات قبول باشه."


def handle_nazri(user_id: int) -> str:
    """پیام مربوط به کلمه‌ی «نذری» رو می‌سازه: یه غذای رندوم + اضافه به یخچال."""
    item = random.choice(NAZRI_ITEMS)
    result = award_variable_xp(user_id, EVENT_NAZRI_RECEIVED, item["seed"])

    if not result["awarded"]:
        if result["reason"] == "cooldown":
            remaining = seconds_until_next(user_id, EVENT_NAZRI_RECEIVED)
            return f"⏳ هنوز نذری قبلی هضم نشده! {_format_cooldown(remaining)} دیگه صبر کن 😋"
        if result["reason"] == "daily_cap":
            return "🌙 امروز دیگه نذری‌ای نمونده؛ فردا دوباره سر بزن 🍛"
        return "🍛 نوش جان!"

    db.add_to_fridge(user_id, item["seed"])
    state = db.get_pigeon_state(user_id)

    lines = [
        f"{item['emoji']} یه پرس {item['name']} گیرت اومد!",
        f"🧊 گذاشتیمش تو یخچالت (الان {to_persian_digits(state['nazri_fridge'])} واحد نذری داری)",
        "🕊️ برای دادنش به کبوترت بنویس «کبوترم» و دکمه‌ی تغذیه رو بزن.",
    ]
    if result["leveled_up"]:
        lines.append(f"\n🎊 تبریک! کبوترت رفت سطح {to_persian_digits(result['new_level'])}!")
    return "\n".join(lines)


def set_pigeon_name(user_id: int, name: str) -> str:
    name = name.strip()[:30]
    if not name:
        return "⚠️ اسم نمی‌تونه خالی باشه."
    db.set_pigeon_name(user_id, name)
    return f"🕊️ از این به بعد کبوترت «{name}» صدا زده می‌شه."


def build_pigeon_status_text(user_id: int, display_name: str) -> str:
    """کارت وضعیت کبوتر رو می‌سازه: نام، دون، مقام، سطح، صلوات پوینت‌ها."""
    profile = db.get_profile(user_id)
    state = db.get_pigeon_state(user_id)
    xp = profile["xp"] if profile else 0
    progress = level_progress(xp)

    capacity = pigeon_seed_capacity(progress["level"])
    seed = min(state["pigeon_seed"], capacity)
    rank = get_pigeon_rank(progress["level"])
    pigeon_name = state["pigeon_name"] or DEFAULT_PIGEON_NAME

    if seed >= capacity:
        seed_status = "😋 سیره"
    elif seed >= capacity // 2:
        seed_status = "😐 نیمه‌گرسنه"
    else:
        seed_status = "😟 گرسنه‌ست"

    xp_str = to_persian_digits(f"{xp:,}")

    lines = [
        f"🕊️ کبوتر {display_name}",
        "",
        f"💕 نام: {pigeon_name}",
        f"🌾 دون: {seed_status} ({to_persian_digits(seed)} / {to_persian_digits(capacity)})",
        "",
        f"🌟 مقام: {rank}",
        f"⭐️ سطح: {to_persian_digits(progress['level'])} / {to_persian_digits(MAX_LEVEL)}",
        "",
        f"💰 صلوات پوینت‌ها: {xp_str} 🪙",
        f"🧊 نذری تو یخچال: {to_persian_digits(state['nazri_fridge'])} واحد",
    ]

    if not progress["is_max_level"]:
        next_level_xp = to_persian_digits(f"{progress['xp_for_next_level']:,}")
        lines.append(f"💰 امتیاز لازم برای سطح بعد: {next_level_xp}")
    else:
        lines.append("👑 کبوترت به بالاترین سطح رسیده!")

    return "\n".join(lines)


def feed_pigeon_from_fridge(user_id: int) -> str:
    """محتوای یخچال رو (تا سقف ظرفیتِ دون) به کبوتر می‌ده."""
    profile = db.get_profile(user_id)
    xp = profile["xp"] if profile else 0
    level = level_progress(xp)["level"]
    capacity = pigeon_seed_capacity(level)

    result = db.feed_pigeon(user_id, capacity)
    if result["fed"] <= 0:
        if result["remaining_fridge"] <= 0:
            return "🧊 یخچالت خالیه؛ اول با نوشتن «نذری» یه چیزی جمع کن."
        return "🌾 کبوترت الان سیره، بعداً بهش غذا بده."

    return (
        f"🕊️ {to_persian_digits(result['fed'])} واحد از یخچال به کبوترت دادی!\n"
        f"🌾 دون فعلی: {to_persian_digits(result['new_seed'])} / {to_persian_digits(capacity)}\n"
        f"🧊 نذری باقی‌مانده در یخچال: {to_persian_digits(result['remaining_fridge'])}"
    )
