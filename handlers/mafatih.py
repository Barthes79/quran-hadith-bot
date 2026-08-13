import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaAudio
from telegram.ext import ContextTypes
import database as db
from text_utils import to_persian_digits

logger = logging.getLogger(__name__)

# ==========================================
# 1. کیبوردها (Keyboards)
# ==========================================
def get_main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗓️ تعقیبات و اعمال هفته", callback_data="mafcat_daily_weekly")],
        [InlineKeyboardButton("🤲 ادعیه و مناجات‌های مشهور", callback_data="mafcat_famous_supplications")],
        [InlineKeyboardButton("🌙 اعمال ماه‌های سال", callback_data="mafcat_lunar_months")],
        [InlineKeyboardButton("🕌 زیارات و عتبات", callback_data="mafcat_ziyarats")],
        [InlineKeyboardButton("📚 باقیات صالحات و ملحقات", callback_data="mafcat_appendices_baqiyat")],
        [InlineKeyboardButton("🔍 جستجو در مفاتیح‌الجنان", callback_data="search_start_mafatih")],
        [InlineKeyboardButton("🏠 بازگشت به خانه", callback_data="menu_main")]
    ])

# --- کیبوردهای دسته‌بندی‌ها ---
def get_keyboard_for_daily_weekly():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧎 تعقیبات نمازها", callback_data="mafsub_post_prayers")],
        [InlineKeyboardButton("📅 دعاهای روزهای هفته", callback_data="mafsub_weekly_days")],
        [InlineKeyboardButton("✨ اعمال شب و روز جمعه", callback_data="mafsub_friday_deeds")],
        [InlineKeyboardButton("🏠 منوی اصلی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_famous_supplications():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ دعاهای معروف", callback_data="mafsub_famous_duas")],
        [InlineKeyboardButton("💬 مناجات‌های خمس عشرة", callback_data="mafsub_khams_ashar")],
        [InlineKeyboardButton("🏠 منوی اصلی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_lunar_months():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🕋 اعمال ماه رجب", callback_data="mafsub_month_rajab")],
        [InlineKeyboardButton("🌸 اعمال ماه شعبان", callback_data="mafsub_month_shaban")],
        [InlineKeyboardButton("🌙 اعمال ماه مبارک رمضان", callback_data="mafsub_month_ramadan")],
        [InlineKeyboardButton("🍂 سایر ماه‌های سال", callback_data="mafsub_other_months")],
        [InlineKeyboardButton("🏠 منوی اصلی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_ziyarats():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌴 زیارات مدینه و بقیع", callback_data="mafsub_medina_ziyarat")],
        [InlineKeyboardButton("⚔️ زیارات عراق (نجف و کربلا)", callback_data="mafsub_karbala_najaf")],
        [InlineKeyboardButton("🕌 اعمال مساجد شریفه", callback_data="mafsub_mosques_deeds")],
        [InlineKeyboardButton("🕌 زیارات ایران (مشهد و ری)", callback_data="mafsub_iran_ziyarats")],
        [InlineKeyboardButton("🏠 منوی اصلی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_appendices_baqiyat():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧎 نمازهای مستحب", callback_data="mafsub_recommended_prayers")],
        [InlineKeyboardButton("💊 ادعیه درمان و بیماری", callback_data="mafsub_sickness_healing")],
        [InlineKeyboardButton("🏠 منوی اصلی مفاتیح", callback_data="mafmenu")]
    ])

