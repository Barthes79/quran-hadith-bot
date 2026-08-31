# -*- coding: utf-8 -*-
"""
منطق یخچال صلواتی و آیتم‌های نذری.

🔒 ادمین‌ها (ADMIN_IDS از config اصلی) کول‌داون و سقف روزانه ندارند.
"""

import random
import datetime
import logging

from . import db
from .config import (
    NAZRI_ITEMS, NAZRI_ITEMS_BY_KEY,
    EVENT_NAZRI_RECEIVED,
    WARM_DURATION_SECONDS,
    WARM_VALUE_MULTIPLIER,
    WARM_NUTRITION_MULTIPLIER,
    fridge_capacity, fridge_upgrade_cost,
    GAMIFICATION_TIMEZONE,
    FRIDGE_BUY_COST,
)
from .events import dispatch_event
from .xp import seconds_until_next
from .angel import add_seed_to_angel
from text_utils import to_persian_digits

from config import ADMIN_IDS

logger = logging.getLogger(__name__)


def _code(value) -> str:
    return f"`{value}`"


def _now() -> datetime.datetime:
    return datetime.datetime.now(GAMIFICATION_TIMEZONE)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def roll_nazri(user_id: int) -> dict:
    if not _is_admin(user_id):
        remaining = seconds_until_next(user_id, EVENT_NAZRI_RECEIVED)
        if remaining > 0:
            minutes = int(remaining // 60)
            secs = int(remaining % 60)
            return {
                "ok": False,
                "message": f"⏳ هنوز نذری قبلی هضم نشده! {_code(to_persian_digits(minutes))}:{_code(to_persian_digits(secs))} دیگه صبر کن 😋"
            }

        today_key = _now().date().isoformat()
        count_today = db.count_events_today(user_id, EVENT_NAZRI_RECEIVED, today_key)
        daily_cap = 10
        if count_today >= daily_cap:
            return {
                "ok": False,
                "message": "🌙 امروز به سقف نذری‌ها رسیدی؛ فردا دوباره تلاش کن."
            }

    item_template = random.choice(NAZRI_ITEMS)
    weight = round(random.uniform(item_template["min_kg"], item_template["max_kg"]), 2)
    value = int(round(weight * item_template["value_per_kg"]))
    nutrition = item_template["nutrition"]

    return {
        "ok": True,
        "item": {
            "food_key": item_template["key"],
            "name": item_template["name"],
            "emoji": item_template["emoji"],
            "weight": weight,
            "value": value,
            "nutrition": nutrition,
        }
    }


def build_offer_text(item: dict) -> str:
    return (
        f"{item['emoji']} *{item['name']}*\n"
        f"وزن: {_code(to_persian_digits(f'{item['weight']:.2f}'))} کیلو\n"
        f"💰 ارزش فروش: {_code(to_persian_digits(f'{item['value']:,}'))} صلوات پوینت\n"
        f"🍽️ ارزش غذایی: {_code(to_persian_digits(item['nutrition']))} واحد دون\n\n"
        "یکی از گزینه‌های زیر را انتخاب کن:"
    )


def sell_offered_item(user_id: int, food_key: str, weight: float) -> str:
    template = NAZRI_ITEMS_BY_KEY.get(food_key)
    if not template:
        return "⚠️ آیتم نامعتبر است."
    value = int(round(weight * template["value_per_kg"]))
    if value <= 0:
        return "⚠️ ارزش این نذری صفر است."
    result = dispatch_event(EVENT_NAZRI_RECEIVED, user_id, xp_override=value)
    if not result["awarded"]:
        return "⚠️ خطا در دریافت پوینت. دوباره امتحان کن."
    return (
        f"💰 {_code(to_persian_digits(value))} صلوات پوینت از فروش نذری دریافت کردی!"
        + (f" 🌟 سطح کلی حسابت رفت {_code(to_persian_digits(result['new_level']))}!" if result["leveled_up"] else "")
    )


def feed_offered_item(user_id: int, food_key: str) -> str:
    template = NAZRI_ITEMS_BY_KEY.get(food_key)
    if not template:
        return "⚠️ آیتم نامعتبر است."
    nutrition = template["nutrition"]
    if nutrition <= 0:
        return "⚠️ این نذری ارزش غذایی ندارد."
    dispatch_event(EVENT_NAZRI_RECEIVED, user_id, xp_override=0)
    result = add_seed_to_angel(user_id, nutrition)
    return (
        f"👼 فرشته‌ات {_code(to_persian_digits(nutrition))} واحد سوخت خورد!\n"
        f"سوخت فعلی: {_code(to_persian_digits(f'{result['new_seed']:.1f}'))} / {_code(to_persian_digits(result['capacity']))}"
    )


def store_offered_item(user_id: int, food_key: str, weight: float) -> str:
    template = NAZRI_ITEMS_BY_KEY.get(food_key)
    if not template:
        return "⚠️ آیتم نامعتبر است."
    
    if not db.get_has_fridge(user_id):
        return "❌ شما یخچال ندارید! ابتدا با نوشتن «یخچالم» یخچال را خریداری کنید."

    fridge_level = db.get_fridge_level(user_id)
    cap = fridge_capacity(fridge_level)
    current_count = db.count_fridge_items(user_id)
    if current_count >= cap:
        return f"❄️ یخچال پر است! (ظرفیت {_code(to_persian_digits(cap))})"

    dispatch_event(EVENT_NAZRI_RECEIVED, user_id, xp_override=0)
    item_id = db.insert_fridge_item(user_id, food_key, weight)
    return f"❄️ {template['emoji']} {template['name']} با وزن {_code(to_persian_digits(f'{weight:.2f}'))} کیلو در یخچال ذخیره شد."


def buy_fridge(user_id: int) -> str:
    if db.get_has_fridge(user_id):
        return "❄️ شما قبلاً یخچال خریداری کرده‌اید!"

    profile = db.get_profile(user_id)
    wallet = profile["xp"] if profile else 0
    cost = FRIDGE_BUY_COST

    if wallet < cost:
        missing = cost - wallet
        return f"💰 برای خرید یخچال به {_code(to_persian_digits(cost))} صلوات پوینت نیاز داری.\nهنوز {_code(to_persian_digits(missing))} پوینت کم داری."

    if not db.spend_points(user_id, cost):
        return "⚠️ خطا در انجام خرید. دوباره امتحان کن."

    db.set_has_fridge(user_id, True)
    return f"🎉 یخچال صلواتی با موفقیت خریداری شد! هزینه: {_code(to_persian_digits(cost))} صلوات پوینت.\n\nحالا می‌تونی نذری‌هات رو توی یخچال ذخیره کنی و از قابلیت‌های یخچال استفاده کنی! ❄️"


def build_fridge_text(user_id: int, display_name: str) -> str:
    items = db.get_fridge_items(user_id)
    fridge_level = db.get_fridge_level(user_id)
    cap = fridge_capacity(fridge_level)
    if not items:
        return f"❄️ *یخچال {display_name}*\n\nهیچ آیتمی در یخچال نیست."
    lines = [f"❄️ *یخچال {display_name}*  ({_code(to_persian_digits(len(items)))}/{_code(to_persian_digits(cap))})\n"]
    for it in items:
        template = NAZRI_ITEMS_BY_KEY.get(it["food_key"])
        name = template["name"] if template else it["food_key"]
        emoji = template["emoji"] if template else "🍽️"
        status = "🔥 گرم‌شده" if it["is_warmed"] else "🧊 سرد"
        lines.append(f"{emoji} {name} — {_code(to_persian_digits(f'{it["weight"]:.2f}'))} کیلو — {status}")
    return "\n".join(lines)


def sell_fridge_item(user_id: int, item_id: int) -> str:
    item = db.get_fridge_item(user_id, item_id)
    if not item:
        return "⚠️ این آیتم در یخچال شما وجود ندارد."
    template = NAZRI_ITEMS_BY_KEY.get(item["food_key"])
    if not template:
        return "⚠️ آیتم نامعتبر است."
    weight = item["weight"]
    multiplier = WARM_VALUE_MULTIPLIER if item["is_warmed"] else 1.0
    value = int(round(weight * template["value_per_kg"] * multiplier))
    if value <= 0:
        return "⚠️ ارزش این نذری صفر است."
    if not db.delete_fridge_item(user_id, item_id):
        return "⚠️ خطا در حذف آیتم از یخچال."
    result = dispatch_event(EVENT_NAZRI_RECEIVED, user_id, xp_override=value)
    return (
        f"💰 {_code(to_persian_digits(value))} صلوات پوینت از فروش {template['name']} دریافت کردی!"
        + (f" 🌟 سطح کلی حسابت رفت {_code(to_persian_digits(result['new_level']))}!" if result["leveled_up"] else "")
    )


def feed_fridge_item(user_id: int, item_id: int) -> str:
    item = db.get_fridge_item(user_id, item_id)
    if not item:
        return "⚠️ این آیتم در یخچال شما وجود ندارد."
    template = NAZRI_ITEMS_BY_KEY.get(item["food_key"])
    if not template:
        return "⚠️ آیتم نامعتبر است."
    nutrition = template["nutrition"]
    if item["is_warmed"]:
        nutrition = int(round(nutrition * WARM_NUTRITION_MULTIPLIER))
    if nutrition <= 0:
        return "⚠️ این نذری ارزش غذایی ندارد."
    if not db.delete_fridge_item(user_id, item_id):
        return "⚠️ خطا در حذف آیتم از یخچال."
    dispatch_event(EVENT_NAZRI_RECEIVED, user_id, xp_override=0)
    result = add_seed_to_angel(user_id, nutrition)
    return (
        f"👼 فرشته‌ات {_code(to_persian_digits(nutrition))} واحد سوخت از {template['name']} خورد!\n"
        f"سوخت فعلی: {_code(to_persian_digits(f'{result['new_seed']:.1f}'))} / {_code(to_persian_digits(result['capacity']))}"
    )


def warm_fridge_item(user_id: int, item_id: int) -> str:
    item = db.get_fridge_item(user_id, item_id)
    if not item:
        return "⚠️ این آیتم در یخچال شما وجود ندارد."
    if item["is_warmed"]:
        return "🔥 این آیتم قبلاً گرم شده است."
    if item["warm_started_at"] is not None:
        return "⏳ این آیتم در حال گرم شدن است."
    now = _now()
    started_at = now.isoformat()
    ready_at = (now + datetime.timedelta(seconds=WARM_DURATION_SECONDS)).isoformat()
    if not db.start_warming_item(user_id, item_id, started_at, ready_at):
        return "⚠️ خطا در شروع گرم‌کردن."
    minutes = WARM_DURATION_SECONDS // 60
    return f"🔥 گرم‌کردن شروع شد! حدود {_code(to_persian_digits(minutes))} دقیقه دیگه آماده می‌شه."


def upgrade_fridge(user_id: int) -> str:
    current_level = db.get_fridge_level(user_id)
    new_level = current_level + 1
    cost = fridge_upgrade_cost(current_level)
    if not db.spend_points(user_id, cost):
        return f"💰 برای ارتقا به {_code(to_persian_digits(f'{cost:,}'))} صلوات پوینت نیاز داری."
    db.set_fridge_level(user_id, new_level)
    new_cap = fridge_capacity(new_level)
    return f"⬆️ یخچالت به سطح {_code(to_persian_digits(new_level))} ارتقا یافت! ظرفیت جدید: {_code(to_persian_digits(new_cap))}"
