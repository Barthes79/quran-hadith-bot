# -*- coding: utf-8 -*-
"""
منطق شخصیت همراه: کبوتر 🕊️

... (بقیه‌ی توضیحات مثل قبل)
"""

import random
import datetime

from . import db
from .xp import award_variable_xp, grant_bonus_xp, seconds_until_next
from .config import (
    EVENT_SALAVAT_SENT, EVENT_PIGEON_HARVEST,
    SALAVAT_POINT_MIN, SALAVAT_POINT_MAX,
    PIGEON_RANK_STAGES, PIGEON_FUEL_SECONDS_PER_UNIT, PIGEON_MAX_FEATURE_LEVEL,
    pigeon_fuel_capacity, pigeon_stage_info, pigeon_level_up_cost, pigeon_production_rate,
    pigeon_feature_level_for_count, pigeon_count_for_next_feature_level,
    fridge_capacity,
)
from text_utils import to_persian_digits, normalize_for_search

DEFAULT_PIGEON_NAME = "کبوتر"

PIGEON_RENAME_COST = 114

_SALAVAT_PHRASE_NORMALIZED = normalize_for_search("اللهم صل علی محمد و آل محمد")


def is_full_salavat_phrase(text: str) -> bool:
    return normalize_for_search(text) == _SALAVAT_PHRASE_NORMALIZED


def _format_cooldown(seconds: int) -> str:
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    secs_str = to_persian_digits(f"{secs:02d}")
    return f"{to_persian_digits(minutes)}:{secs_str}"


def _code(value) -> str:
    return f"`{value}`"


def _fmt_rate(rate: float) -> str:
    return to_persian_digits(f"{rate:g}")


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _parse_dt(value):
    if not value:
        return None
    try:
        dt = datetime.datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    except (ValueError, TypeError):
        return None


def roll_salavat_points() -> int:
    return random.randint(SALAVAT_POINT_MIN, SALAVAT_POINT_MAX)


def _sync_production(user_id: int) -> dict:
    state = db.get_pigeon_state(user_id)
    now = _now()
    last = _parse_dt(state.get("pigeon_last_synced_at")) or now
    elapsed = max(0.0, (now - last).total_seconds())

    global_level = state["pigeon_global_level"] or 1
    stage = pigeon_stage_info(global_level)
    seed = float(state["pigeon_seed"] or 0)
    pending = float(state["pigeon_pending_points"] or 0)

    capacity = pigeon_fuel_capacity(global_level)

    if elapsed > 0 and seed > 0:
        rate = pigeon_production_rate(stage["sub_level"])
        fuel_seconds = seed * PIGEON_FUEL_SECONDS_PER_UNIT
        active_seconds = min(elapsed, fuel_seconds)
        produced = rate * active_seconds
        seed_used = active_seconds / PIGEON_FUEL_SECONDS_PER_UNIT
        seed = max(0.0, seed - seed_used)
        pending += produced

    db.update_pigeon_seed_and_pending(user_id, seed=seed, pending=pending, synced_at=now.isoformat())

    return {
        "global_level": global_level,
        "stage": stage,
        "seed": seed,
        "pending": pending,
        "capacity": capacity,
    }


def add_seed_to_pigeon(user_id: int, amount: float) -> dict:
    synced = _sync_production(user_id)
    new_seed = min(synced["capacity"], synced["seed"] + amount)
    db.update_pigeon_seed_and_pending(
        user_id, seed=new_seed, pending=synced["pending"], synced_at=_now().isoformat()
    )
    return {"new_seed": new_seed, "capacity": synced["capacity"]}


def get_pigeon_name(user_id: int) -> str:
    state = db.get_pigeon_state(user_id)
    return state.get("pigeon_name") or DEFAULT_PIGEON_NAME


def get_pigeon_feature_level(user_id: int) -> int:
    """سطح فعلی «پیشرفت قابلیت‌ها» رو برمی‌گردونه (۱ تا ۸)."""
    state = db.get_pigeon_state(user_id)
    count = state.get("pigeon_salavat_count") or 0
    return pigeon_feature_level_for_count(count)