# --- کیبوردهای زیردسته‌ها (لیست ادعیه) ---
def get_keyboard_for_post_prayers():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤲 مشترک", callback_data="mafitem_common_post_prayer"), InlineKeyboardButton("🌅 صبح", callback_data="mafitem_subh_post")],
        [InlineKeyboardButton("☀️ ظهر", callback_data="mafitem_zohr_post"), InlineKeyboardButton("🌤️ عصر", callback_data="mafitem_asr_post")],
        [InlineKeyboardButton("🌌 مغرب", callback_data="mafitem_maghrib_post"), InlineKeyboardButton("🌃 عشاء", callback_data="mafitem_isha_post")],
        [InlineKeyboardButton("🙇 سجده شکر", callback_data="mafitem_sajda_shukr")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_daily_weekly"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_weekly_days():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("شنبه", callback_data="mafitem_85"), InlineKeyboardButton("یکشنبه", callback_data="mafitem_86")],
        [InlineKeyboardButton("دوشنبه", callback_data="mafitem_87"), InlineKeyboardButton("سه‌شنبه", callback_data="mafitem_88")],
        [InlineKeyboardButton("چهارشنبه", callback_data="mafitem_89"), InlineKeyboardButton("پنج‌شنبه", callback_data="mafitem_90")],
        [InlineKeyboardButton("جمعه", callback_data="mafitem_91")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_daily_weekly"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_friday_deeds():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌌 اعمال شب جمعه", callback_data="mafitem_friday_night_deeds"), InlineKeyboardButton("☀️ اعمال روز جمعه", callback_data="mafitem_day_friday")],
        [InlineKeyboardButton("📿 صلوات ضراب اصفهانی", callback_data="mafitem_durrab_esfahani")],
        [InlineKeyboardButton("⛪ نماز حضرت رسول", callback_data="mafitem_namaz_prophet_friday"), InlineKeyboardButton("⚔️ نماز امیرالمؤمنین", callback_data="mafitem_namaz_ali_friday")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_daily_weekly"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_famous_duas():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 کمیل", callback_data="mafitem_kumayl"), InlineKeyboardButton("🔵 توسل", callback_data="mafitem_tavassul")],
        [InlineKeyboardButton("🔶 جوشن کبیر", callback_data="mafitem_joshan_kabir"), InlineKeyboardButton("🔷 جوشن صغیر", callback_data="mafitem_joshan_saghir")],
        [InlineKeyboardButton("📖 یستشیر", callback_data="mafitem_yastashir"), InlineKeyboardButton("🥀 مشلول", callback_data="mafitem_mashlool")],
        [InlineKeyboardButton("🌅 سمات", callback_data="mafitem_simat"), InlineKeyboardButton("☀️ صباح", callback_data="mafitem_sabah")],
        [InlineKeyboardButton("📿 عشرات", callback_data="mafitem_asharat"), InlineKeyboardButton("🔥 مجیر", callback_data="mafitem_mojir")],
        [InlineKeyboardButton("⛪ عدیله", callback_data="mafitem_adilah"), InlineKeyboardButton("🌟 فرج", callback_data="mafitem_faraj")],
        [InlineKeyboardButton("⚔️ قاموس", callback_data="mafitem_dua_qamus"), InlineKeyboardButton("⚡ سریع الاجابه", callback_data="mafitem_dua_sari_al_ijabah")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_famous_supplications"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_khams_ashar():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("۱. تائبین", callback_data="mafitem_monajat_taebin"), InlineKeyboardButton("۲. شاکین", callback_data="mafitem_monajat_shakin")],
        [InlineKeyboardButton("۳. خائفین", callback_data="mafitem_monajat_khaefin"), InlineKeyboardButton("۴. راجین", callback_data="mafitem_monajat_rajeen")],
        [InlineKeyboardButton("۵. راغبین", callback_data="mafitem_monajat_raghebin"), InlineKeyboardButton("۶. شاکرین", callback_data="mafitem_monajat_shakerin")],
        [InlineKeyboardButton("۷. مطیعین", callback_data="mafitem_monajat_mutieen"), InlineKeyboardButton("۸. مریدین", callback_data="mafitem_monajat_moridin")],
        [InlineKeyboardButton("۹. محبین", callback_data="mafitem_monajat_mohibbin"), InlineKeyboardButton("۱۰. متوسلین", callback_data="mafitem_monajat_motavasselin")],
        [InlineKeyboardButton("۱۱. مفتقرین", callback_data="mafitem_monajat_moftaqerin"), InlineKeyboardButton("۱۲. عارفین", callback_data="mafitem_monajat_arefin")],
        [InlineKeyboardButton("۱۳. ذاکرین", callback_data="mafitem_monajat_zakerin"), InlineKeyboardButton("۱۴. معتصمین", callback_data="mafitem_monajat_motasemin")],
        [InlineKeyboardButton("۱۵. زاهدین", callback_data="mafitem_monajat_zahedin"), InlineKeyboardButton("📜 منظومه", callback_data="mafitem_monajat_manzoumeh")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_famous_supplications"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_month_rajab():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤲 اعمال مشترک رجب", callback_data="mafitem_rajab_common")],
        [InlineKeyboardButton("✨ لیلة الرغائب", callback_data="mafitem_laylat_raghaeb"), InlineKeyboardButton("☀️ روز مبعث", callback_data="mafitem_rajab_27")],
        [InlineKeyboardButton("📖 اعمال ام داوود", callback_data="mafitem_umm_dawud")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_lunar_months"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_month_shaban():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤲 اعمال مشترک شعبان", callback_data="mafitem_shaban_common"), InlineKeyboardButton("💬 مناجات شعبانیه", callback_data="mafitem_munajat_shabaniyah")],
        [InlineKeyboardButton("✨ اعمال نیمه شعبان", callback_data="mafitem_mid_shaban")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_lunar_months"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_month_ramadan():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌅 اعمال سحر", callback_data="mafitem_ramadan_sahar"), InlineKeyboardButton("📖 دعای ابوحمزه", callback_data="mafitem_abu_hamzah")],
        [InlineKeyboardButton("🛡️ شب‌های قدر", callback_data="mafsub_laylat_alqadr"), InlineKeyboardButton("📅 دعای روزانه", callback_data="mafsub_ramadan_days")],
        [InlineKeyboardButton("👑 دعای افتتاح", callback_data="mafitem_dua_iftitah")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_lunar_months"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_laylat_alqadr():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌙 اعمال شب قدر ۱۹", callback_data="mafitem_qadr_19")],
        [InlineKeyboardButton("🌙 اعمال شب قدر ۲۱", callback_data="mafitem_qadr_21")],
        [InlineKeyboardButton("🌙 اعمال شب قدر ۲۳", callback_data="mafitem_qadr_23")],
        [InlineKeyboardButton("🤝 اعمال مشترک شب قدر", callback_data="mafitem_qadr_common")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafsub_month_ramadan"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_ramadan_days():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 روز ۱", callback_data="mafitem_ramadan_day_1"), InlineKeyboardButton("📅 روز ۲", callback_data="mafitem_ramadan_day_2"), InlineKeyboardButton("📅 روز ۳", callback_data="mafitem_ramadan_day_3")],
        [InlineKeyboardButton("📅 روز ۴", callback_data="mafitem_ramadan_day_4"), InlineKeyboardButton("📅 روز ۵", callback_data="mafitem_ramadan_day_5"), InlineKeyboardButton("📅 روز ۶", callback_data="mafitem_ramadan_day_6")],
        [InlineKeyboardButton("📅 روز ۷", callback_data="mafitem_ramadan_day_7"), InlineKeyboardButton("📅 روز ۸", callback_data="mafitem_ramadan_day_8"), InlineKeyboardButton("📅 روز ۹", callback_data="mafitem_ramadan_day_9")],
        [InlineKeyboardButton("📅 روز ۱۰", callback_data="mafitem_ramadan_day_10"), InlineKeyboardButton("📅 روز ۱۱", callback_data="mafitem_ramadan_day_11"), InlineKeyboardButton("📅 روز ۱۲", callback_data="mafitem_ramadan_day_12")],
        [InlineKeyboardButton("📅 روز ۱۳", callback_data="mafitem_ramadan_day_13"), InlineKeyboardButton("📅 روز ۱۴", callback_data="mafitem_ramadan_day_14"), InlineKeyboardButton("📅 روز ۱۵", callback_data="mafitem_ramadan_day_15")],
        [InlineKeyboardButton("📅 روز ۱۶", callback_data="mafitem_ramadan_day_16"), InlineKeyboardButton("📅 روز ۱۷", callback_data="mafitem_ramadan_day_17"), InlineKeyboardButton("📅 روز ۱۸", callback_data="mafitem_ramadan_day_18")],
        [InlineKeyboardButton("📅 روز ۱۹", callback_data="mafitem_ramadan_day_19"), InlineKeyboardButton("📅 روز ۲۰", callback_data="mafitem_ramadan_day_20"), InlineKeyboardButton("📅 روز ۲۱", callback_data="mafitem_ramadan_day_21")],
        [InlineKeyboardButton("📅 روز ۲۲", callback_data="mafitem_ramadan_day_22"), InlineKeyboardButton("📅 روز ۲۳", callback_data="mafitem_ramadan_day_23"), InlineKeyboardButton("📅 روز ۲۴", callback_data="mafitem_ramadan_day_24")],
        [InlineKeyboardButton("📅 روز ۲۵", callback_data="mafitem_ramadan_day_25"), InlineKeyboardButton("📅 روز ۲۶", callback_data="mafitem_ramadan_day_26"), InlineKeyboardButton("📅 روز ۲۷", callback_data="mafitem_ramadan_day_27")],
        [InlineKeyboardButton("📅 روز ۲۸", callback_data="mafitem_ramadan_day_28"), InlineKeyboardButton("📅 روز ۲۹", callback_data="mafitem_ramadan_day_29"), InlineKeyboardButton("📅 روز ۳۰", callback_data="mafitem_ramadan_day_30")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafsub_month_ramadan"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_other_months():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌍 دحوالارض", callback_data="mafitem_dahw_al_ard"), InlineKeyboardButton("⛰️ روز عرفه", callback_data="mafitem_arafah_deeds")],
        [InlineKeyboardButton("👑 عید غدیر خم", callback_data="mafitem_ghadir_day"), InlineKeyboardButton("🏴 دهه اول محرم", callback_data="mafitem_muharram_ashura")],
        [InlineKeyboardButton("👣 اعمال اربعین", callback_data="mafitem_arbaeen_deeds")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_lunar_months"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_medina_ziyarat():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💚 پیامبر (ص)", callback_data="mafitem_prophet_ziyarat"), InlineKeyboardButton("🌸 حضرت زهرا (س)", callback_data="mafitem_fatima_ziyarat")],
        [InlineKeyboardButton("🕌 ائمه بقیع", callback_data="mafitem_baqi_imams"), InlineKeyboardButton("⛰️ شهدای احد", callback_data="mafitem_uhud_martyrs")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_ziyarats"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_karbala_najaf():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛡️ زیارت امین الله", callback_data="mafitem_aminullah"), InlineKeyboardButton("🏴 زیارت عاشورا", callback_data="mafitem_ashura")],
        [InlineKeyboardButton("👣 زیارت اربعین", callback_data="mafitem_arbaeen_deeds"), InlineKeyboardButton("📜 زیارت وارث", callback_data="mafitem_warith_ziyarat")],
        [InlineKeyboardButton("👑 زیارت جامعه کبیره", callback_data="mafitem_jameah_kabirah"), InlineKeyboardButton("🛡️ حضرت عباس (ع)", callback_data="mafitem_abbas_ziyarat")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_ziyarats"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_mosques_deeds():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏛️ مسجد کوفه", callback_data="mafitem_kufa_mosque"), InlineKeyboardButton("🕌 مسجد سهله", callback_data="mafitem_sahla_mosque")],
        [InlineKeyboardButton("⛪ مسجد زید", callback_data="mafitem_zayd_mosque"), InlineKeyboardButton("🗡️زیارت مسلم", callback_data="mafitem_muslim_ziyarat")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_ziyarats"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_iran_ziyarats():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💛 امام رضا (ع)", callback_data="mafitem_reza_ziyarat"), InlineKeyboardButton("👑 شاهزاده عبدالعظیم", callback_data="mafitem_abdul_azim")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_ziyarats"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_recommended_prayers():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌌 نماز شب", callback_data="mafitem_namaz_shab"), InlineKeyboardButton("🕊️ نماز جعفر طیار", callback_data="mafitem_namaz_jafar")],
        [InlineKeyboardButton("🕯️ لیلة الدفن", callback_data="mafitem_namaz_laylat_aldafn"), InlineKeyboardButton("👨‍👩‍👦 نماز والدین", callback_data="mafitem_namaz_parents")],
        [InlineKeyboardButton("📝 استخاره ذات الرقاع", callback_data="mafitem_namaz_istikhareh"), InlineKeyboardButton("🤲 نماز حاجت", callback_data="mafitem_namaz_hajjat")],
        [InlineKeyboardButton("👑 نماز امام زمان (عج)", callback_data="mafitem_namaz_hujjat")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_appendices_baqiyat"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_sickness_healing():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🩺 دعای شفای بیمار", callback_data="mafitem_sickness_dua"), InlineKeyboardButton("🛡️ رفع چشم‌زخم", callback_data="mafitem_hasad_eye")],
        [InlineKeyboardButton("💰 رزق و روزی", callback_data="mafitem_rizq_dua"), InlineKeyboardButton("🛌 خواب و بیداری", callback_data="mafitem_sleep_duas")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_appendices_baqiyat"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

# ==========================================
# 2. دیکشنری‌های مسیریابی (Routing Maps)
# ==========================================
CAT_KEYBOARDS = {
    "daily_weekly": get_keyboard_for_daily_weekly,
    "famous_supplications": get_keyboard_for_famous_supplications,
    "lunar_months": get_keyboard_for_lunar_months,
    "ziyarats": get_keyboard_for_ziyarats,
    "appendices_baqiyat": get_keyboard_for_appendices_baqiyat
}

SUB_KEYBOARDS = {
    "post_prayers": get_keyboard_for_post_prayers,
    "weekly_days": get_keyboard_for_weekly_days,
    "friday_deeds": get_keyboard_for_friday_deeds,
    "famous_duas": get_keyboard_for_famous_duas,
    "khams_ashar": get_keyboard_for_khams_ashar,
    "month_rajab": get_keyboard_for_month_rajab,
    "month_shaban": get_keyboard_for_month_shaban,
    "month_ramadan": get_keyboard_for_month_ramadan,
    "other_months": get_keyboard_for_other_months,
    "laylat_alqadr": get_keyboard_for_laylat_alqadr,
    "ramadan_days": get_keyboard_for_ramadan_days,
    "medina_ziyarat": get_keyboard_for_medina_ziyarat,
    "karbala_najaf": get_keyboard_for_karbala_najaf,
    "mosques_deeds": get_keyboard_for_mosques_deeds,
    "iran_ziyarats": get_keyboard_for_iran_ziyarats,
    "recommended_prayers": get_keyboard_for_recommended_prayers,
    "sickness_healing": get_keyboard_for_sickness_healing
}

def build_mafatih_item_location_map():
    """
    نگاشت شناسه‌ی هر آیتم مفاتیح (همان چیزی که در callback_data به‌شکل
    mafitem_<شناسه> استفاده می‌شود، مثل mafitem_kumayl یا mafitem_85) به
    مسیر واقعی‌اش در منو (برچسب دسته‌ی اصلی + برچسب زیردسته).

    برخلاف ستون category در دیتابیس (که فقط ۶ مقدار کلی دارد و لزوماً با
    ساختار واقعی منو یکی نیست)، این نگاشت مستقیماً از روی خودِ دکمه‌های
    منو ساخته می‌شود؛ یعنی همیشه دقیقاً همان چیزی را نشان می‌دهد که کاربر
    واقعاً در منو می‌بیند، و اگر بعداً زیردسته یا آیتم جدیدی اضافه شود،
    خودکار به‌روز می‌ماند.
    """
    top_labels = {}
    for row in get_main_menu_keyboard().inline_keyboard:
        for btn in row:
            if btn.callback_data and btn.callback_data.startswith("mafcat_"):
                top_labels[btn.callback_data[len("mafcat_"):]] = btn.text

    sub_info = {}  # mafsub_key -> (sub_label, top_label)
    for cat_key, cat_fn in CAT_KEYBOARDS.items():
        top_label = top_labels.get(cat_key, "")
        try:
            keyboard = cat_fn()
        except Exception:
            logger.exception(f"MAFATIH MENU BUILD ERROR (category={cat_key})")
            continue
        for row in keyboard.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("mafsub_"):
                    sub_key = btn.callback_data[len("mafsub_"):]
                    sub_info[sub_key] = (btn.text, top_label)

    location = {}
    for sub_key, sub_fn in SUB_KEYBOARDS.items():
        sub_label, top_label = sub_info.get(sub_key, ("", ""))
        try:
            keyboard = sub_fn()
        except Exception:
            # اگر یک زیردسته به هر دلیلی (مثلاً باگ در تعریف دکمه‌ها) خطا داد،
            # کل نگاشت را خراب نکند؛ فقط همان زیردسته را رد کن.
            logger.exception(f"MAFATIH MENU BUILD ERROR (subcategory={sub_key})")
            continue
        for row in keyboard.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("mafitem_"):
                    identifier = btn.callback_data[len("mafitem_"):]
                    location[identifier] = (top_label, sub_label)

    return location


MAFATIH_ITEM_LOCATION = build_mafatih_item_location_map()


# ==========================================
# 3. هندلرها (Handlers)
# ==========================================

async def safe_edit_message(query, text, reply_markup=None, parse_mode=None):
    """
    ویرایش امن پیام.
    اگر پیام فعلی از نوع عکس باشد (مثلاً کاربر تازه یک دعای عکس‌دار را دیده)،
    edit_message_text با خطا مواجه می‌شود چون تلگرام اجازه تبدیل پیام عکس‌دار
    به پیام متنی را نمی‌دهد. در این حالت پیام قبلی حذف و یک پیام متنی جدید فرستاده می‌شود.
    """
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            logger.exception("safe_edit_message: خطا در حذف پیام قبلی")
        await query.message.chat.send_message(text, reply_markup=reply_markup, parse_mode=parse_mode)

async def cleanup_extra_photo(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """
    وقتی ترجمه‌ی یک دعا طولانی بوده، عکس و متن آن در دو پیام جدا فرستاده شده
    (عکس بدون دکمه، متن با دکمه). این تابع آن عکسِ بدون دکمه را -در صورت وجود- پاک می‌کند
    تا هنگام برگشت به منو یا رفتن به بخش دیگر، عکس یتیم روی صفحه باقی نماند.
    """
    photo_msg_id = context.user_data.pop("maf_extra_photo_id", None)
    if photo_msg_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=photo_msg_id)
        except Exception:
            logger.exception("cleanup_extra_photo: خطا در حذف عکس اضافی")

    audio_msg_id = context.user_data.pop("maf_extra_audio_id", None)
    if audio_msg_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=audio_msg_id)
        except Exception:
            logger.exception("cleanup_extra_photo: خطا در حذف فایل صوتی اضافی")

