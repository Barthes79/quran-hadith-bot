import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

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
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی ربات", callback_data="menu_main")]
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
        [InlineKeyboardButton("📖 سوره‌های قرآنی مفاتیح", callback_data="mafsub_quran_surahs")],
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
        [InlineKeyboardButton("🌌 اعمال شب جمعه", callback_data="mafitem_night_friday"), InlineKeyboardButton("☀️ اعمال روز جمعه", callback_data="mafitem_day_friday")],
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
        [InlineKeyboardButton("⛪ عدیله", callback_data="mafitem_adilah"), InlineKeyboardButton("🌟 فرج", callback_data="mafitem_faraj_allah")],
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
        [InlineKeyboardButton("۱۳. ذاکرین", callback_data="mafitem_monajat_zakerin"), InlineKeyboardButton("۱۴. معتصمین", callback_data="mafitem_monajat_moatasemin")],
        [InlineKeyboardButton("۱۵. زاهدین", callback_data="mafitem_monajat_zahedin"), InlineKeyboardButton("📜 منظومه", callback_data="mafitem_monajat_manzum")],
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
        [InlineKeyboardButton("🛡️ شب‌های قدر", callback_data="mafitem_laylat_alqadr"), InlineKeyboardButton("📅 دعای روزانه", callback_data="mafitem_ramadan_days")],
        [InlineKeyboardButton("👑 دعای افتتاح", callback_data="mafitem_dua_iftitah")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_lunar_months"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_other_months():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌍 دحوالارض", callback_data="mafitem_dahw_al_ard"), InlineKeyboardButton("⛰️ روز عرفه", callback_data="mafitem_arafat_day")],
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
        [InlineKeyboardButton("🛡️ زیارت امین الله", callback_data="mafitem_aminullah"), InlineKeyboardButton("🏴 زیارت عاشورا", callback_data="mafitem_ashura_ziyarat")],
        [InlineKeyboardButton("👣 زیارت اربعین", callback_data="mafitem_arbaeen_ziyarat"), InlineKeyboardButton("📜 زیارت وارث", callback_data="mafitem_warith_ziyarat")],
        [InlineKeyboardButton("👑 زیارت جامعه کبیره", callback_data="mafitem_jameah_kabirah"), InlineKeyboardButton("🛡️ حضرت عباس (ع)", callback_data="mafitem_abbas_ziyarat")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="mafcat_ziyarats"), InlineKeyboardButton("🏠 منوی مفاتیح", callback_data="mafmenu")]
    ])

def get_keyboard_for_mosques_deeds():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏛️ مسجد کوفه", callback_data="mafitem_kufa_mosque"), InlineKeyboardButton("🕌 مسجد سهله", callback_data="mafitem_sahla_mosque")],
        [InlineKeyboardButton("⛪ مساجد براثا و زید", callback_data="mafitem_mosque_deeds_others"), InlineKeyboardButton("🗡️ مسلم و هانی", callback_data="mafitem_muslim_ziyarat")],
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

def get_keyboard_for_quran_surahs():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 حدیث شریف کساء", callback_data="mafitem_hadith_kisa"), InlineKeyboardButton("💎 مکارم الاخلاق", callback_data="mafitem_dua_makarem")],
        [InlineKeyboardButton("💚 سوره یس", callback_data="mafitem_surah_yasin"), InlineKeyboardButton("🌸 سوره الرحمن", callback_data="mafitem_surah_rahman")],
        [InlineKeyboardButton("💎 سوره واقعه", callback_data="mafitem_surah_waqiah"), InlineKeyboardButton("📖 روم و عنکبوت", callback_data="mafitem_surah_rom_ankabut")],
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
    "medina_ziyarat": get_keyboard_for_medina_ziyarat,
    "karbala_najaf": get_keyboard_for_karbala_najaf,
    "mosques_deeds": get_keyboard_for_mosques_deeds,
    "iran_ziyarats": get_keyboard_for_iran_ziyarats,
    "recommended_prayers": get_keyboard_for_recommended_prayers,
    "sickness_healing": get_keyboard_for_sickness_healing,
    "quran_surahs": get_keyboard_for_quran_surahs
}

