# -*- coding: utf-8 -*-
"""
منطق شخصیت همراه: فرشته 👼  (قبلاً «کبوتر 🕊️» بود؛ این فایل جایگزینِ
gamification/pigeon.py است. اگه هنوز جایی import گامیفیکیشن.pigeon باقی
مونده -- مثلاً handlers/pigeon.py -- باید به gamification.angel و اسم‌های
جدیدِ زیر آپدیت بشه.)

رفتارهای اصلی:
  - نوشتنِ *عینِ کاملِ* یکی از عبارت‌های DHIKR_PHRASES (صلوات یا هرکدوم
    از اذکارِ دیگه) → «نور»ِ تصادفی می‌ده. رنجِ نور دیگه ثابت نیست؛ بر
    اساسِ سطحِ فعلیِ کاربر (angel_feature_level_for_count) از
    DHIKR_LIGHT_REWARD_RANGES/light_reward_range خونده می‌شه. کول‌داون
    ۵ دقیقه‌ست؛ در پیوی مستقیماً award می‌شه، در گروه از طریق
    dispatch_event(xp_override=...) که handlers/salavat.py صداش می‌زنه.
  - فرشته، وقتی سوخت داره، خودش مثل یه ماینر passive نور تولید می‌کنه
    (نرخ تولید به سطح کلی خودش بستگی داره). این پوینت‌ها اول تو یه
    استخر «آماده‌ی برداشت» جمع می‌شن و با دکمه‌ی «برداشت» به کیف‌پول
    اصلی (ستون xp) منتقل می‌شن.
  - کاربر می‌تونه با خرج از کیف‌پول، سطح فرشته رو بالا ببره؛ وقتی سطح به
    سقفِ مقام فعلی رسید، به‌جاش «ارتقا مقام» (هزینه‌ی سنگین‌تر) میاد.
  - سوخت دیگه خودکار از یخچال پر نمی‌شه؛ منطقِ «نذری»/یخچال کامل تو
    gamification/fridge.py هست و از تابع add_seed_to_angel همینجا برای
    «بده فرشته‌ات بخوره» استفاده می‌کنه.

توجه: این ماژول فقط متن آماده برمی‌گرداند؛ ارسال پیام/دکمه به تلگرام در
handlers/angel.py (قبلاً handlers/pigeon.py) انجام می‌شود.
"""

import random
import datetime

from . import db
from .xp import award_variable_xp, grant_bonus_xp, seconds_until_next
from .config import (
    EVENT_SALAVAT_SENT, EVENT_ANGEL_HARVEST,
    ANGEL_RANK_STAGES, ANGEL_FUEL_SECONDS_PER_UNIT, ANGEL_MAX_FEATURE_LEVEL,
    angel_fuel_capacity, angel_stage_info, angel_level_up_cost, angel_production_rate,
    angel_feature_level_for_count, angel_count_for_next_feature_level,
    light_reward_range,
    fridge_capacity,
    get_angel_level_up_message,
)
from text_utils import to_persian_digits, normalize_for_search

DEFAULT_ANGEL_NAME = "فرشته"

# هزینه‌ی تغییرِ اسمِ فرشته (چه از دکمه‌ی «✏️ تغییر نام» چه با نوشتنِ
# مستقیمِ «اسم فرشته‌ام ...») -- هر دو راه از همین یه هزینه/اعتبارسنجی رد
# می‌شن تا یکی‌شون راهِ دورزدنِ اون یکی نشه.
ANGEL_RENAME_COST = 114

