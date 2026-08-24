# -*- coding: utf-8 -*-
"""
منطق شخصیت همراه: کبوتر 🕊️

رفتارهای اصلی:
  - «صلوات» → صلوات پوینتِ تصادفی (SALAVAT_POINT_MIN تا MAX) با کول‌داون
    ۵ دقیقه؛ در پیوی مستقیماً award می‌شه، در گروه از طریق
    dispatch_event(xp_override=...) که handlers/salavat.py صداش می‌زنه.
  - کبوتر، وقتی سوخت (دون) داره، خودش مثل یه ماینر passive صلوات پوینت
    تولید می‌کنه (نرخ تولید به سطح کلی خودش بستگی داره). این پوینت‌ها
    اول تو یه استخر «آماده‌ی برداشت» جمع می‌شن و با دکمه‌ی «برداشت» به
    کیف‌پول اصلی (ستون xp) منتقل می‌شن.
  - کاربر می‌تونه با خرج از کیف‌پول، سطح کبوتر رو بالا ببره؛ وقتی سطح به
    سقفِ مقام فعلی رسید، به‌جاش «ارتقا مقام» (هزینه‌ی سنگین‌تر) میاد.
  - سوخت (دون) دیگه خودکار از یخچال پر نمی‌شه؛ منطقِ «نذری»/یخچال کامل
    تو gamification/fridge.py هست و از تابع add_seed_to_pigeon همینجا
    برای «بده کبوترت بخوره» استفاده می‌کنه.

توجه: این ماژول فقط متن آماده برمی‌گرداند؛ ارسال پیام/دکمه به تلگرام در
handlers/pigeon.py انجام می‌شود.
"""

import random
import datetime

from . import db
from .xp import award_variable_xp, grant_bonus_xp, seconds_until_next
from .config import (
    EVENT_SALAVAT_SENT, EVENT_PIGEON_HARVEST,
    SALAVAT_POINT_MIN, SALAVAT_POINT_MAX,
    PIGEON_RANK_STAGES, PIGEON_FUEL_SECONDS_PER_UNIT,
    pigeon_fuel_capacity, pigeon_stage_info, pigeon_level_up_cost, pigeon_production_rate,
    fridge_capacity,
)
from text_utils import to_persian_digits, normalize_for_search

DEFAULT_PIGEON_NAME = "کبوتر"

# صلوات پوینت (چه پیوی چه گروه) فقط وقتی داده می‌شه که کاربر *عین کامل*
# عبارت صلوات رو نوشته باشه، نه فقط کلمه‌ی «صلوات» یا «N صلوات». از
# normalize_for_search استفاده می‌کنیم تا «آل»/«ال»، فاصله‌های اضافه، و
# تفاوت‌های ظاهری عربی/فارسی (رایج تو کیبورد موبایل) مشکلی ایجاد نکنن؛
# ولی همچنان باید عبارت *کامل* باشه، نه بخشی از یه پیام بزرگ‌تر یا کوتاه‌تر.
_SALAVAT_PHRASE_NORMALIZED = normalize_for_search("اللهم صل علی محمد و آل محمد")


def is_full_salavat_phrase(text: str) -> bool:
    """True فقط اگه کل پیام (بعد از نرمال‌سازی) دقیقاً همون عبارت کامل
    صلوات باشه. هم handlers/pigeon.py (پیوی) هم handlers/salavat.py
    (گروه) از همین یه تابع استفاده می‌کنن تا رفتار یکسان بمونه."""
    return normalize_for_search(text) == _SALAVAT_PHRASE_NORMALIZED


def _format_cooldown(seconds: int) -> str:
    """ثانیه را به شکل mm:ss با ارقام فارسی نمایش می‌دهد (مثلاً «۴:۵۵»)."""
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    secs_str = to_persian_digits(f"{secs:02d}")
    return f"{to_persian_digits(minutes)}:{secs_str}"