async def mafatih_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.message:
        await cleanup_extra_photo(context, query.message.chat.id)
    text = "📖 *بخش مفاتیح الجنان*\n\nلطفاً دسته‌بندی مورد نظر خود را انتخاب کنید:"
    await safe_edit_message(query, text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

async def mafatih_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await cleanup_extra_photo(context, query.message.chat.id)
    
    # mafcat_daily_weekly -> daily_weekly
    cat_id = query.data.replace("mafcat_", "")
    
    kb_func = CAT_KEYBOARDS.get(cat_id)
    if kb_func:
        await safe_edit_message(query, "📂 لطفاً زیردسته مورد نظر را انتخاب کنید:", reply_markup=kb_func())

async def mafatih_subcategory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await cleanup_extra_photo(context, query.message.chat.id)
    
    # mafsub_post_prayers -> post_prayers
    sub_id = query.data.replace("mafsub_", "")
    
    kb_func = SUB_KEYBOARDS.get(sub_id)
    if kb_func:
        await safe_edit_message(query, "📜 لطفاً دعای مورد نظر را انتخاب کنید:", reply_markup=kb_func())

# ==========================================
# 3.5. صفحه‌بندی متون طولانی (دکمه «ادامه ▶️»)
# ==========================================
MAF_TEXT_CHUNK_SIZE = 3500


def _split_maf_text(full_text: str, chunk_size: int = MAF_TEXT_CHUNK_SIZE):
    """متن را بدون شکستن وسط پاراگراف/کلمه به تکه‌های قابل نمایش در تلگرام تقسیم می‌کند."""
    if len(full_text) <= chunk_size:
        return [full_text]

    paragraphs = full_text.split("\n")
    chunks = []
    current = ""

    def flush():
        nonlocal current
        if current:
            chunks.append(current.strip("\n"))
            current = ""

    for para in paragraphs:
        candidate = (current + "\n" + para) if current else para
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        flush()
        if len(para) <= chunk_size:
            current = para
        else:
            words = para.split(" ")
            piece = ""
            for word in words:
                cand = (piece + " " + word) if piece else word
                if len(cand) <= chunk_size:
                    piece = cand
                else:
                    if piece:
                        chunks.append(piece)
                    piece = word
            if piece:
                current = piece
    flush()
    return chunks or [full_text]


def build_mafatih_pages(item):
    """آیتم دیتابیس را به هدر + لیستی از تکه‌های متنی تبدیل می‌کند."""
    title = item["title"]
    header = f"✨ {title}\n\n"

    body_parts = []
    if item["arabic_text"]:
        body_parts.append(item["arabic_text"])
    if item["translation_text"]:
        body_parts.append(f"📖 ترجمه:\n{item['translation_text']}")
    if item["tafsir_text"]:
        body_parts.append(f"💡 توضیحات:\n{item['tafsir_text']}")

    full_body = "\n\n".join(body_parts)
    chunks = _split_maf_text(full_body)
    return header, chunks


def mafatih_item_keyboard(item_id, page: int = 0, total_pages: int = 1, has_audio: bool = False):
    buttons = []
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ صفحه قبل", callback_data=f"maftxt_{item_id}_{page-1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("صفحه بعد ▶️", callback_data=f"maftxt_{item_id}_{page+1}"))
        if nav_row:
            buttons.append(nav_row)
    if has_audio:
        buttons.append([InlineKeyboardButton("🎧 فایل صوتی این دعا", callback_data=f"mafaudio_{item_id}")])
    buttons.append([InlineKeyboardButton("⭐ افزودن به علاقه‌مندی‌ها", callback_data=f"favmaf_{item_id}")])
    buttons.append([InlineKeyboardButton("🏠 منوی اصلی مفاتیح", callback_data="mafmenu")])
    return InlineKeyboardMarkup(buttons)


async def _render_mafatih_item(query, context: ContextTypes.DEFAULT_TYPE, item_id: str, page: int = 0):
    """متن یک آیتم مفاتیح (با در نظر گرفتن صفحه‌بندی) را نمایش می‌دهد."""
    item = db.get_mafatih_item_flexible(item_id)

    if not item:
        await safe_edit_message(
            query,
            "❌ اطلاعات این دعا در دیتابیس یافت نشد!",
            reply_markup=get_main_menu_keyboard()
        )
        return

    header, chunks = build_mafatih_pages(item)
    total_pages = len(chunks)
    page = max(0, min(page, total_pages - 1))

    text = header
    if total_pages > 1:
        text += f"(صفحه {to_persian_digits(page + 1)} از {to_persian_digits(total_pages)})\n\n"
    text += chunks[page]

    image_path = item["image_path"] if "image_path" in item.keys() else None
    audio_file_id = item["audio_file_id"] if "audio_file_id" in item.keys() else None

    markup = mafatih_item_keyboard(item_id, page=page, total_pages=total_pages, has_audio=bool(audio_file_id))

    # عکس فقط وقتی نمایش داده می‌شود که پیام واقعی و chat مشخصی داشته باشیم.
    # پیام‌های حاصل از نتایج سرچ اینلاین (query.message is None) فقط قابل
    # ویرایش متنی هستند و نمی‌توان پیام عکسِ جدا برایشان فرستاد.
    if image_path and page == 0 and query.message is not None:
        from pathlib import Path
        full_path = Path("/app") / image_path
        if full_path.exists():
            try:
                if len(text) <= 1024:
                    # متن کوتاه است: عکس + متن در یک پیام (کپشن)
                    with open(full_path, "rb") as img:
                        await query.message.reply_photo(photo=img, caption=text, reply_markup=markup)
                else:
                    # متن طولانی است: عکس در یک پیام، متنِ صفحه‌بندی‌شده در پیام بعدی
                    with open(full_path, "rb") as img:
                        photo_msg = await query.message.reply_photo(photo=img, caption=f"✨ {item['title']}")
                    context.user_data["maf_extra_photo_id"] = photo_msg.message_id
                    await query.message.chat.send_message(text, reply_markup=markup)
                await query.message.delete()
                return
            except Exception:
                logger.exception(f"MAFATIH IMAGE SEND ERROR {item_id} ({full_path})")
        else:
            logger.warning(f"MAFATIH IMAGE NOT FOUND {item_id}: {full_path}")

    await safe_edit_message(query, text, reply_markup=markup)


async def _send_mafatih_item_to_pv(query, context: ContextTypes.DEFAULT_TYPE, item_id: str):
    """وقتی دکمه‌ی «مشاهده کامل» زیر پست خودکار داخل یک گروه زده می‌شود، به‌جای
    ویرایش پیام داخل گروه (که صفحه‌بندی/دکمه‌های کامل بات را در گروه نمایش
    می‌دهد)، متن کامل دعا را در پیوی خودِ کاربر می‌فرستیم؛ ادامه‌ی ورق‌زدن،
    شنیدن صوت و افزودن به علاقه‌مندی‌ها از همان‌جا انجام می‌شود."""
    item = db.get_mafatih_item_flexible(item_id)
    if not item:
        await query.answer("❌ اطلاعات این دعا در دیتابیس یافت نشد!", show_alert=True)
        return

    header, chunks = build_mafatih_pages(item)
    total_pages = len(chunks)
    text = header
    if total_pages > 1:
        text += f"(صفحه {to_persian_digits(1)} از {to_persian_digits(total_pages)})\n\n"
    text += chunks[0]

    image_path = item["image_path"] if "image_path" in item.keys() else None
    audio_file_id = item["audio_file_id"] if "audio_file_id" in item.keys() else None
    markup = mafatih_item_keyboard(item_id, page=0, total_pages=total_pages, has_audio=bool(audio_file_id))
    user_id = query.from_user.id

    try:
        sent_via_photo = False
        if image_path:
            from pathlib import Path
            full_path = Path("/app") / image_path
            if full_path.exists():
                if len(text) <= 1024:
                    with open(full_path, "rb") as img:
                        await context.bot.send_photo(user_id, photo=img, caption=text, reply_markup=markup)
                else:
                    with open(full_path, "rb") as img:
                        await context.bot.send_photo(user_id, photo=img, caption=f"✨ {item['title']}")
                    await context.bot.send_message(user_id, text, reply_markup=markup)
                sent_via_photo = True
        if not sent_via_photo:
            await context.bot.send_message(user_id, text, reply_markup=markup)
        await query.answer("📩 متن کامل براتون در پیوی ربات ارسال شد.")
    except Exception:
        logger.exception(f"MAFATIH PV SEND ERROR {item_id}")
        await query.answer(
            "⚠️ برای دریافت متن کامل، اول در پیوی ربات دستور /start را بزنید، بعد دوباره روی این دکمه بزنید.",
            show_alert=True,
        )


async def mafatih_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    # اگر از دعای قبلی یک عکسِ یتیم (بدون دکمه) باقی مانده، پاکش کن.
    # این فقط وقتی ممکن است که پیام واقعی و chat مشخصی داشته باشیم؛ پیام‌هایی
    # که از طریق نتایج سرچ اینلاین (@نام_ربات عبارت) فرستاده شده‌اند chat_id
    # مشخصی به بات نمی‌دهند (query.message برایشان None است) و این مرحله باید
    # نادیده گرفته شود، وگرنه کل هندلر با خطا شکست می‌خورد و دکمه هیچ واکنشی نشان نمی‌دهد.
    if query.message:
        await cleanup_extra_photo(context, query.message.chat.id)

    item_id = query.data.replace("mafitem_", "")

    # اگر این دکمه (مثلاً زیر پست خودکار ساعتی) داخل یک گروه زده شده، متن کامل
    # را به‌جای نمایش در گروه، در پیوی کاربر می‌فرستیم.
    chat_type = update.effective_chat.type if update.effective_chat else None
    if chat_type in ("group", "supergroup"):
        await _send_mafatih_item_to_pv(query, context, item_id)
        return

    await query.answer()
    try:
        await _render_mafatih_item(query, context, item_id, page=0)
    except Exception as e:
        logger.exception(f"MAFATIH ERROR {item_id}: {e}")
        await safe_edit_message(
            query,
            "❌ خطایی در نمایش دعا رخ داد.",
            reply_markup=get_main_menu_keyboard()
        )


async def mafatih_text_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دکمه‌ی «صفحه بعد / صفحه قبل» برای دعاهای طولانی."""
    query = update.callback_query
    await query.answer()

    # maftxt_{item_id}_{page}  — چون item_id خودش ممکن است شامل _ باشد (مثل subh_post)
    # فقط آخرین بخش را به‌عنوان شماره صفحه جدا می‌کنیم
    raw = query.data.replace("maftxt_", "")
    item_id, page = raw.rsplit("_", 1)

    try:
        await _render_mafatih_item(query, context, item_id, page=int(page))
    except Exception as e:
        logger.exception(f"MAFATIH PAGE ERROR {item_id}: {e}")
        await safe_edit_message(
            query,
            "❌ خطایی در نمایش دعا رخ داد.",
            reply_markup=get_main_menu_keyboard()
        )

async def mafatih_audio_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دکمه‌ی «فایل صوتی این دعا».
    برای پیام‌های معمولی داخل چت/گروه: صدا را جدا در همان چت می‌فرستد.
    برای پیام‌هایی که از نتیجه‌ی سرچ اینلاین آمده‌اند (query.message خالی است
    چون تلگرام chat_id این‌ها را به بات نمی‌دهد) امکان فرستادن پیام جداگانه
    نیست؛ به‌جای آن خودِ همان پیام به یک پیام صوتی تبدیل می‌شود."""
    query = update.callback_query
    item_id = query.data.replace("mafaudio_", "")
    item = db.get_mafatih_item_flexible(item_id)

    audio_file_id = item["audio_file_id"] if item and "audio_file_id" in item.keys() else None
    if not audio_file_id:
        await query.answer("❌ فایل صوتی برای این دعا یافت نشد.", show_alert=True)
        return

    if query.message:
        await query.answer()
        try:
            audio_msg = await query.message.chat.send_audio(
                audio=audio_file_id,
                title=item["title"],
                caption=f"🎧 {item['title']}",
            )
            context.user_data["maf_extra_audio_id"] = audio_msg.message_id
        except Exception:
            logger.exception(f"MAFATIH AUDIO SEND ERROR {item_id} (file_id={audio_file_id})")
            try:
                await query.message.reply_text("❌ در ارسال فایل صوتی خطایی رخ داد.")
            except Exception:
                pass
    else:
        # پیام از نتیجه‌ی سرچ اینلاین است؛ chat_id نداریم پس پیام جدا ممکن نیست
        try:
            await query.edit_message_media(
                media=InputMediaAudio(
                    media=audio_file_id, title=item["title"], caption=f"🎧 {item['title']}"
                )
            )
            await query.answer()
        except Exception:
            logger.exception(f"MAFATIH INLINE AUDIO EDIT ERROR {item_id} (file_id={audio_file_id})")
            await query.answer(
                "❌ پخش صدا از داخل نتیجه‌ی سرچ ممکن نشد. برای شنیدن صدا، دعا را "
                "از منوی داخل ربات (نه از نتیجه‌ی سرچ) باز کنید.",
                show_alert=True,
            )


async def fav_mafatih_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    item_id = query.data.replace("favmaf_", "")
    user_id = query.from_user.id

    try:
        db.add_favorite(user_id, "mafatih", item_id)
        await query.answer("⭐ به علاقه‌مندی‌های شما اضافه شد!", show_alert=True)
    except Exception as e:
        logger.error(f"Error adding fav mafatih {item_id}: {e}")
        await query.answer("❌ خطا در افزودن به علاقه‌مندی‌ها.", show_alert=True)

async def add_mafatih_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای دستور /addmafatih (مخصوص ادمین‌ها)"""
    await update.message.reply_text("این بخش جهت افزودن دعای جدید توسط ادمین می‌باشد. (در حال توسعه)")

async def mafatih_menu_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای زمانی که کاربر دکمه متنی مفاتیح الجنان را می‌زند"""
    text = "📖 *بخش مفاتیح الجنان*\n\nلطفاً دسته‌بندی مورد نظر خود را انتخاب کنید:"
    await update.message.reply_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")