def get_pigeon_feature_progress(user_id: int) -> dict:
    """
    اطلاعات کامل پیشرفت قابلیت‌ها رو برمی‌گردونه:
      - count: تعداد صلوات کامل گفته‌شده
      - level: سطح فعلی
      - next_threshold: آستانه‌ی سطح بعد (یا None اگه به سقف رسیده)
      - remaining: تعداد صلوات باقی‌مونده تا سطح بعد (برای سطح ۳، باقی‌مونده تا ۷۰)
    """
    state = db.get_pigeon_state(user_id)
    count = state.get("pigeon_salavat_count") or 0
    current_level = pigeon_feature_level_for_count(count)
    next_threshold = pigeon_count_for_next_feature_level(current_level)
    return {
        "count": count,
        "level": current_level,
        "next_threshold": next_threshold,
        "remaining": next_threshold - count if next_threshold is not None else 0,
    }


def register_pigeon_feature_progress(user_id: int) -> dict:
    new_count = db.increment_pigeon_salavat_count(user_id, 1)
    old_level = pigeon_feature_level_for_count(new_count - 1)
    new_level = pigeon_feature_level_for_count(new_count)
    return {
        "count": new_count,
        "old_level": old_level,
        "new_level": new_level,
        "leveled_up": new_level > old_level,
    }


def _pigeon_feature_levelup_line(level_result: dict) -> str:
    return (
        f"🔓 پیشرفتِ قابلیت‌هات رفت سطح {_code(to_persian_digits(level_result['new_level']))}! "
        f"(قابلیت‌های هر سطح به‌زودی اضافه می‌شن)"
    )


def _build_salavat_card(user_id: int, result: dict, feature_progress_result: dict | None = None) -> str:
    leveled_up_line = None
    if feature_progress_result and feature_progress_result.get("leveled_up"):
        leveled_up_line = _pigeon_feature_levelup_line(feature_progress_result)

    if result["awarded"]:
        profile = db.get_profile(user_id)
        total = profile["xp"] if profile else result["xp"]
        remaining = seconds_until_next(user_id, EVENT_SALAVAT_SENT)
        total_str = to_persian_digits(f"{total:,}")
        lines = [
            f"🎉 {_code(to_persian_digits(result['xp']))} صلوات پوینت گرفتی!",
            f"💰 صلوات پوینت‌هات: {_code(total_str)} 🪙",
            f"⏳ بعد از {_code(_format_cooldown(remaining))} می‌تونی دوباره صلوات پوینت بگیری.",
        ]
        if result["leveled_up"]:
            lines.append(f"🌟 سطح کلیِ حسابت هم رفت {_code(to_persian_digits(result['new_level']))}!")
        if leveled_up_line:
            lines.append(leveled_up_line)
        return "\n".join(lines)

    if result["reason"] == "cooldown":
        remaining = seconds_until_next(user_id, EVENT_SALAVAT_SENT)
        base = f"⏳ صلوات پوینتِ بعدیت {_code(_format_cooldown(remaining))} دیگه آماده می‌شه 🌹"
        return f"{base}\n\n{leveled_up_line}" if leveled_up_line else base

    if result["reason"] == "daily_cap":
        base = "🌙 امروز به سقف صلوات پوینت رسیدی؛ فردا دوباره تلاش کن 🌹"
        return f"{base}\n\n{leveled_up_line}" if leveled_up_line else base

    base = "🌹 صلوات قبول باشه."
    return f"{base}\n\n{leveled_up_line}" if leveled_up_line else base


def build_salavat_card_from_dispatch(user_id: int, dispatch_result: dict) -> str:
    progress_result = register_pigeon_feature_progress(user_id)
    return _build_salavat_card(user_id, dispatch_result, progress_result)


def handle_salavat_points(user_id: int) -> str:
    result = award_variable_xp(user_id, EVENT_SALAVAT_SENT, roll_salavat_points())
    progress_result = register_pigeon_feature_progress(user_id)
    return _build_salavat_card(user_id, result, progress_result)


