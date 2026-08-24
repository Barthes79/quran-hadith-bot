# -*- coding: utf-8 -*-
"""
یخچال صلواتی 🧊 و آیتم‌های نذری.

جریان کلی:
  - نوشتنِ «نذری» (کول‌داون ۱ ساعته) یه آیتمِ رندوم (با وزنِ رندوم)
    *پیشنهاد* می‌ده -- هنوز جایی ذخیره نشده. کاربر باید انتخاب کنه:
      • فروش نذری          -> فوری صلوات‌پوینت می‌گیره
      • بده کبوترت بخوره   -> فوری «ارزش غذایی»ش به دونِ کبوتر اضافه می‌شه
      • بندازش تو یخچال     -> اگه جا باشه، به‌عنوان یه آیتمِ واقعی تو
                                جدولِ nazri_items ذخیره می‌شه
  - آیتم‌های تو یخچال بعداً هم قابل فروش/تغذیه‌ان، هم می‌شه «گرم»شون کرد
    (یه مدت طول می‌کشه، بعدش ارزش/ارزش غذایی‌شون چند برابر می‌شه).
  - یخچال خودش «سطح» داره؛ سطح بالاتر = ظرفیتِ بیشتر؛ ارتقاش با خرج از
    کیف‌پول صلوات‌پوینته.

نکته‌ی مهم دربارهٔ کول‌داون: چون رول‌کردنِ آیتم دیگه مستقیماً XP نمی‌ده
(ممکنه کاربر انتخاب کنه بفروشه یا نده)، به‌جای award_xp/award_variable_xp
از xp.check_cooldown استفاده می‌کنیم و خودمون یه تراکنشِ صفر-امتیازی ثبت
می‌کنیم -- همون چیزی که کول‌داون/سقفِ روزانه رو کنترل می‌کنه.
"""

import random
import time
import datetime

from . import db
from .xp import check_cooldown, seconds_until_next, grant_bonus_xp
from .config import (
    EVENT_NAZRI_RECEIVED, NAZRI_ITEMS, NAZRI_ITEMS_BY_KEY,
    WARM_DURATION_SECONDS, WARM_VALUE_MULTIPLIER, WARM_NUTRITION_MULTIPLIER,
    fridge_capacity, fridge_upgrade_cost,
)
from text_utils import to_persian_digits

EVENT_NAZRI_SOLD = "nazri_sold"


def _code(value) -> str:
    return f"`{value}`"


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


def _format_cooldown(seconds: int) -> str:
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    secs_str = to_persian_digits(f"{secs:02d}")
    return f"{to_persian_digits(minutes)}:{secs_str}"


def compute_value(food_key: str, weight: float, is_warmed: bool) -> int:
    """ارزشِ فروشِ یه آیتم؛ متناسب با وزنه، و اگه گرم شده باشه چند برابر."""
    food = NAZRI_ITEMS_BY_KEY[food_key]
    value = food["value_per_kg"] * weight
    if is_warmed:
        value *= WARM_VALUE_MULTIPLIER
    return max(1, int(round(value)))


def compute_nutrition(food_key: str, is_warmed: bool) -> int:
    """ارزشِ غذاییِ یه آیتم (برای تغذیه‌ی کبوتر)؛ مستقل از وزنه."""
    food = NAZRI_ITEMS_BY_KEY[food_key]
    nutrition = food["nutrition"]
    if is_warmed:
        nutrition = int(round(nutrition * WARM_NUTRITION_MULTIPLIER))
    return nutrition


# ---------------------------------------------------------------------------
# رول‌کردن و پیشنهادِ نذریِ جدید (هنوز ذخیره نشده)
# ---------------------------------------------------------------------------