# ---------------------------------------------------------------------------
# عبارت‌های کاملِ ذکر/صلوات که «نور» می‌دن
# ---------------------------------------------------------------------------
# نور (چه پیوی چه گروه) فقط وقتی داده می‌شه که کاربر *عینِ کاملِ* یکی از
# این عبارت‌ها رو نوشته باشه، نه فقط بخشی از یکی‌شون یا یه عدد. از
# normalize_for_search استفاده می‌کنیم تا «آل»/«ال»، فاصله‌های اضافه، و
# تفاوت‌های ظاهری عربی/فارسی (رایج تو کیبورد موبایل) مشکلی ایجاد نکنن؛
# ولی همچنان باید عبارت *کامل* باشه، نه بخشی از یه پیام بزرگ‌تر یا کوتاه‌تر.
#
# کلیدِ "salavat" معنای خاصی داره: هم به شمارنده‌ی واقعیِ صلواتِ گروه
# (handlers/salavat.py) اضافه می‌شه، هم پیامِ کارتش عبارتِ «صلوات» رو
# نگه می‌داره. بقیه‌ی کلیدها فقط «ذکر نورانی» حساب می‌شن.
DHIKR_PHRASES = {
    "salavat": "اللهم صل علی محمد و آل محمد",
    "la_ilaha_illallah": "لا اله الا الله",
    "allahu_akbar": "الله اکبر",
    "alhamdulillah": "الحمدلله",
    "astaghfirullah": "استغفرالله",
    "astaghfirullah_full": "استغفرالله ربی و اتوب الیه",
    "subhanallah": "سبحان الله",
}

_DHIKR_NORMALIZED_TO_KEY = {
    normalize_for_search(phrase): key for key, phrase in DHIKR_PHRASES.items()
}


def match_full_dhikr_phrase(text: str):
    """اگه کل پیام (بعد از نرمال‌سازی) دقیقاً یکی از عبارت‌های کاملِ
    DHIKR_PHRASES باشه، کلیدِ همون ذکر رو برمی‌گردونه (مثلاً "salavat"،
    "subhanallah")؛ وگرنه None. هم handlers/angel.py (پیوی) هم
    handlers/salavat.py (گروه) از همین یه تابع استفاده می‌کنن تا رفتار
    یکسان بمونه."""
    return _DHIKR_NORMALIZED_TO_KEY.get(normalize_for_search(text))


def is_full_salavat_phrase(text: str) -> bool:
    """بک‌وارد-کامپتیبل: فقط برای عینِ عبارتِ کاملِ صلوات True برمی‌گردونه.
    برای تشخیصِ بقیه‌ی اذکار از match_full_dhikr_phrase استفاده کن."""
    return match_full_dhikr_phrase(text) == "salavat"


def _format_cooldown(seconds: int) -> str:
    """ثانیه را به شکل mm:ss (با صفرِ ابتداییِ دقیقه) و ارقام فارسی نمایش
    می‌دهد (مثلاً «۰۱:۵۹»)."""
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    minutes_str = to_persian_digits(f"{minutes:02d}")
    secs_str = to_persian_digits(f"{secs:02d}")
    return f"{minutes_str}:{secs_str}"


def _code(value) -> str:
    """مقدار رو بین بک‌تیک می‌ذاره تا تو تلگرام به‌شکل monospace/آبی و
    قابل‌کپی (با یه تپ) نمایش داده بشه. پیام‌هایی که از این استفاده می‌کنن
    باید با parse_mode="Markdown" فرستاده بشن."""
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


def get_current_feature_level(user_id: int) -> int:
    """سطحِ فعلیِ «پیشرفتِ قابلیت‌ها»ی کاربر (۰ تا ۱۴) رو، بر اساسِ
    شمارشِ ذکرِ کاملِ تا همین الان (قبل از این پیام)، برمی‌گردونه. برای
    تعیینِ رنجِ «نور»ِ همین پیام استفاده می‌شه."""
    state = db.get_angel_state(user_id)
    count = state.get("angel_dhikr_count") or 0
    return angel_feature_level_for_count(count)


def roll_light_points(level: int) -> int:
    """یه عدد تصادفیِ «نور» برمی‌گردونه، متناسب با رنجِ سطحِ فعلیِ کاربر."""
    lo, hi = light_reward_range(level)
    return random.randint(lo, hi)


