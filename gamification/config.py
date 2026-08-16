# -*- coding: utf-8 -*-
"""
تنظیمات مرکزی سیستم گیمیفیکیشن.

همه‌ی مقادیر قابل‌تنظیم (XP، سطح‌ها، کول‌داون‌ها، سقف‌های روزانه) اینجا
تعریف می‌شوند تا هیچ‌جای دیگر کد hard-code نشوند. تغییر مقدار XP یک
فعالیت فقط با ویرایش همین فایل انجام می‌شود.
"""

from zoneinfo import ZoneInfo

# منطقه‌ی زمانی مرجع برای محاسبه‌ی «روز» (streak، ریست مأموریت‌های روزانه).
# با بقیه‌ی جاهای پروژه (مثل schedule_daily_prayer_reminders) هماهنگ است.
GAMIFICATION_TIMEZONE = ZoneInfo("Asia/Tehran")


# ---------------------------------------------------------------------------
# انواع رویداد (Event Types)
# ---------------------------------------------------------------------------
# این‌ها به‌عنوان رشته ثابت نگه داشته می‌شوند (نه Enum) تا هم در دیتابیس
# (ستون event_type) خوانا باشند و هم افزودن رویداد جدید نیازی به تغییر
# import در جاهای مختلف نداشته باشد.

EVENT_DAILY_LOGIN = "daily_login"
EVENT_HADITH_VIEWED = "hadith_viewed"
EVENT_QURAN_VIEWED = "quran_viewed"
EVENT_NAHJ_VIEWED = "nahj_viewed"
EVENT_MAFATIH_VIEWED = "mafatih_viewed"
EVENT_QUIZ_STARTED = "quiz_started"
EVENT_QUIZ_CORRECT = "quiz_correct"
EVENT_MISSION_COMPLETE = "mission_complete"
EVENT_SALAVAT_SENT = "salavat_sent"


# ---------------------------------------------------------------------------
# مقدار XP هر فعالیت
# ---------------------------------------------------------------------------
XP_REWARDS = {
    EVENT_DAILY_LOGIN: 10,
    EVENT_HADITH_VIEWED: 5,
    EVENT_QURAN_VIEWED: 5,
    EVENT_NAHJ_VIEWED: 5,
    EVENT_MAFATIH_VIEWED: 5,
    EVENT_QUIZ_STARTED: 3,
    EVENT_QUIZ_CORRECT: 15,
    EVENT_MISSION_COMPLETE: 30,
    # نکته‌ی طراحی مهم: صلوات با بقیه‌ی رویدادها فرق دارد؛ یک پیام می‌تواند
    # عدد دلخواهی (مثلاً «۱۰۰ صلوات») را به شمارنده اضافه کند. اگر XP متناسب
    # با آن عدد داده شود، یعنی هر کاربر می‌تواند با نوشتن یک عدد بزرگ در یک
    # پیام XP نامحدود بگیرد. به همین دلیل XP اینجا فلت و به‌ازای «هر پیامِ
    # واجد شرایط» است، نه به‌ازای مقدار صلوات آن پیام. خودِ شمارنده‌ی واقعی
    # صلوات (برای اهداف مذهبی/ختم‌ها) هرگز محدود یا دستکاری نمی‌شود؛ فقط
    # لایه‌ی XP این سیستم محدود است.
    EVENT_SALAVAT_SENT: 3,
}


