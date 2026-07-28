# handlers/prayer.py
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

# غیرفعال کردن بررسی SSL
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# لیست کدهای شهرهای اصلی ایران
CITY_CODES = {
    "تهران": 1,
    "مشهد": 2,
    "اصفهان": 3,
    "شیراز": 4,
    "تبریز": 5,
    "کرج": 6,
    "قم": 7,
    "اهواز": 8,
    "کرمانشاه": 9,
    "رشت": 10,
    "یزد": 11,
    "کرمان": 12,
    "اراک": 13,
    "همدان": 14,
    "زنجان": 15,
    "ساری": 16,
    "گرگان": 17,
    "بوشهر": 18,
    "بیرجند": 19,
    "خرم‌آباد": 20,
    "ارومیه": 21,
    "شهرکرد": 22,
    "بندرعباس": 23,
    "زاهدان": 24,
    "سنندج": 25,
    "قزوین": 26,
    "سمنان": 27,
    "مازندران": 28,
    "گلستان": 29,
    "لرستان": 30,
}


def get_prayer_times(city_code: int):
    """دریافت اوقات شرعی از API آوینی با غیرفعال کردن بررسی SSL"""
    url = f"https://prayer.aviny.com/api/prayertimes/{city_code}"
    
    try:
        response = requests.get(url, timeout=10, verify=False)
        response.raise_for_status()
        data = response.json()
        
        return {
            "success": True,
            "city": data.get("CityName", ""),
            "country": data.get("CountryName", ""),
            "date": data.get("Today", ""),
            "fajr": data.get("Imsaak", ""),
            "sunrise": data.get("Sunrise", ""),
            "noon": data.get("Noon", ""),
            "sunset": data.get("Sunset", ""),
            "maghrib": data.get("Maghreb", ""),
            "midnight": data.get("Midnight", ""),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"خطا در دریافت اوقات شرعی: {e}")
        return {"success": False, "error": str(e)}


def prayer_keyboard(city_code: int = None, user_id: int = None):
    """کیبورد دکمه‌های اوقات شرعی با شناسه کاربر"""
    buttons = []
    
    # دکمه‌های شهرهای پرکاربرد
    city_buttons = [
        [InlineKeyboardButton("🕌 تهران", callback_data=f"prayer_city_1_{user_id}"),
         InlineKeyboardButton("🕌 مشهد", callback_data=f"prayer_city_2_{user_id}")],
        [InlineKeyboardButton("🕌 اصفهان", callback_data=f"prayer_city_3_{user_id}"),
         InlineKeyboardButton("🕌 شیراز", callback_data=f"prayer_city_4_{user_id}")],
        [InlineKeyboardButton("🕌 قم", callback_data=f"prayer_city_7_{user_id}"),
         InlineKeyboardButton("🕌 کرج", callback_data=f"prayer_city_6_{user_id}")],
        [InlineKeyboardButton("🌍 انتخاب شهر دیگر", callback_data=f"prayer_city_list_{user_id}")],
        [InlineKeyboardButton("📌 دریافت بر اساس موقعیت", callback_data=f"prayer_location_{user_id}")],
    ]
    
    # دکمه‌های عملیاتی
    action_buttons = [
        [InlineKeyboardButton("🔄 به‌روزرسانی", callback_data=f"prayer_refresh_{city_code or 1}_{user_id}"),
         InlineKeyboardButton("⏰ تنظیم یادآور", callback_data=f"prayer_reminder_{user_id}")],
        [InlineKeyboardButton("📋 دریافت همه شهرها", callback_data=f"prayer_all_cities_{user_id}")],
        [InlineKeyboardButton("⬅️ بازگشت به منو", callback_data="menu_back")],
    ]
    
    buttons.extend(city_buttons)
    buttons.extend(action_buttons)
    return InlineKeyboardMarkup(buttons)