def _sync_production(user_id: int) -> dict:
    """
    از آخرین سینک تا الان، بر اساس سوخت موجود، تولیدِ passive رو حساب
    می‌کنه: تولید رو به angel_pending_points اضافه می‌کنه و سوختِ
    مصرف‌شده رو کم می‌کنه. همیشه قبل از ساختن کارت وضعیت یا برداشت صدا
    زده می‌شه تا اعداد به‌روز باشن.

    توجه: سوخت دیگه خودکار از یخچال پر نمی‌شه -- فقط با «بده فرشته‌ات
    بخوره» (gamification/fridge.py، از طریق add_seed_to_angel همینجا)
    پر می‌شه.
    """
    state = db.get_angel_state(user_id)
    now = _now()
    last = _parse_dt(state.get("angel_last_synced_at")) or now
    elapsed = max(0.0, (now - last).total_seconds())

    global_level = state["angel_global_level"] or 1
    stage = angel_stage_info(global_level)
    seed = float(state["angel_seed"] or 0)
    pending = float(state["angel_pending_points"] or 0)

    capacity = angel_fuel_capacity(global_level)

    if elapsed > 0 and seed > 0:
        # نرخ تولید بر اساس sub_level (سطحِ داخلِ مقامِ فعلی) حساب می‌شه،
        # نه global_level -- چون با هر ارتقا مقام، تولید دوباره از ۰.۱
        # شروع می‌شه (طبق طراحیِ جدید).
        rate = angel_production_rate(stage["sub_level"])
        fuel_seconds = seed * ANGEL_FUEL_SECONDS_PER_UNIT
        active_seconds = min(elapsed, fuel_seconds)
        produced = rate * active_seconds
        seed_used = active_seconds / ANGEL_FUEL_SECONDS_PER_UNIT
        seed = max(0.0, seed - seed_used)
        pending += produced

    db.update_angel_seed_and_pending(user_id, seed=seed, pending=pending, synced_at=now.isoformat())

    return {
        "global_level": global_level,
        "stage": stage,
        "seed": seed,
        "pending": pending,
        "capacity": capacity,
    }


def add_seed_to_angel(user_id: int, amount: float) -> dict:
    """مستقیم مقدار amount رو به سوخت فرشته اضافه می‌کنه (تا سقف ظرفیت)؛
    قبلش سینک می‌کنه تا وضعیت فعلی درست باشه. برای «بده فرشته‌ات بخوره»
    روی آیتم‌های نذری (gamification/fridge.py) استفاده می‌شه."""
    synced = _sync_production(user_id)
    new_seed = min(synced["capacity"], synced["seed"] + amount)
    db.update_angel_seed_and_pending(
        user_id, seed=new_seed, pending=synced["pending"], synced_at=_now().isoformat()
    )
    return {"new_seed": new_seed, "capacity": synced["capacity"]}


def get_angel_name(user_id: int) -> str:
    """اسم فعلی فرشته رو برمی‌گردونه."""
    state = db.get_angel_state(user_id)
    return state.get("angel_name") or DEFAULT_ANGEL_NAME


def get_angel_feature_level(user_id: int) -> int:
    """سطح فعلی «پیشرفت قابلیت‌ها» رو برمی‌گردونه (۰ تا ۱۴)."""
    state = db.get_angel_state(user_id)
    count = state.get("angel_dhikr_count") or 0
    return angel_feature_level_for_count(count)


def get_angel_feature_progress(user_id: int) -> dict:
    """
    اطلاعات کامل پیشرفت قابلیت‌ها رو برمی‌گردونه:
      - count: تعداد ذکر/صلواتِ کامل گفته‌شده
      - level: سطح فعلی (۰ تا ۱۴)
      - next_threshold: آستانه‌ی سطح بعد (یا None اگه به سقف رسیده)
      - remaining: تعداد ذکر باقی‌مونده تا سطح بعد
    """
    state = db.get_angel_state(user_id)
    count = state.get("angel_dhikr_count") or 0
    current_level = angel_feature_level_for_count(count)
    next_threshold = angel_count_for_next_feature_level(current_level)
    return {
        "count": count,
        "level": current_level,
        "next_threshold": next_threshold,
        "remaining": next_threshold - count if next_threshold is not None else 0,
    }