def roll_nazri(user_id: int) -> dict:
    """
    اگه کول‌داون/سقف روزانه اجازه بده، یه آیتم نذریِ رندوم (با وزنِ
    رندوم) برمی‌گردونه. خروجی:
        {"ok": True, "item": {...}} یا {"ok": False, "message": "..."}
    """
    allowed, reason = check_cooldown(user_id, EVENT_NAZRI_RECEIVED)
    if not allowed:
        if reason == "cooldown":
            remaining = seconds_until_next(user_id, EVENT_NAZRI_RECEIVED)
            return {"ok": False, "item": None,
                    "message": f"⏳ هنوز نذری قبلی هضم نشده! {_code(_format_cooldown(remaining))} دیگه صبر کن 😋"}
        if reason == "daily_cap":
            return {"ok": False, "item": None,
                    "message": "🌙 امروز دیگه نذری‌ای نمونده؛ فردا دوباره سر بزن 🍛"}
        return {"ok": False, "item": None, "message": "🍛 الان نمی‌شه، بعداً امتحان کن."}

    # یه تراکنشِ صفر-امتیازی، فقط برای ثبتِ زمان (کول‌داون/سقف روزانه)
    idem_key = f"{user_id}:{EVENT_NAZRI_RECEIVED}:{int(time.time()*1000)}"
    db.insert_xp_transaction(user_id, EVENT_NAZRI_RECEIVED, 0, None, idem_key)

    food = random.choice(NAZRI_ITEMS)
    weight = round(random.uniform(food["min_kg"], food["max_kg"]), 2)
    item = {"food_key": food["key"], "name": food["name"], "emoji": food["emoji"], "weight": weight}
    return {"ok": True, "item": item, "message": None}


def build_offer_text(item: dict) -> str:
    """متنِ پیشنهادِ نذریِ تازه‌رول‌شده (قبل از انتخاب کاربر)."""
    value = compute_value(item["food_key"], item["weight"], is_warmed=False)
    nutrition = compute_nutrition(item["food_key"], is_warmed=False)
    weight_str = to_persian_digits(f"{item['weight']:.2f}")
    lines = [
        f"{item['emoji']} یه پرس {item['name']} گیرت اومد!",
        "",
        f"⚖️ وزن: {_code(weight_str)} کیلو",
        f"💰 ارزش: {_code(to_persian_digits(f'{value:,}'))} 🪙",
        f"🍖 ارزش غذایی: {_code(to_persian_digits(nutrition))}",
        "",
        "می‌خوای باهاش چی‌کار کنی؟",
    ]
    return "\n".join(lines)


def sell_offered_item(user_id: int, food_key: str, weight: float) -> str:
    """فروشِ فوریِ آیتمِ پیشنهادی (هنوز تو یخچال ذخیره نشده بود)."""
    value = compute_value(food_key, weight, is_warmed=False)
    idem_key = f"{user_id}:{EVENT_NAZRI_SOLD}:{int(_now().timestamp()*1000)}"
    result = grant_bonus_xp(user_id, value, EVENT_NAZRI_SOLD, reference_id=idem_key, idempotency_key=idem_key)
    if not result["awarded"]:
        return "⚠️ مشکلی پیش اومد، دوباره امتحان کن."
    lines = [f"💰 فروختیش و {_code(to_persian_digits(f'{value:,}'))} صلوات پوینت گرفتی!"]
    if result["leveled_up"]:
        lines.append(f"🎊 تبریک! رفتی سطح {_code(to_persian_digits(result['new_level']))}!")
    return "\n".join(lines)


def feed_offered_item(user_id: int, food_key: str) -> str:
    """تغذیه‌ی فوریِ کبوتر با آیتمِ پیشنهادی."""
    from .pigeon import add_seed_to_pigeon  # جلوگیری از import چرخه‌ای

    nutrition = compute_nutrition(food_key, is_warmed=False)
    result = add_seed_to_pigeon(user_id, nutrition)
    new_seed_str = to_persian_digits(f"{result['new_seed']:.1f}".rstrip("0").rstrip("."))
    return (
        "🕊️ کبوترت خورد و حسابی خوشحال شد!\n"
        f"🌾 دون فعلی: {_code(new_seed_str)} / {_code(to_persian_digits(result['capacity']))}"
    )


