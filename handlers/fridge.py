# -*- coding: utf-8 -*-
"""
منطق یخچال صلواتی و آیتم‌های نذری.

قابلیت‌ها:
  - roll_nazri: تولید تصادفی یک آیتم نذری با در نظر گرفتن کول‌داون و سقف روزانه
  - sell_offered_item: فروش فوری آیتم پیشنهادی
  - feed_offered_item: تغذیه‌ی کبوتر با آیتم پیشنهادی
  - store_offered_item: ذخیره‌ی آیتم در یخچال
  - sell_fridge_item: فروش آیتم از یخچال
  - feed_fridge_item: تغذیه‌ی کبوتر از یخچال
  - warm_fridge_item: گرم کردن آیتم در یخچال
  - upgrade_fridge: ارتقا سطح یخچال
  - build_offer_text, build_fridge_text: ساخت متن‌های نمایشی

🔒 تغییر جدید: ادمین‌ها (ADMIN_IDS) محدودیت کول‌داون و سقف روزانه‌ی نذری را ندارند.
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
)
from .xp import dispatch_event, seconds_until_next
from .pigeon import add_seed_to_pigeon
from text_utils import to_persian_digits
from config import ADMIN_IDS  # ✅ ایمپورت از فایل config اصلی ربات

logger = logging.getLogger(__name__)


def _code(value) -> str:
    return f"`{value}`"


def _now() -> datetime.datetime:
    return datetime.datetime.now(GAMIFICATION_TIMEZONE)


def _is_admin(user_id: int) -> bool:
    """بررسی می‌کند که آیا کاربر در لیست ادمین‌ها است."""
    return user_id in ADMIN_IDS


def roll_nazri(user_id: int) -> dict:
    """
    یک آیتم نذری تصادفی با وزن تصادفی تولید می‌کند.
    اگر کاربر به سقف روزانه رسیده باشد یا کول‌داون فعال باشد، پیام خطا برمی‌گرداند.
    
    🔒 ادمین‌ها محدودیت کول‌داون و سقف روزانه را ندارند.
    """
    # 🔒 اگر کاربر ادمین است، محدودیت‌ها را نادیده بگیر
    if _is_admin(user_id):
        logger.info(f"ADMIN {user_id} is bypassing nazri cooldown")
    else:
        # بررسی کول‌داون (فقط برای غیرادمین‌ها)
        remaining = seconds_until_next(user_id, EVENT_NAZRI_RECEIVED)
        if remaining > 0:
            minutes = int(remaining // 60)
            secs = int(remaining % 60)
            return {
                "ok": False,
                "message": f"⏳ تا نذری بعدی {_code(to_persian_digits(minutes))} دقیقه و {_code(to_persian_digits(secs))} ثانیه مونده."
            }

        # بررسی سقف روزانه (فقط برای غیرادمین‌ها)
        today_key = _now().date().isoformat()
        count_today = db.count_events_today(user_id, EVENT_NAZRI_RECEIVED, today_key)
        daily_cap = 10  # از config خوانده شود
        if count_today >= daily_cap:
            return {
                "ok": False,
                "message": "🌙 امروز به سقف نذری‌ها رسیدی؛ فردا دوباره تلاش کن."
            }

    # انتخاب آیتم تصادفی
    item_template = random.choice(NAZRI_ITEMS)
    weight = round(random.uniform(item_template["min_kg"], item_template["max_kg"]), 2)
    value = int(round(weight * item_template["value_per_kg"]))
    nutrition = item_template["nutrition"]  # ارزش غذایی ثابت، مستقل از وزن

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
    """متن نمایشی برای آیتم پیشنهادی نذری."""
    return (
        f"{item['emoji']} *{item['name']}*\n"
        f"وزن: {_code(to_persian_digits(f'{item['weight']:.2f}'))} کیلو\n"
        f"💰 ارزش فروش: {_code(to_persian_digits(f'{item['value']:,}'))} صلوات پوینت\n"
        f"🍽️ ارزش غذایی: {_code(to_persian_digits(item['nutrition']))} واحد دون\n\n"
        "یکی از گزینه‌های زیر را انتخاب کن:"
    )


# ============================================================
# عملیات روی آیتم پیشنهادی (هنوز ذخیره نشده)
# ============================================================

def sell_offered_item(user_id: int, food_key: str, weight: float) -> str:
    """فروش فوری آیتم پیشنهادی و دریافت صلوات پوینت."""
    template = NAZRI_ITEMS_BY_KEY.get(food_key)
    if not template:
        return "⚠️ آیتم نامعتبر است."

    value = int(round(weight * template["value_per_kg"]))
    if value <= 0:
        return "⚠️ ارزش این نذری صفر است."

    # ثبت رویداد (برای ادمین‌ها هم محدودیت اعمال نمی‌شود چون قبلاً در roll_nazri چک شده)
    result = dispatch_event(EVENT_NAZRI_RECEIVED, user_id, xp_override=value)
    if not result["awarded"]:
        return "⚠️ خطا در دریافت پوینت. دوباره امتحان کن."

    return (
        f"💰 {_code(to_persian_digits(value))} صلوات پوینت از فروش نذری دریافت کردی!"
        + (f" 🌟 سطح کلی حسابت رفت {_code(to_persian_digits(result['new_level']))}!" if result["leveled_up"] else "")
    )


def feed_offered_item(user_id: int, food_key: str) -> str:
    """تغذیه‌ی کبوتر با آیتم پیشنهادی (تبدیل به دون)."""
    template = NAZRI_ITEMS_BY_KEY.get(food_key)
    if not template:
        return "⚠️ آیتم نامعتبر است."

    nutrition = template["nutrition"]
    if nutrition <= 0:
        return "⚠️ این نذری ارزش غذایی ندارد."

    # ثبت رویداد با XP=0 (چون پوینت نمی‌دهد، فقط دون می‌دهد)
    dispatch_event(EVENT_NAZRI_RECEIVED, user_id, xp_override=0)

    result = add_seed_to_pigeon(user_id, nutrition)
    return (
        f"🕊️ کبوترت {_code(to_persian_digits(nutrition))} واحد دون خورد!\n"
        f"دون فعلی: {_code(to_persian_digits(f'{result['new_seed']:.1f}'))} / {_code(to_persian_digits(result['capacity']))}"
    )


def store_offered_item(user_id: int, food_key: str, weight: float) -> str:
    """ذخیره‌ی آیتم پیشنهادی در یخچال."""
    template = NAZRI_ITEMS_BY_KEY.get(food_key)
    if not template:
        return "⚠️ آیتم نامعتبر است."

    fridge_level = db.get_fridge_level(user_id)
    cap = fridge_capacity(fridge_level)
    current_count = db.count_fridge_items(user_id)
    if current_count >= cap:
        return f"❄️ یخچال پر است! (ظرفیت {_code(to_persian_digits(cap))})"

    # ثبت رویداد با XP=0 (چون پوینت نمی‌دهد، فقط ذخیره می‌شود)
    dispatch_event(EVENT_NAZRI_RECEIVED, user_id, xp_override=0)

    item_id = db.insert_fridge_item(user_id, food_key, weight)
    return f"❄️ {template['emoji']} {template['name']} با وزن {_code(to_persian_digits(f'{weight:.2f}'))} کیلو در یخچال ذخیره شد."


# ============================================================
# عملیات روی آیتم‌های موجود در یخچال
# ============================================================

def build_fridge_text(user_id: int, display_name: str) -> str:
    """متن نمایشی یخچال با لیست آیتم‌ها."""
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
    """فروش یک آیتم از یخچال."""
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

    # ثبت رویداد با XP=value (فروش = دریافت پوینت)
    result = dispatch_event(EVENT_NAZRI_RECEIVED, user_id, xp_override=value)
    return (
        f"💰 {_code(to_persian_digits(value))} صلوات پوینت از فروش {template['name']} دریافت کردی!"
        + (f" 🌟 سطح کلی حسابت رفت {_code(to_persian_digits(result['new_level']))}!" if result["leveled_up"] else "")
    )


def feed_fridge_item(user_id: int, item_id: int) -> str:
    """تغذیه‌ی کبوتر با یک آیتم از یخچال."""
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
    result = add_seed_to_pigeon(user_id, nutrition)
    return (
        f"🕊️ کبوترت {_code(to_persian_digits(nutrition))} واحد دون از {template['name']} خورد!\n"
        f"دون فعلی: {_code(to_persian_digits(f'{result['new_seed']:.1f}'))} / {_code(to_persian_digits(result['capacity']))}"
    )


def warm_fridge_item(user_id: int, item_id: int) -> str:
    """شروع فرآیند گرم کردن یک آیتم در یخچال."""
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
    """ارتقا سطح یخچال با خرج صلوات پوینت."""
    current_level = db.get_fridge_level(user_id)
    new_level = current_level + 1
    cost = fridge_upgrade_cost(current_level)

    if not db.spend_points(user_id, cost):
        return f"💰 برای ارتقا به {_code(to_persian_digits(f'{cost:,}'))} صلوات پوینت نیاز داری."

    db.set_fridge_level(user_id, new_level)
    new_cap = fridge_capacity(new_level)
    return f"⬆️ یخچالت به سطح {_code(to_persian_digits(new_level))} ارتقا یافت! ظرفیت جدید: {_code(to_persian_digits(new_cap))}"