def register_angel_feature_progress(user_id: int) -> dict:
    """
    هر بار که کاربر *عینِ کاملِ* یکی از عبارت‌های DHIKR_PHRASES رو
    می‌نویسه (چه پیوی چه گروه) صدا زده می‌شه: شمارنده‌ی angel_dhikr_count
    رو +۱ می‌کنه و اگه با شمارشِ جدید، سطحِ «پیشرفتِ قابلیت‌ها» (طبقِ
    ANGEL_FEATURE_THRESHOLDS) بالا رفته باشه، خبرش رو برمی‌گردونه.

    توجه مهم: این «سطح» کاملاً جداست از مقام/سطحِ پولیِ فرشته (که با
    خرجِ نور لول‌آپ می‌شه، پایین‌تر تو همین فایل با level_up_angel). این
    یکی فقط تعدادِ دفعاتِ گفتنِ ذکره؛ خودِ سطح تو ستونِ angel_dhikr_count
    محاسبه‌پذیره (نیازی به ستونِ سطحِ جدا نداره). عمداً کاملاً مستقل از
    کول‌داون/سقفِ روزانه‌ی نورِ کیف‌پوله -- شمارش هیچ‌وقت محدود نمی‌شه.
    """
    new_count = db.increment_angel_dhikr_count(user_id, 1)
    old_level = angel_feature_level_for_count(new_count - 1)
    new_level = angel_feature_level_for_count(new_count)
    return {
        "count": new_count,
        "old_level": old_level,
        "new_level": new_level,
        "leveled_up": new_level > old_level,
    }


def _angel_feature_levelup_line(level_result: dict) -> str:
    """پیام تبریک کامل برای وقتی که کاربر به سطح جدیدی می‌رسد."""
    new_level = level_result['new_level']
    return get_angel_level_up_message(new_level)


def _build_dhikr_card(user_id: int, result: dict, kind: str,
                       feature_progress_result: dict | None = None) -> str:
    """
    متن کارتِ «نور» رو از روی یه نتیجه‌ی award (که از قبل محاسبه شده)
    می‌سازه؛ خودش award صدا نمی‌زنه. این جداسازی لازمه چون تو گروه، award
    همین الان توسط salavat_text_handler انجام شده.

    kind: کلیدِ DHIKR_PHRASES ("salavat" یا هرکدوم از بقیه). فقط برای
    انتخابِ متنِ درستِ کارت استفاده می‌شه (صلوات/ذکر)؛ منطقِ award و
    کول‌داون برای همه‌شون یکسانه.

    feature_progress_result اگه داده بشه (خروجیِ
    register_angel_feature_progress)، مستقل از این‌که کیف‌پول award شده
    باشه یا نه (کول‌داون/سقفِ روزانه خورده باشه هم فرقی نداره)، پیامِ
    پیشرفتِ قابلیت‌ها رو اضافه می‌کنه.
    """
    leveled_up_message = None
    if feature_progress_result and feature_progress_result.get("leveled_up"):
        leveled_up_message = _angel_feature_levelup_line(feature_progress_result)

    is_salavat = kind == "salavat"
    noun = "صلوات" if is_salavat else "ذکر"
    title = "📿 صلواتت با موفقیت ثبت شد." if is_salavat else "📿 ذکر نورانی شما با موفقیت ثبت شد."
    closing_line = f"🕊 ادامه بده؛ مسیرت با هر {noun} روشن‌تر می‌شه."

    if result["awarded"]:
        profile = db.get_profile(user_id)
        total = profile["xp"] if profile else result["xp"]
        remaining = seconds_until_next(user_id, EVENT_SALAVAT_SENT)
        total_str = to_persian_digits(f"{total:,}")
        lines = [
            title,
            f"✨ {_code(to_persian_digits(result['xp']))} نور گرفتی!",
            f"💫 نور معنویتت رسید به: {total_str}✨",
            f"⏳ بعد از {_code(_format_cooldown(remaining))} می‌تونی یه {noun} دیگه ثبت کنی.",
            closing_line,
        ]
        if leveled_up_message:
            lines.append("\n" + leveled_up_message)
        return "\n".join(lines)

    if result["reason"] == "cooldown":
        remaining = seconds_until_next(user_id, EVENT_SALAVAT_SENT)
        base = f"⏳ {noun}ِ بعدیت {_code(_format_cooldown(remaining))} دیگه آماده می‌شه 🌹"
        if leveled_up_message:
            return f"{base}\n\n{leveled_up_message}"
        return base

    if result["reason"] == "daily_cap":
        base = "🌙 امروز به سقفِ نور رسیدی؛ فردا دوباره تلاش کن 🌹"
        if leveled_up_message:
            return f"{base}\n\n{leveled_up_message}"
        return base

    base = f"🌹 {noun} قبول باشه."
    if leveled_up_message:
        return f"{base}\n\n{leveled_up_message}"
    return base