def _is_valid_pigeon_name(name: str) -> bool:
    name = name.strip()
    if not (3 <= len(name) <= 22):
        return False
    if "  " in name:
        return False
    return all(ch.isalpha() for ch in name if ch != " ")


def set_pigeon_name(user_id: int, name: str) -> str:
    name = name.strip()
    if not _is_valid_pigeon_name(name):
        return (
            "⚠️ اسم باید بینِ ۳ تا ۲۲ کاراکتر و فقط از حروف و فاصله تشکیل شده باشه "
            "(بدون عدد، ایموجی، یا علامتِ نگارشی)."
        )

    profile = db.get_profile(user_id)
    wallet = profile["xp"] if profile else 0
    if wallet < PIGEON_RENAME_COST:
        missing = PIGEON_RENAME_COST - wallet
        return (
            f"💰 برای تغییرِ اسم به {_code(to_persian_digits(PIGEON_RENAME_COST))} صلوات پوینت نیاز داری.\n"
            f"هنوز {_code(to_persian_digits(missing))} پوینت کم داری."
        )

    if not db.spend_points(user_id, PIGEON_RENAME_COST):
        return "⚠️ مشکلی پیش اومد (شاید موجودیت تغییر کرده)، دوباره امتحان کن."

    db.set_pigeon_name(user_id, name)
    return f"🕊️ از این به بعد کبوترت «{name}» صدا زده می‌شه."


def build_pigeon_status_text(user_id: int, display_name: str) -> str:
    synced = _sync_production(user_id)
    profile = db.get_profile(user_id)
    state = db.get_pigeon_state(user_id)

    wallet = profile["xp"] if profile else 0
    global_level = synced["global_level"]
    stage = synced["stage"]
    rate = pigeon_production_rate(stage["sub_level"])
    capacity = synced["capacity"]
    seed = synced["seed"]
    pending = synced["pending"]
    pigeon_name = state["pigeon_name"] or DEFAULT_PIGEON_NAME
    salavat_count = state.get("pigeon_salavat_count") or 0

    fridge_level = db.get_fridge_level(user_id)
    fridge_count = db.count_fridge_items(user_id)
    fridge_cap = fridge_capacity(fridge_level)

    if seed >= capacity:
        seed_status = "😋 سیر"
    elif seed >= capacity / 2:
        seed_status = "😐 نیمه‌سیر"
    else:
        seed_status = "😟 گرسنه"

    at_cap = stage["sub_level"] >= stage["cap"]
    if at_cap and not stage["is_last_stage"]:
        next_cost = stage["rank_up_cost"]
        next_label = "ارتقا کبوتر"
    elif at_cap and stage["is_last_stage"]:
        next_cost = None
        next_label = None
    else:
        next_cost = pigeon_level_up_cost(global_level)
        next_label = "ارتقا سطح"

    feature_level = pigeon_feature_level_for_count(salavat_count)
    next_feature_threshold = pigeon_count_for_next_feature_level(feature_level)

    wallet_str = to_persian_digits(f"{wallet:,}")
    pending_str = to_persian_digits(f"{int(pending):,}")
    seed_str = to_persian_digits(f"{seed:.1f}".rstrip("0").rstrip("."))
    feature_level_str = to_persian_digits(feature_level)

    lines = [
        f"🕊️ کبوتر {display_name}",
        "",
        f"💕 نام: {pigeon_name}",
        f"🍽️ شکم: {seed_status} ({_code(seed_str)} / {_code(to_persian_digits(capacity))})",
        "",
        f"🌟 مقام {_code(to_persian_digits(stage['stage_number']))}: {stage['name']}",
        f"⭐️ سطح: {_code(to_persian_digits(stage['sub_level']))} / {_code(to_persian_digits(stage['cap']))}",
        "",
        f"💰 صلوات پوینت‌ها: {_code(wallet_str)} 🪙",
        f"💫 تولید در ثانیه: {_code(_fmt_rate(rate))} 🪙",
        f"📥 آماده‌ی برداشت: {_code(pending_str)} 🪙",
        f"❄️ یخچال: {_code(to_persian_digits(fridge_count))} / {_code(to_persian_digits(fridge_cap))} (با «یخچالم» ببینش)",
    ]

    if next_cost is not None:
        cost_str = to_persian_digits(f"{next_cost:,}")
        lines.append(f"💰 هزینه‌ی {next_label}: {_code(cost_str)} 🪙")
    else:
        lines.append("👑 کبوترت به بالاترین مقام و سطح رسیده!")

    lines.append("")
    lines.append(f"🔓 پیشرفتِ قابلیت‌ها: {_code(feature_level_str)} / {_code(to_persian_digits(PIGEON_MAX_FEATURE_LEVEL))}")
    if next_feature_threshold is not None:
        remaining = max(0, next_feature_threshold - salavat_count)
        lines.append(
            f"🤲 تا سطحِ بعدِ قابلیت‌ها: {_code(to_persian_digits(remaining))} صلواتِ کامل دیگه بگو "
            f"(اللهم صل علی محمد و آل محمد)"
        )
    else:
        lines.append("🔓 پیشرفتِ قابلیت‌ها به سقف رسیده!")

    return "\n".join(lines)