async def prayer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /prayer - نمایش اوقات شرعی"""
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id
    
    # در گروه‌ها، فقط با دستور یا منشن کار می‌کند
    if chat_type != "private" and not update.message.text.startswith("/prayer"):
        return
    
    message = "🕌 *اوقات شرعی*\n\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:"
    
    # ذخیره user_id در context
    context.user_data["prayer_user_id"] = user_id
    
    # اگر کاربر قبلاً شهری انتخاب کرده، در context ذخیره می‌کنیم
    if "prayer_city" not in context.user_data:
        context.user_data["prayer_city"] = 1  # پیش‌فرض تهران
    
    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        reply_markup=prayer_keyboard(context.user_data["prayer_city"], user_id)
    )


def check_ownership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """بررسی می‌کند که آیا کاربری که دکمه را زده، همان صاحب پیام (owner_id داخل callback_data) است.

    نکته مهم: نباید از context.user_data برای این کار استفاده کرد، چون در
    python-telegram-bot این دیتا per-user است نه per-message؛ یعنی وقتی کاربر
    دیگری روی دکمه کلیک می‌کند، context.user_data مخصوص همان کاربر کلیک‌کننده
    برگردانده می‌شود (نه صاحب اصلی پیام) و همیشه owner_id را None می‌داد و در
    نتیجه بررسی همیشه پاس می‌شد.
    به همین دلیل آیدی مالک را مستقیماً از انتهای callback_data می‌خوانیم، چون
    همیشه به شکل ..._{user_id} ساخته شده است.
    """
    query = update.callback_query
    if not query or not query.data:
        return True

    try:
        owner_id = int(query.data.rsplit("_", 1)[-1])
    except (ValueError, IndexError):
        # اگر callback_data آیدی مالک نداشت، بررسی را رد نمی‌کنیم
        return True

    return update.effective_user.id == owner_id


async def prayer_city_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کالبک انتخاب شهر"""
    query = update.callback_query
    
    # بررسی مالکیت
    if not check_ownership(update, context):
        await query.answer("❌ این دکمه متعلق به شما نیست!", show_alert=True)
        return
    
    await query.answer()
    
    # استخراج کد شهر از کالبک
    parts = query.data.split("_")
    city_code = int(parts[2])
    context.user_data["prayer_city"] = city_code
    
    # دریافت و نمایش اوقات شرعی
    await show_prayer_times(update, context, city_code)


async def prayer_city_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لیست کامل شهرها با صفحه‌بندی"""
    query = update.callback_query
    
    # بررسی مالکیت
    if not check_ownership(update, context):
        await query.answer("❌ این دکمه متعلق به شما نیست!", show_alert=True)
        return
    
    await query.answer()
    
    # صفحه‌بندی شهرها
    page = context.user_data.get("prayer_page", 0)
    user_id = update.effective_user.id
    city_items = list(CITY_CODES.items())
    page_size = 10
    total_pages = (len(city_items) + page_size - 1) // page_size
    
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(city_items))
    
    buttons = []
    for city_name, code in city_items[start_idx:end_idx]:
        buttons.append([InlineKeyboardButton(f"📍 {city_name}", callback_data=f"prayer_city_{code}_{user_id}")])
    
    # دکمه‌های صفحه‌بندی
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"prayer_page_prev_{user_id}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"prayer_page_next_{user_id}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"prayer_back_{user_id}")])
    
    await query.edit_message_text(
        f"🌍 انتخاب شهر (صفحه {page+1} از {total_pages}):",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def prayer_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """صفحه‌بندی لیست شهرها"""
    query = update.callback_query
    
    # بررسی مالکیت
    if not check_ownership(update, context):
        await query.answer("❌ این دکمه متعلق به شما نیست!", show_alert=True)
        return
    
    await query.answer()
    
    if "page_prev" in query.data:
        context.user_data["prayer_page"] = max(0, context.user_data.get("prayer_page", 0) - 1)
    elif "page_next" in query.data:
        context.user_data["prayer_page"] = context.user_data.get("prayer_page", 0) + 1
    
    await prayer_city_list_callback(update, context)


async def prayer_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """به‌روزرسانی اوقات شرعی"""
    query = update.callback_query
    
    # بررسی مالکیت
    if not check_ownership(update, context):
        await query.answer("❌ این دکمه متعلق به شما نیست!", show_alert=True)
        return
    
    await query.answer("🔄 در حال به‌روزرسانی...")
    
    parts = query.data.split("_")
    city_code = int(parts[2])
    await show_prayer_times(update, context, city_code)


async def prayer_location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست موقعیت مکانی از کاربر"""
    query = update.callback_query
    
    # بررسی مالکیت
    if not check_ownership(update, context):
        await query.answer("❌ این دکمه متعلق به شما نیست!", show_alert=True)
        return
    
    await query.answer()
    
    location_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📍 ارسال موقعیت", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await query.edit_message_text(
        "📍 لطفاً موقعیت مکانی خود را ارسال کنید تا اوقات شرعی بر اساس شهر شما محاسبه شود.\n\n"
        "⚠️ توجه: این قابلیت به یک سرویس خارجی برای تبدیل مختصات به نام شهر نیاز دارد.",
        reply_markup=location_keyboard
    )