def _code(value) -> str:
    """مقدار رو بین بک‌تیک می‌ذاره تا تو تلگرام به‌شکل monospace/آبی و
    قابل‌کپی (با یه تپ) نمایش داده بشه -- دقیقاً همون افکتی که تو
    مثال‌های Meowie رو اعداد بود. پیام‌هایی که از این استفاده می‌کنن باید
    با parse_mode="Markdown" فرستاده بشن."""
    return f"`{value}`"


def _fmt_rate(rate: float) -> str:
    """عدد نرخ تولید رو کوتاه و بدون صفرهای اضافه نشون می‌ده (۰.۱، ۴.۵، ۱۰)."""
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
    """یه عدد تصادفیِ صلوات پوینت برمی‌گردونه (برای پیوی و گروه، یکسان)."""
    return random.randint(SALAVAT_POINT_MIN, SALAVAT_POINT_MAX)


def _sync_production(user_id: int) -> dict:
    """
    از آخرین سینک تا الان، بر اساس سوخت (دون) موجود، تولیدِ passive رو
    حساب می‌کنه: تولید رو به pigeon_pending_points اضافه می‌کنه و دون
    مصرف‌شده رو کم می‌کنه. همیشه قبل از ساختن کارت وضعیت یا برداشت صدا
    زده می‌شه تا اعداد به‌روز باشن.

    توجه: سوخت (دون) دیگه خودکار از یخچال پر نمی‌شه -- فقط با «بده
    کبوترت بخوره» (gamification/fridge.py، از طریق add_seed_to_pigeon
    همینجا) پر می‌شه.
    """
    state = db.get_pigeon_state(user_id)
    now = _now()
    last = _parse_dt(state.get("pigeon_last_synced_at")) or now
    elapsed = max(0.0, (now - last).total_seconds())

    global_level = state["pigeon_global_level"] or 1
    seed = float(state["pigeon_seed"] or 0)
    pending = float(state["pigeon_pending_points"] or 0)

    capacity = pigeon_fuel_capacity(global_level)

    if elapsed > 0 and seed > 0:
        rate = pigeon_production_rate(global_level)
        fuel_seconds = seed * PIGEON_FUEL_SECONDS_PER_UNIT
        active_seconds = min(elapsed, fuel_seconds)
        produced = rate * active_seconds
        seed_used = active_seconds / PIGEON_FUEL_SECONDS_PER_UNIT
        seed = max(0.0, seed - seed_used)
        pending += produced

    db.update_pigeon_seed_and_pending(user_id, seed=seed, pending=pending, synced_at=now.isoformat())

    return {
        "global_level": global_level,
        "seed": seed,
        "pending": pending,
        "capacity": capacity,
    }


def add_seed_to_pigeon(user_id: int, amount: float) -> dict:
    """مستقیم مقدار amount رو به سوخت (دون) کبوتر اضافه می‌کنه (تا سقف
    ظرفیت)؛ قبلش سینک می‌کنه تا وضعیت فعلی درست باشه. برای «بده کبوترت
    بخوره» روی آیتم‌های نذری (gamification/fridge.py) استفاده می‌شه."""
    synced = _sync_production(user_id)
    new_seed = min(synced["capacity"], synced["seed"] + amount)
    db.update_pigeon_seed_and_pending(
        user_id, seed=new_seed, pending=synced["pending"], synced_at=_now().isoformat()
    )
    return {"new_seed": new_seed, "capacity": synced["capacity"]}


def _build_salavat_card(user_id: int, result: dict) -> str:
    """
    متن کارت «صلوات پوینت» رو از روی یه نتیجه‌ی award (که از قبل محاسبه
    شده) می‌سازه؛ خودش award صدا نمی‌زنه. این جداسازی لازمه چون تو گروه،
    award همین الان توسط salavat_text_handler انجام شده.
    """
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
            lines.append(f"\n🎊 تبریک! کبوترت رفت سطح {_code(to_persian_digits(result['new_level']))}!")
        return "\n".join(lines)

    if result["reason"] == "cooldown":
        remaining = seconds_until_next(user_id, EVENT_SALAVAT_SENT)
        return f"⏳ صلوات پوینتِ بعدیت {_code(_format_cooldown(remaining))} دیگه آماده می‌شه 🌹"

    if result["reason"] == "daily_cap":
        return "🌙 امروز به سقف صلوات پوینت رسیدی؛ فردا دوباره تلاش کن 🌹"

    return "🌹 صلوات قبول باشه."