def harvest_points(user_id: int) -> str:
    synced = _sync_production(user_id)
    pending = synced["pending"]
    harvest_amount = int(pending)

    if harvest_amount <= 0:
        return "⏳ هنوز چیزی برای برداشت جمع نشده؛ یکم صبر کن یا با «نذری» بهش سوخت بده 🕊️"

    now = _now()
    idem_key = f"{user_id}:pigeon_harvest:{int(now.timestamp())}"
    result = grant_bonus_xp(
        user_id, harvest_amount, EVENT_PIGEON_HARVEST,
        reference_id=str(int(now.timestamp())), idempotency_key=idem_key,
    )
    if not result["awarded"]:
        return "⚠️ مشکلی توی برداشت پیش اومد، دوباره امتحان کن."

    leftover = pending - harvest_amount
    db.set_pigeon_pending(user_id, leftover)

    amount_str = to_persian_digits(f"{harvest_amount:,}")
    lines = [f"📥 {_code(amount_str)} صلوات پوینت برداشت کردی و به کیف‌پولت اضافه شد!"]
    if result["leveled_up"]:
        lines.append(f"🌟 سطح کلیِ حسابت رفت {_code(to_persian_digits(result['new_level']))}!")
    return "\n".join(lines)


def level_up_pigeon(user_id: int) -> str:
    profile = db.get_profile(user_id)
    wallet = profile["xp"] if profile else 0
    state = db.get_pigeon_state(user_id)
    global_level = state["pigeon_global_level"] or 1
    stage = pigeon_stage_info(global_level)

    at_cap = stage["sub_level"] >= stage["cap"]

    if at_cap and stage["is_last_stage"]:
        return "👑 کبوترت همین الان تو بالاترین مقام و سطح ممکنه!"

    if at_cap:
        cost = stage["rank_up_cost"]
        next_stage = PIGEON_RANK_STAGES[stage["stage_index"] + 1]
        action_label = f"ارتقا کبوتر به «{next_stage['name']}»"
    else:
        cost = pigeon_level_up_cost(global_level)
        action_label = "ارتقا سطح"

    if wallet < cost:
        missing = cost - wallet
        return (
            f"💰 برای {action_label} به {_code(to_persian_digits(f'{cost:,}'))} صلوات پوینت نیاز داری.\n"
            f"هنوز {_code(to_persian_digits(f'{missing:,}'))} پوینت کم داری."
        )

    if not db.spend_points(user_id, cost):
        return "⚠️ مشکلی پیش اومد (شاید موجودیت تغییر کرده)، دوباره امتحان کن."

    new_level = global_level + 1
    db.set_pigeon_level(user_id, new_level)
    new_stage = pigeon_stage_info(new_level)

    if new_stage["stage_index"] != stage["stage_index"]:
        return f"🎉 مبارکه! کبوترت الان شد «{new_stage['name']}»!"
    return f"⬆️ کبوترت رفت سطح {_code(to_persian_digits(new_stage['sub_level']))} / {_code(to_persian_digits(new_stage['cap']))}!"