def build_dhikr_card_from_dispatch(user_id: int, dispatch_result: dict, kind: str = "salavat") -> str:
    """نسخه‌ی عمومی برای فراخوانی از handlers/salavat.py تو گروه، بعد از
    این‌که خودشون dispatch_event رو انجام دادن. پیشرفتِ قابلیت‌های
    فرشته رو هم همینجا (مستقل از نتیجه‌ی dispatch) ثبت می‌کنه.

    kind رو handlers/salavat.py از match_full_dhikr_phrase می‌گیره و
    پاس می‌ده تا متنِ کارت (صلوات/ذکر) درست انتخاب بشه."""
    progress_result = register_angel_feature_progress(user_id)
    return _build_dhikr_card(user_id, dispatch_result, kind, progress_result)


# بک‌وارد-کامپتیبل: کدهای قدیمی‌ای که هنوز build_salavat_card_from_dispatch
# رو import می‌کنن (بدونِ آپدیت) هم کار کنن؛ رفتارش دقیقاً مثلِ قبل
# (کارتِ صلوات) می‌مونه.
def build_salavat_card_from_dispatch(user_id: int, dispatch_result: dict) -> str:
    return build_dhikr_card_from_dispatch(user_id, dispatch_result, kind="salavat")


def handle_dhikr_points(user_id: int, kind: str = "salavat") -> str:
    """مسیر پیوی: هیچ سیستم دیگه‌ای قبلش ذکر رو پردازش نکرده، پس خودش
    award_variable_xp رو با یه عددِ رندومِ متناسب با سطحِ فعلیِ کاربر صدا
    می‌زنه، پیشرفتِ قابلیت‌های فرشته رو ثبت می‌کنه، و بعد کارت رو می‌سازه.

    kind: کلیدِ DHIKR_PHRASES که handlers/angel.py از
    match_full_dhikr_phrase گرفته و پاس داده."""
    current_level = get_current_feature_level(user_id)
    result = award_variable_xp(user_id, EVENT_SALAVAT_SENT, roll_light_points(current_level))
    progress_result = register_angel_feature_progress(user_id)
    return _build_dhikr_card(user_id, result, kind, progress_result)


# بک‌وارد-کامپتیبل با نامِ قدیمی (فقط برای صلوات).
def handle_salavat_points(user_id: int) -> str:
    return handle_dhikr_points(user_id, kind="salavat")


def _is_valid_angel_name(name: str) -> bool:
    """۳ تا ۲۲ کاراکتر، فقط حروف (فارسی/عربی/انگلیسی و...) و فاصله‌ی
    تکی بینشون؛ بدون عدد، ایموجی، یا هر علامتِ نگارشیِ دیگه."""
    name = name.strip()
    if not (3 <= len(name) <= 22):
        return False
    if "  " in name:  # چند فاصله‌ی پشت‌سرهم مجاز نیست
        return False
    return all(ch.isalpha() for ch in name if ch != " ")


def set_angel_name(user_id: int, name: str) -> str:
    """با پرداختِ ANGEL_RENAME_COST نور از کیف‌پول، اسمِ فرشته رو عوض
    می‌کنه. اسم باید ۳ تا ۲۲ کاراکتر، فقط حروف و فاصله باشه (بدون عدد،
    ایموجی، یا علامتِ نگارشی)."""
    name = name.strip()
    if not _is_valid_angel_name(name):
        return (
            "⚠️ اسم باید بینِ ۳ تا ۲۲ کاراکتر و فقط از حروف و فاصله تشکیل شده باشه "
            "(بدون عدد، ایموجی، یا علامتِ نگارشی)."
        )

    profile = db.get_profile(user_id)
    wallet = profile["xp"] if profile else 0
    if wallet < ANGEL_RENAME_COST:
        missing = ANGEL_RENAME_COST - wallet
        return (
            f"💰 برای تغییرِ اسم به {_code(to_persian_digits(ANGEL_RENAME_COST))} نور نیاز داری.\n"
            f"هنوز {_code(to_persian_digits(missing))} نور کم داری."
        )

    if not db.spend_points(user_id, ANGEL_RENAME_COST):
        return "⚠️ مشکلی پیش اومد (شاید موجودیت تغییر کرده)، دوباره امتحان کن."

    db.set_angel_name(user_id, name)
    return f"👼 از این به بعد فرشته‌ات «{name}» صدا زده می‌شه."