def store_offered_item(user_id: int, food_key: str, weight: float) -> str:
    """گذاشتنِ آیتمِ پیشنهادی تو یخچال (اگه جا باشه)."""
    level = db.get_fridge_level(user_id)
    capacity = fridge_capacity(level)
    current_count = db.count_fridge_items(user_id)
    if current_count >= capacity:
        return "❄️ یخچالت پره! اول یه چیزی رو بفروش یا بده کبوترت بخوره، بعد جا باز می‌شه."
    db.insert_fridge_item(user_id, food_key, weight)
    return "❄️ گذاشتیمش تو یخچالت. با «یخچالم» می‌تونی ببینیش."


# ---------------------------------------------------------------------------
# پنلِ یخچال (آیتم‌های واقعاً ذخیره‌شده)
# ---------------------------------------------------------------------------

def _finalize_ready_items(user_id: int):
    """هر آیتمی که وقتِ گرم‌شدنش تموم شده رو is_warmed=1 می‌کنه. مثل
    idle-mining کبوتر، این کاملاً lazy انجام می‌شه (هر بار پنل باز شد)."""
    items = db.get_fridge_items(user_id)
    now = _now()
    for it in items:
        if not it["is_warmed"] and it["warm_ready_at"]:
            ready_at = _parse_dt(it["warm_ready_at"])
            if ready_at and now >= ready_at:
                db.finalize_warm_item(user_id, it["id"])


def build_fridge_text(user_id: int, display_name: str) -> str:
    """کارت وضعیت کامل یخچال: سطح، ظرفیت، لیست آیتم‌ها، هزینه‌ی ارتقا."""
    _finalize_ready_items(user_id)
    items = db.get_fridge_items(user_id)
    level = db.get_fridge_level(user_id)
    capacity = fridge_capacity(level)
    upgrade_cost = fridge_upgrade_cost(level)
    now = _now()

    lines = [
        f"❄️ یخچال صلواتی {display_name}",
        "",
        f"⭐️ سطح یخچال: {_code(to_persian_digits(level))}",
        f"🍽 ظرفیت یخچال: {_code(to_persian_digits(len(items)))} / {_code(to_persian_digits(capacity))}",
    ]

    if items:
        lines.append("")
        lines.append("〰️〰️〰️〰️〰️〰️〰️")
        for it in items:
            food = NAZRI_ITEMS_BY_KEY[it["food_key"]]
            is_warmed = bool(it["is_warmed"])
            value = compute_value(it["food_key"], it["weight"], is_warmed)
            nutrition = compute_nutrition(it["food_key"], is_warmed)
            weight_str = to_persian_digits(f"{it['weight']:.2f}")
            warm_tag = " (پخته شده 🔥)" if is_warmed else ""

            lines.append("")
            lines.append(f"{food['emoji']} | {food['name']}{warm_tag}")
            lines.append(f"┘─ ⚖️ وزن: {_code(weight_str)} کیلو")
            lines.append(f"┘─ 💰 ارزش: {_code(to_persian_digits(f'{value:,}'))} 🪙")
            lines.append(f"┘─ 🍖 ارزش غذایی: {_code(to_persian_digits(nutrition))}")

            if not is_warmed and it["warm_started_at"]:
                ready_at = _parse_dt(it["warm_ready_at"])
                remaining = max(0, int((ready_at - now).total_seconds())) if ready_at else 0
                if remaining > 0:
                    lines.append(f"┘─ 🔥 در حال گرم‌شدن... {_code(_format_cooldown(remaining))} مونده")
        lines.append("")
        lines.append("〰️〰️〰️〰️〰️〰️〰️")
    else:
        lines.append("")
        lines.append("یخچالت خالیه؛ با نوشتن «نذری» یه چیزی جمع کن 🍛")

    lines.append("")
    lines.append(f"💰 هزینه ارتقا سطح یخچال: {_code(to_persian_digits(f'{upgrade_cost:,}'))} صلوات پوینت 🪙")

    return "\n".join(lines)