# ---------------------------------------------------------------------------
# Anti-Abuse: کول‌داون و سقف روزانه به‌ازای هر نوع رویداد
# ---------------------------------------------------------------------------
# cooldown_seconds: حداقل فاصله‌ی زمانی بین دو بار XP گرفتن برای همون کاربر
#                    و همون نوع رویداد (نه لزوماً همون آیتم).
# daily_cap:         حداکثر تعداد باری که این رویداد در یک شبانه‌روز (به وقت
#                    GAMIFICATION_TIMEZONE) برای یک کاربر XP می‌دهد.
# per_item_cooldown: اگر True باشد، کول‌داون به‌ازای هر آیتم (reference_id)
#                    جداگانه اعمال می‌شود، نه کل نوع رویداد. مثلاً باز کردن
#                    حدیث شماره‌ی ۵ نباید جلوی گرفتن XP از حدیث شماره‌ی ۶ را
#                    بگیرد؛ ولی باز کردن دوباره‌ی همان حدیث ۵ در بازه‌ی کوتاه
#                    نباید XP تکراری بدهد.
ANTI_ABUSE_RULES = {
    EVENT_DAILY_LOGIN: {"cooldown_seconds": 0, "daily_cap": 1, "per_item_cooldown": False},
    EVENT_HADITH_VIEWED: {"cooldown_seconds": 20, "daily_cap": 30, "per_item_cooldown": True},
    EVENT_QURAN_VIEWED: {"cooldown_seconds": 20, "daily_cap": 30, "per_item_cooldown": True},
    EVENT_NAHJ_VIEWED: {"cooldown_seconds": 20, "daily_cap": 20, "per_item_cooldown": True},
    EVENT_MAFATIH_VIEWED: {"cooldown_seconds": 20, "daily_cap": 20, "per_item_cooldown": True},
    EVENT_QUIZ_STARTED: {"cooldown_seconds": 5, "daily_cap": 20, "per_item_cooldown": False},
    EVENT_QUIZ_CORRECT: {"cooldown_seconds": 0, "daily_cap": 50, "per_item_cooldown": False},
    EVENT_MISSION_COMPLETE: {"cooldown_seconds": 0, "daily_cap": 10, "per_item_cooldown": False},
    # صلوات ذاتاً «کلیک تکراری مشروع» است (شمارش صلوات)؛ برخلاف حدیث/آیه که
    # باز کردن مکررش مصنوعی است. پس اینجا per_item_cooldown بی‌معناست (آیتم
    # مشخصی وجود ندارد) و فقط یک کول‌داون کوتاه بین دو پیامِ XP-دهنده و یک
    # سقف روزانه‌ی معقول داریم تا کسی با ارسال دسته‌جمعی و سریع پیام‌های
    # «صلوات» XP نامحدود نگیرد؛ ارسال صلوات بیشتر از سقف همچنان در شمارنده‌ی
    # واقعی صلوات (و ختم‌ها) به‌طور کامل ثبت می‌شود، فقط دیگر XP اضافه نمی‌دهد.
    EVENT_SALAVAT_SENT: {"cooldown_seconds": 45, "daily_cap": 15, "per_item_cooldown": False},
}


# ---------------------------------------------------------------------------
# سیستم Level
# ---------------------------------------------------------------------------
# فرمول: XP لازم برای رسیدن به سطح n = BASE_XP * n^EXPONENT
# این فرمول (توان ۱.۵) نسبت به خطی (کسل‌کننده در سطوح بالا) و نمایی/توان ۲
# (خیلی سریع غیرقابل‌دسترس می‌شود) تعادل بهتری بین «پیشرفت اولیه‌ی سریع
# و انگیزه‌بخش» و «چالش‌برانگیز بودن سطوح بالا» ایجاد می‌کند.
LEVEL_BASE_XP = 50
LEVEL_EXPONENT = 1.5
MAX_LEVEL = 100

# عنوان‌های سطح — با احترام و بدون ادعای مقام معنوی واقعی
LEVEL_TITLES = {
    1: "🌱 آغازگر",
    5: "📖 همراه قرآن",
    10: "📚 جوینده معرفت",
    15: "🕯️ اهل مطالعه",
    20: "🌙 اهل ذکر",
    30: "📿 پویای مسیر",
    40: "🌿 راهجوی معرفت",
    50: "🏛️ طالب معرفت",
    65: "🕌 همراه همیشگی",
    80: "🌟 ستاره‌ی پیشرفت",
    100: "🏆 نمونه‌ی استمرار",
}


def get_level_title(level: int) -> str:
    """عنوان مناسب‌ترین سطحِ کمتر یا مساوی level را برمی‌گرداند."""
    applicable = [lvl for lvl in LEVEL_TITLES if lvl <= level]
    if not applicable:
        return LEVEL_TITLES[1]
    return LEVEL_TITLES[max(applicable)]


# ---------------------------------------------------------------------------
# نقاط عطف Streak (فقط برای نمایش/اعلان، نه محدودیت)
# ---------------------------------------------------------------------------
STREAK_MILESTONES = [1, 3, 7, 14, 30, 60, 100, 365]