def build_angel_status_text(user_id: int, display_name: str) -> str:
    """کارت وضعیت فرشته رو می‌سازه: نام، شکم، مقام/سطح (پولی)، تولید،
    آماده‌ی برداشت، کیف‌پول، هزینه‌ی اقدامِ بعدی، و پیشرفتِ قابلیت‌ها
    (شمارشِ ذکر، کاملاً جدا از مقام)."""
    synced = _sync_production(user_id)
    profile = db.get_profile(user_id)
    state = db.get_angel_state(user_id)

    wallet = profile["xp"] if profile else 0
    global_level = synced["global_level"]
    stage = synced["stage"]
    rate = angel_production_rate(stage["sub_level"])
    capacity = synced["capacity"]
    seed = synced["seed"]
    pending = synced["pending"]
    angel_name = state["angel_name"] or DEFAULT_ANGEL_NAME
    dhikr_count = state.get("angel_dhikr_count") or 0

    fridge_level = db.get_fridge_level(user_id)
    fridge_count = db.count_fridge_items(user_id)
    fridge_cap = fridge_capacity(fridge_level)

    # وضعیت شکم (قبلاً: دون)
    if seed >= capacity:
        seed_status = "😋 سیر"
    elif seed >= capacity / 2:
        seed_status = "😐 نیمه‌سیر"
    else:
        seed_status = "😟 گرسنه"

    at_cap = stage["sub_level"] >= stage["cap"]
    if at_cap and not stage["is_last_stage"]:
        next_cost = stage["rank_up_cost"]
        next_label = "ارتقا فرشته"
    elif at_cap and stage["is_last_stage"]:
        next_cost = None
        next_label = None
    else:
        next_cost = angel_level_up_cost(global_level)
        next_label = "ارتقا سطح"

    feature_level = angel_feature_level_for_count(dhikr_count)
    next_feature_threshold = angel_count_for_next_feature_level(feature_level)

    wallet_str = to_persian_digits(f"{wallet:,}")
    pending_str = to_persian_digits(f"{int(pending):,}")
    seed_str = to_persian_digits(f"{seed:.1f}".rstrip("0").rstrip("."))
    feature_level_str = to_persian_digits(feature_level)

    lines = [
        f"👼 فرشته‌ی {display_name}",
        "",
        f"💕 نام: {angel_name}",
        f"🍽️ شکم: {seed_status} ({_code(seed_str)} / {_code(to_persian_digits(capacity))})",
        "",
        f"🌟 مقام {_code(to_persian_digits(stage['stage_number']))}: {stage['name']}",
        f"⭐️ سطح: {_code(to_persian_digits(stage['sub_level']))} / {_code(to_persian_digits(stage['cap']))}",
        "",
        f"💰 نور: {_code(wallet_str)} ✨",
        f"💫 تولید در ثانیه: {_code(_fmt_rate(rate))} ✨",
        f"📥 آماده‌ی برداشت: {_code(pending_str)} ✨",
        f"❄️ یخچال: {_code(to_persian_digits(fridge_count))} / {_code(to_persian_digits(fridge_cap))} (با «یخچالم» ببینش)",
    ]

    if next_cost is not None:
        cost_str = to_persian_digits(f"{next_cost:,}")
        lines.append(f"💰 هزینه‌ی {next_label}: {_code(cost_str)} ✨")
    else:
        lines.append("👑 فرشته‌ات به بالاترین مقام و سطح رسیده!")

    # این بخش کاملاً جدا از مقام/سطحِ بالاست -- فقط با گفتنِ عینِ ذکر
    # پیشرفت می‌کنه، به پول/تولید هیچ ربطی نداره.
    lines.append("")
    lines.append(f"🔓 پیشرفتِ قابلیت‌ها: {_code(feature_level_str)} / {_code(to_persian_digits(ANGEL_MAX_FEATURE_LEVEL))}")
    if next_feature_threshold is not None:
        remaining = max(0, next_feature_threshold - dhikr_count)
        lines.append(
            f"🤲 تا سطحِ بعدِ قابلیت‌ها: {_code(to_persian_digits(remaining))} ذکرِ کامل دیگه بگو "
            f"(مثلاً «اللهم صل علی محمد و آل محمد» یا «سبحان الله»)"
        )
    else:
        lines.append("🔓 پیشرفتِ قابلیت‌ها به سقف رسیده!")

    return "\n".join(lines)