def sell_fridge_item(user_id: int, item_id: int) -> str:
    item = db.get_fridge_item(user_id, item_id)
    if not item:
        return "⚠️ این آیتم دیگه تو یخچالت نیست."
    value = compute_value(item["food_key"], item["weight"], bool(item["is_warmed"]))
    idem_key = f"{user_id}:{EVENT_NAZRI_SOLD}:item{item_id}"
    result = grant_bonus_xp(user_id, value, EVENT_NAZRI_SOLD, reference_id=str(item_id), idempotency_key=idem_key)
    if not result["awarded"]:
        return "⚠️ مشکلی پیش اومد، دوباره امتحان کن."
    db.delete_fridge_item(user_id, item_id)
    lines = [f"💰 فروختیش و {_code(to_persian_digits(f'{value:,}'))} صلوات پوینت گرفتی!"]
    if result["leveled_up"]:
        lines.append(f"🎊 تبریک! رفتی سطح {_code(to_persian_digits(result['new_level']))}!")
    return "\n".join(lines)


def feed_fridge_item(user_id: int, item_id: int) -> str:
    from .pigeon import add_seed_to_pigeon  # جلوگیری از import چرخه‌ای

    item = db.get_fridge_item(user_id, item_id)
    if not item:
        return "⚠️ این آیتم دیگه تو یخچالت نیست."
    nutrition = compute_nutrition(item["food_key"], bool(item["is_warmed"]))
    result = add_seed_to_pigeon(user_id, nutrition)
    db.delete_fridge_item(user_id, item_id)
    new_seed_str = to_persian_digits(f"{result['new_seed']:.1f}".rstrip("0").rstrip("."))
    return (
        "🕊️ کبوترت خورد و حسابی خوشحال شد!\n"
        f"🌾 دون فعلی: {_code(new_seed_str)} / {_code(to_persian_digits(result['capacity']))}"
    )


def warm_fridge_item(user_id: int, item_id: int) -> str:
    item = db.get_fridge_item(user_id, item_id)
    if not item:
        return "⚠️ این آیتم دیگه تو یخچالت نیست."
    if item["is_warmed"]:
        return "🔥 این یکی از قبل گرمه."

    now = _now()
    if item["warm_started_at"]:
        ready_at = _parse_dt(item["warm_ready_at"])
        remaining = max(0, int((ready_at - now).total_seconds())) if ready_at else 0
        if remaining > 0:
            return f"⏳ داره گرم می‌شه، {_code(_format_cooldown(remaining))} دیگه آماده می‌شه."
        db.finalize_warm_item(user_id, item_id)
        return "🔥 گرم شد! ارزش و ارزش غذاییش رفت بالا."

    ready_at = now + datetime.timedelta(seconds=WARM_DURATION_SECONDS)
    db.start_warming_item(user_id, item_id, now.isoformat(), ready_at.isoformat())
    return f"🔥 گذاشتیمش رو گرم‌کن؛ {_code(_format_cooldown(WARM_DURATION_SECONDS))} دیگه آماده می‌شه."


def upgrade_fridge(user_id: int) -> str:
    level = db.get_fridge_level(user_id)
    cost = fridge_upgrade_cost(level)
    profile = db.get_profile(user_id)
    wallet = profile["xp"] if profile else 0

    if wallet < cost:
        missing = cost - wallet
        return (
            f"💰 برای ارتقا یخچال به {_code(to_persian_digits(f'{cost:,}'))} صلوات پوینت نیاز داری.\n"
            f"هنوز {_code(to_persian_digits(f'{missing:,}'))} پوینت کم داری."
        )

    if not db.spend_points(user_id, cost):
        return "⚠️ مشکلی پیش اومد، دوباره امتحان کن."

    db.set_fridge_level(user_id, level + 1)
    return f"🎉 یخچالت رفت سطح {_code(to_persian_digits(level + 1))}!"