# ==========================================
# 3. هندلرها (Handlers)
# ==========================================

async def mafatih_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "📖 **بخش مفاتیح الجنان**\n\nلطفاً دسته‌بندی مورد نظر خود را انتخاب کنید:"
    await query.edit_message_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

async def mafatih_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # mafcat_daily_weekly -> daily_weekly
    cat_id = query.data.replace("mafcat_", "")
    
    kb_func = CAT_KEYBOARDS.get(cat_id)
    if kb_func:
        await query.edit_message_text("📂 لطفاً زیردسته مورد نظر را انتخاب کنید:", reply_markup=kb_func())

async def mafatih_subcategory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # mafsub_post_prayers -> post_prayers
    sub_id = query.data.replace("mafsub_", "")
    
    kb_func = SUB_KEYBOARDS.get(sub_id)
    if kb_func:
        await query.edit_message_text("📜 لطفاً دعای مورد نظر را انتخاب کنید:", reply_markup=kb_func())

async def mafatih_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    item_id = query.data.replace("mafitem_", "")

    try:
        item = db.get_mafatih_item(item_id)

        if not item:
            await query.edit_message_text(
                "❌ اطلاعات این دعا در دیتابیس یافت نشد!",
                reply_markup=get_main_menu_keyboard()
            )
            return

        title = item["title"]

        text = f"✨ {title}\n\n"

        if item["arabic_text"]:
            text += f"{item['arabic_text']}\n\n"

        if item["translation_text"]:
            text += f"📖 ترجمه:\n{item['translation_text']}\n\n"

        if item["tafsir_text"]:
            text += f"💡 توضیحات:\n{item['tafsir_text']}"

        back_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ افزودن به علاقه‌مندی‌ها", callback_data=f"favmaf_{item_id}")],
            [InlineKeyboardButton("🏠 منوی اصلی مفاتیح", callback_data="mafmenu")]
        ])

        image_path = item["image_path"]

        if image_path:
            from pathlib import Path
            full_path = Path("/app") / image_path

            if full_path.exists():
                with open(full_path, "rb") as img:
                    await query.message.reply_photo(
                        photo=img,
                        caption=text[:1024],
                        reply_markup=back_kb
                    )
                await query.message.delete()
                return

        await query.edit_message_text(
            text[:4096],
            reply_markup=back_kb
        )

    except Exception as e:
        logger.exception(f"MAFATIH ERROR {item_id}: {e}")
        await query.edit_message_text(
            "❌ خطایی در نمایش دعا رخ داد.",
            reply_markup=get_main_menu_keyboard()
        )

async def fav_mafatih_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    item_id = query.data.replace("favmaf_", "")
    user_id = query.from_user.id
    
    try:
        # اگر در دیتابیس تابعی برای افزودن به علاقه‌مندی‌ها دارید، اینجا فراخوانی کنید
        # db.add_favorite(user_id, "mafatih", item_id)
        await query.answer("⭐ به علاقه‌مندی‌های شما اضافه شد!", show_alert=True)
    except Exception as e:
        logger.error(f"Error adding fav mafatih {item_id}: {e}")
        await query.answer("❌ خطا در افزودن به علاقه‌مندی‌ها.", show_alert=True)

async def add_mafatih_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای دستور /addmafatih (مخصوص ادمین‌ها)"""
    await update.message.reply_text("این بخش جهت افزودن دعای جدید توسط ادمین می‌باشد. (در حال توسعه)")

async def mafatih_menu_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای زمانی که کاربر دکمه متنی مفاتیح الجنان را می‌زند"""
    text = "📖 **بخش مفاتیح الجنان**\n\nلطفاً دسته‌بندی مورد نظر خود را انتخاب کنید:"
    await update.message.reply_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")