def harvest_points(user_id: int) -> str:
    """پوینتِ آماده‌ی برداشت رو (بخش صحیحش) به کیف‌پول اصلی منتقل می‌کنه."""
    synced = _sync_production(user_id)
    pending = synced["pending"]
    harvest_amount = int(pending)

    if harvest_amount <= 0:
        return "⏳ هنوز چیزی برای برداشت جمع نشده؛ یکم صبر کن یا با «نذری» بهش سوخت بده 👼"

    now = _now()
    idem_key = f"{user_id}:angel_harvest:{int(now.timestamp())}"
    result = grant_bonus_xp(
        user_id, harvest_amount, EVENT_ANGEL_HARVEST,
        reference_id=str(int(now.timestamp())), idempotency_key=idem_key,
    )
    if not result["awarded"]:
        return "⚠️ مشکلی توی برداشت پیش اومد، دوباره امتحان کن."

    leftover = pending - harvest_amount
    db.set_angel_pending(user_id, leftover)

    amount_str = to_persian_digits(f"{harvest_amount:,}")
    lines = [f"📥 {_code(amount_str)} نور برداشت کردی و به کیف‌پولت اضافه شد!"]
    return "\n".join(lines)


def level_up_angel(user_id: int) -> str:
    """با خرج از کیف‌پول، سطحِ فرشته رو بالا می‌بره (یا اگه به سقفِ مقام
    رسیده، «ارتقا فرشته» می‌ده: اسمِ مقام عوض می‌شه، سطح و تولید ریست
    می‌شه)."""
    profile = db.get_profile(user_id)
    wallet = profile["xp"] if profile else 0
    state = db.get_angel_state(user_id)
    global_level = state["angel_global_level"] or 1
    stage = angel_stage_info(global_level)

    at_cap = stage["sub_level"] >= stage["cap"]

    if at_cap and stage["is_last_stage"]:
        return "👑 فرشته‌ات همین الان تو بالاترین مقام و سطح ممکنه!"

    if at_cap:
        cost = stage["rank_up_cost"]
        next_stage = ANGEL_RANK_STAGES[stage["stage_index"] + 1]
        action_label = f"ارتقا فرشته به «{next_stage['name']}»"
    else:
        cost = angel_level_up_cost(global_level)
        action_label = "ارتقا سطح"

    if wallet < cost:
        missing = cost - wallet
        return (
            f"💰 برای {action_label} به {_code(to_persian_digits(f'{cost:,}'))} نور نیاز داری.\n"
            f"هنوز {_code(to_persian_digits(f'{missing:,}'))} نور کم داری."
        )

    if not db.spend_points(user_id, cost):
        return "⚠️ مشکلی پیش اومد (شاید موجودیت تغییر کرده)، دوباره امتحان کن."

    new_level = global_level + 1
    db.set_angel_level(user_id, new_level)
    new_stage = angel_stage_info(new_level)

    if new_stage["stage_index"] != stage["stage_index"]:
        return f"🎉 مبارکه! فرشته‌ات الان شد «{new_stage['name']}»!"
    return f"⬆️ فرشته‌ات رفت سطح {_code(to_persian_digits(new_stage['sub_level']))} / {_code(to_persian_digits(new_stage['cap']))}!"