def build_salavat_card_from_dispatch(user_id: int, dispatch_result: dict) -> str:
    """نسخه‌ی عمومی برای فراخوانی از handlers/salavat.py تو گروه، بعد از
    این‌که خودشون dispatch_event رو انجام دادن."""
    return _build_salavat_card(user_id, dispatch_result)


def handle_salavat_points(user_id: int) -> str:
    """مسیر پیوی: هیچ سیستم دیگه‌ای قبلش صلوات رو پردازش نکرده، پس خودش
    award_variable_xp رو با یه عدد رندوم صدا می‌زنه و بعد کارت رو می‌سازه."""
    result = award_variable_xp(user_id, EVENT_SALAVAT_SENT, roll_salavat_points())
    return _build_salavat_card(user_id, result)


def set_pigeon_name(user_id: int, name: str) -> str:
    name = name.strip()[:30]
    if not name:
        return "⚠️ اسم نمی‌تونه خالی باشه."
    db.set_pigeon_name(user_id, name)
    return f"🕊️ از این به بعد کبوترت «{name}» صدا زده می‌شه."


def build_pigeon_status_text(user_id: int, display_name: str) -> str:
    """کارت وضعیت کبوتر رو می‌سازه: نام، دون، مقام/سطح، تولید، آماده‌ی
    برداشت، کیف‌پول، و هزینه‌ی اقدام بعدی (ارتقا سطح/مقام)."""
    synced = _sync_production(user_id)
    profile = db.get_profile(user_id)
    state = db.get_pigeon_state(user_id)

    wallet = profile["xp"] if profile else 0
    global_level = synced["global_level"]
    stage = pigeon_stage_info(global_level)
    rate = pigeon_production_rate(global_level)
    capacity = synced["capacity"]
    seed = synced["seed"]
    pending = synced["pending"]
    pigeon_name = state["pigeon_name"] or DEFAULT_PIGEON_NAME

    fridge_level = db.get_fridge_level(user_id)
    fridge_count = db.count_fridge_items(user_id)
    fridge_cap = fridge_capacity(fridge_level)

    if seed >= capacity:
        seed_status = "😋 سیره"
    elif seed >= capacity / 2:
        seed_status = "😐 نیمه‌گرسنه"
    else:
        seed_status = "😟 گرسنه‌ست"

    at_cap = stage["sub_level"] >= stage["cap"]
    if at_cap and not stage["is_last_stage"]:
        next_cost = stage["rank_up_cost"]
        next_label = "ارتقا مقام"
    elif at_cap and stage["is_last_stage"]:
        next_cost = None
        next_label = None
    else:
        next_cost = pigeon_level_up_cost(global_level)
        next_label = "ارتقا سطح"

    wallet_str = to_persian_digits(f"{wallet:,}")
    pending_str = to_persian_digits(f"{int(pending):,}")
    seed_str = to_persian_digits(f"{seed:.1f}".rstrip("0").rstrip("."))

    lines = [
        f"🕊️ کبوتر {display_name}",
        "",
        f"💕 نام: {pigeon_name}",
        f"🌾 دون: {seed_status} ({_code(seed_str)} / {_code(to_persian_digits(capacity))})",
        "",
        f"🌟 مقام: {stage['name']}",
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

    return "\n".join(lines)


def harvest_points(user_id: int) -> str:
    """پوینتِ آماده‌ی برداشت رو (بخش صحیحش) به کیف‌پول اصلی منتقل می‌کنه."""
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
        lines.append(f"🎊 تبریک! رفتی سطح {_code(to_persian_digits(result['new_level']))}!")
    return "\n".join(lines)


def level_up_pigeon(user_id: int) -> str:
    """با خرج از کیف‌پول، سطح کبوتر رو بالا می‌بره (یا اگه به سقف مقام
    رسیده، ارتقا مقام می‌ده)."""
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
        action_label = f"ارتقا مقام به «{next_stage['name']}»"
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