async def prayer_location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش موقعیت مکانی دریافتی"""
    location = update.message.location
    user_id = update.effective_user.id
    
    # بررسی مالکیت
    if not check_ownership(update, context):
        await update.message.reply_text("❌ شما دسترسی به این عملیات ندارید!")
        return
    
    # تبدیل مختصات به نام شهر (با استفاده از API Nominatim)
    try:
        lat = location.latitude
        lon = location.longitude
        
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        response = requests.get(url, timeout=10, headers={"User-Agent": "TelegramBot"})
        data = response.json()
        
        address = data.get("address", {})
        city = address.get("city") or address.get("town") or address.get("village") or address.get("state") or "ناشناس"
        
        city_code = None
        for name, code in CITY_CODES.items():
            if name in city or city in name:
                city_code = code
                break
        
        if city_code:
            context.user_data["prayer_city"] = city_code
            await show_prayer_times(update, context, city_code, city)
        else:
            await update.message.reply_text(
                f"⚠️ متاسفانه شهر '{city}' در لیست ما موجود نیست.\n"
                "لطفاً یکی از شهرهای موجود را انتخاب کنید.",
                reply_markup=prayer_keyboard(context.user_data.get("prayer_city", 1), user_id)
            )
    except Exception as e:
        logger.error(f"خطا در تبدیل موقعیت: {e}")
        await update.message.reply_text(
            "⚠️ خطا در دریافت اطلاعات موقعیت. لطفاً شهر مورد نظر را از لیست انتخاب کنید.",
            reply_markup=prayer_keyboard(context.user_data.get("prayer_city", 1), user_id)
        )


async def prayer_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به منوی اوقات شرعی"""
    query = update.callback_query
    
    # بررسی مالکیت
    if not check_ownership(update, context):
        await query.answer("❌ این دکمه متعلق به شما نیست!", show_alert=True)
        return
    
    await query.answer()
    user_id = update.effective_user.id
    
    await query.edit_message_text(
        "🕌 *اوقات شرعی*\n\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=prayer_keyboard(context.user_data.get("prayer_city", 1), user_id)
    )


async def show_prayer_times(update: Update, context: ContextTypes.DEFAULT_TYPE, city_code: int, city_name: str = None):
    """نمایش اوقات شرعی با فرمت زیبا"""
    query = update.callback_query if update.callback_query else None
    user_id = update.effective_user.id
    
    result = get_prayer_times(city_code)
    
    if not result["success"]:
        error_msg = f"⚠️ خطا در دریافت اوقات شرعی: {result.get('error', 'خطای ناشناخته')}\n\nلطفاً دوباره تلاش کنید."
        if query:
            await query.edit_message_text(error_msg, reply_markup=prayer_keyboard(city_code, user_id))
        else:
            await update.message.reply_text(error_msg, reply_markup=prayer_keyboard(city_code, user_id))
        return
    
    message = f"""🕌 *اوقات شرعی {result['city']}*

📅 *تاریخ:* {result['date']}
🌍 *کشور:* {result['country']}

🌅 *اذان صبح:* {result['fajr']}
☀️ *طلوع آفتاب:* {result['sunrise']}
🌤 *اذان ظهر:* {result['noon']}
🌅 *غروب آفتاب:* {result['sunset']}
🌙 *اذان مغرب:* {result['maghrib']}
🌃 *نیمه‌شب شرعی:* {result['midnight']}

⏰ *زمان به‌روزرسانی:* لحظه‌ای
🔄 برای به‌روزرسانی، دکمه زیر را بزنید.
"""
    
    keyboard = [
        [InlineKeyboardButton("🔄 به‌روزرسانی", callback_data=f"prayer_refresh_{city_code}_{user_id}"),
         InlineKeyboardButton("📍 شهر دیگر", callback_data=f"prayer_city_list_{user_id}")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"prayer_back_{user_id}")]
    ]
    
    if query:
        await query.edit_message_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def prayer_all_cities_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش اوقات شرعی چند شهر اصلی"""
    query = update.callback_query
    
    # بررسی مالکیت
    if not check_ownership(update, context):
        await query.answer("❌ این دکمه متعلق به شما نیست!", show_alert=True)
        return
    
    await query.answer()
    user_id = update.effective_user.id
    
    main_cities = [
        ("تهران", 1), ("مشهد", 2), ("اصفهان", 3),
        ("شیراز", 4), ("قم", 7)
    ]
    
    message = "🕌 *اوقات شرعی شهرهای اصلی ایران*\n\n"
    for city_name, code in main_cities:
        result = get_prayer_times(code)
        if result["success"]:
            message += f"**{city_name}:**\n"
            message += f"🌅 اذان صبح: {result['fajr']}\n"
            message += f"🌤 اذان ظهر: {result['noon']}\n"
            message += f"🌙 اذان مغرب: {result['maghrib']}\n\n"
        else:
            message += f"⚠️ {city_name}: خطا در دریافت\n\n"
    
    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"prayer_back_{user_id}")]
        ])
    )