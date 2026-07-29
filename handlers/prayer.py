# handlers/prayer.py
import logging
import html
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    get_prayer_reminder,
    upsert_prayer_reminder,
    toggle_prayer_reminder_azan,
    set_prayer_reminder_minutes,
    get_all_enabled_prayer_reminders,
)

# غیرفعال کردن بررسی SSL
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

IRAN_TZ = ZoneInfo("Asia/Tehran")

# نگاشت کلید داخلی هر اذان به فیلد پاسخ API آوینی و برچسب نمایشی فارسی
PRAYER_FIELD_MAP = {
    "fajr": ("fajr", "🌅 اذان صبح"),
    "noon": ("noon", "🌤 اذان ظهر"),
    "maghrib": ("maghrib", "🌙 اذان مغرب"),
}

# لیست کدهای شهرهای اصلی ایران
# نکته: این کدها دلخواه/پشت‌سرهم نیستن؛ کد واقعی هر شهر توی سیستم آوینی
# با استفاده از اسکریپت check_city_codes.py استخراج و تأیید شده (تاریخ تأیید: امروز).
CITY_CODES = {
    "تهران": 1,
    "اصفهان": 2,
    "ارومیه": 3,
    "اراک": 4,
    "اهواز": 5,
    "تبریز": 6,
    "بندرعباس": 7,
    "شیراز": 8,
    "کرج": 9,
    "قزوین": 10,
    "قم": 11,
    "زاهدان": 12,
    "مشهد": 13,
    "یزد": 14,
    "بجنورد": 15,
    "رشت": 16,
    "ساری": 17,
    "گرگان": 18,
    "کرمان": 19,
    "بوشهر": 20,
    "کرمانشاه": 21,
    "سنندج": 22,
    "مهاباد": 23,
    "همدان": 24,
    "زنجان": 25,
    "اردبیل": 26,
    "سمنان": 27,
    "ایلام": 29,
    "خرم‌آباد": 30,
    "شهرکرد": 31,
    "یاسوج": 32,
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


def _compute_remind_datetime(now: datetime, time_str: str, minutes_before: int):
    """از روی رشته‌ی ساعت اذان (مثل '04:12') و تعداد دقیقه‌ی قبل از آن،
    زمان دقیق ارسال یادآور را برمی‌گرداند. اگر فرمت نامعتبر بود None."""
    try:
        hh, mm = map(int, time_str.strip().split(":")[:2])
    except (ValueError, AttributeError):
        return None
    azan_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return azan_dt - timedelta(minutes=minutes_before)


async def _schedule_reminders_for_row(reminder_row, context: ContextTypes.DEFAULT_TYPE):
    """برای یک ردیف یادآور (یک کاربر)، اذان‌های امروزِ باقی‌مانده را که فعال کرده،
    به‌صورت جاب یک‌بارمصرف زمان‌بندی می‌کند."""
    if not context.job_queue:
        return

    user_id = reminder_row["user_id"]
    result = get_prayer_times(reminder_row["city_code"])
    if not result["success"]:
        logger.warning(f"عدم امکان زمان‌بندی یادآور برای کاربر {user_id}: خطا در دریافت اوقات شرعی")
        return

    now = datetime.now(IRAN_TZ)
    for key, (field, label) in PRAYER_FIELD_MAP.items():
        job_name = f"prayer_reminder_{user_id}_{key}_{now.date()}"

        if not reminder_row[f"remind_{key}"]:
            continue

        remind_dt = _compute_remind_datetime(now, result.get(field, ""), reminder_row["minutes_before"])
        if not remind_dt or remind_dt <= now:
            continue

        # جلوگیری از زمان‌بندی تکراری در صورتی که قبلاً برای همین روز ساخته شده باشد
        for j in context.job_queue.get_jobs_by_name(job_name):
            j.schedule_removal()

        context.job_queue.run_once(
            send_prayer_reminder,
            when=remind_dt,
            data={
                "user_id": user_id,
                "label": label,
                "minutes_before": reminder_row["minutes_before"],
                "group_chat_id": reminder_row["group_chat_id"],
                "user_name": reminder_row["user_name"] or "کاربر",
            },
            name=job_name,
        )


async def schedule_reminders_for_user(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """بلافاصله بعد از تغییر تنظیمات یادآور توسط کاربر صدا زده می‌شود تا همون روز
    هم اذان‌های باقی‌مانده زمان‌بندی بشن (منتظر جاب نیمه‌شب نمونیم)."""
    reminder = get_prayer_reminder(user_id)
    if not reminder or not reminder["enabled"]:
        return
    await _schedule_reminders_for_row(reminder, context)


async def schedule_daily_prayer_reminders(context: ContextTypes.DEFAULT_TYPE):
    """جاب روزانه: هر روز خیلی زود صبح اجرا می‌شود، اوقات شرعی امروز را برای
    تمام کاربرهایی که یادآور فعال دارند می‌گیرد و برای هرکدوم یک جاب
    یک‌بارمصرف در زمان مناسب می‌سازد."""
    for reminder_row in get_all_enabled_prayer_reminders():
        await _schedule_reminders_for_row(reminder_row, context)


async def send_prayer_reminder(context: ContextTypes.DEFAULT_TYPE):
    """جاب یک‌بارمصرفی که در زمان مقرر، پیام یادآوری را هم در پیوی کاربر
    و هم (در صورت وجود) با تگ کردن او در گروهی که تنظیم را انجام داده، می‌فرستد."""
    job_data = context.job.data
    user_id = job_data["user_id"]
    label = job_data["label"]
    minutes_before = job_data["minutes_before"]
    group_chat_id = job_data.get("group_chat_id")
    user_name = html.escape(job_data.get("user_name") or "کاربر")

    # پیام پیوی
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"⏰ {minutes_before} دقیقه تا {label} مانده است.",
        )
    except Exception as e:
        logger.error(f"خطا در ارسال یادآور اذان (پیوی) به کاربر {user_id}: {e}")

    # پیام گروه با تگ کردن کاربر (اگه یادآور از داخل یه گروه تنظیم شده باشه)
    if group_chat_id:
        mention = f'<a href="tg://user?id={user_id}">{user_name}</a>'
        try:
            await context.bot.send_message(
                chat_id=group_chat_id,
                text=f"⏰ {mention} {minutes_before} دقیقه تا {label} مانده است.",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"خطا در ارسال یادآور اذان (گروه {group_chat_id}) برای کاربر {user_id}: {e}")


def prayer_keyboard(city_code: int = None, user_id: int = None):
    """کیبورد دکمه‌های اوقات شرعی با شناسه کاربر"""
    buttons = []
    
    # دکمه‌های شهرهای پرکاربرد
    city_buttons = [
        [InlineKeyboardButton("🕌 تهران", callback_data=f"prayer_city_1_{user_id}"),
         InlineKeyboardButton("🕌 مشهد", callback_data=f"prayer_city_13_{user_id}")],
        [InlineKeyboardButton("🕌 اصفهان", callback_data=f"prayer_city_2_{user_id}"),
         InlineKeyboardButton("🕌 شیراز", callback_data=f"prayer_city_8_{user_id}")],
        [InlineKeyboardButton("🕌 قم", callback_data=f"prayer_city_11_{user_id}"),
         InlineKeyboardButton("🕌 کرج", callback_data=f"prayer_city_9_{user_id}")],
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
    
    # نکته: edit_message_text فقط InlineKeyboardMarkup قبول می‌کنه، نه ReplyKeyboardMarkup.
    # برای همین کیبورد سفارشی (درخواست موقعیت) باید توی یک پیام جدید فرستاده بشه،
    # نه با ویرایش پیام قبلی.
    await query.edit_message_text(
        "📍 لطفاً از دکمه‌ی پایین صفحه، موقعیت مکانی خودتون رو ارسال کنید تا اوقات شرعی شهرتون محاسبه بشه.\n\n"
        "⚠️ توجه: این قابلیت به یک سرویس خارجی برای تبدیل مختصات به نام شهر نیاز دارد."
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📍 برای ارسال موقعیت، دکمه‌ی زیر رو بزن:",
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
        ("تهران", 1), ("مشهد", 13), ("اصفهان", 2),
        ("شیراز", 8), ("قم", 11)
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


# ==========================================
# یادآور اذان
# ==========================================

def _mark(flag) -> str:
    return "✅" if flag else "❌"


def _capture_reminder_context(update: Update, user_id: int):
    """
    اسم کاربر رو همیشه ذخیره می‌کنه (برای منشن توی گروه).
    group_chat_id رو فقط وقتی خود کاربر داخل یه گروه دکمه رو زده آپدیت می‌کنه؛
    اگه از پیوی داره تنظیمات رو عوض می‌کنه، group_chat_id قبلی (اگه از قبل
    توی یه گروه ست شده بود) دست‌نخورده می‌مونه.
    """
    chat = update.effective_chat
    user = update.effective_user
    fields = {"user_name": user.first_name or user.full_name or "کاربر"}
    if chat.type in ("group", "supergroup"):
        fields["group_chat_id"] = chat.id
    upsert_prayer_reminder(user_id, **fields)


async def show_reminder_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, city_code: int):
    """نمایش (یا بروزرسانی) منوی تنظیم یادآور اذان برای یک کاربر"""
    reminder = get_prayer_reminder(user_id)
    fajr_on = bool(reminder["remind_fajr"]) if reminder else False
    noon_on = bool(reminder["remind_noon"]) if reminder else False
    maghrib_on = bool(reminder["remind_maghrib"]) if reminder else False
    minutes = reminder["minutes_before"] if reminder else 10
    enabled = bool(reminder["enabled"]) if reminder else False
    group_chat_id = reminder["group_chat_id"] if reminder else None

    text = (
        "⏰ *تنظیم یادآور اذان*\n\n"
        "هر کدوم از اذان‌ها رو که می‌خوای، فعال کن. من "
        f"*{minutes} دقیقه* قبل از اون اذان یه پیام یادآوری برات می‌فرستم.\n\n"
        f"وضعیت کلی: {'🟢 فعال' if enabled else '🔴 غیرفعال'}\n"
    )
    if group_chat_id:
        text += "📌 چون از داخل یه گروه تنظیمش کردی، توی همون گروه هم با تگ کردن خودت یادآوری می‌فرستم.\n"

    keyboard = [
        [InlineKeyboardButton(f"{_mark(fajr_on)} اذان صبح", callback_data=f"prayer_remind_toggle_fajr_{user_id}")],
        [InlineKeyboardButton(f"{_mark(noon_on)} اذان ظهر", callback_data=f"prayer_remind_toggle_noon_{user_id}")],
        [InlineKeyboardButton(f"{_mark(maghrib_on)} اذان مغرب", callback_data=f"prayer_remind_toggle_maghrib_{user_id}")],
        [InlineKeyboardButton(f"⏱ {minutes} دقیقه قبل (بزن برای تغییر)", callback_data=f"prayer_remind_setmin_{user_id}")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"prayer_back_{user_id}")],
    ]

    query = update.callback_query
    if query:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.effective_chat.send_message(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def prayer_reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """باز کردن منوی تنظیم یادآور اذان (دکمه‌ی ⏰ تنظیم یادآور)"""
    query = update.callback_query

    if not check_ownership(update, context):
        await query.answer("❌ این دکمه متعلق به شما نیست!", show_alert=True)
        return

    await query.answer()
    user_id = update.effective_user.id
    city_code = context.user_data.get("prayer_city", 1)
    _capture_reminder_context(update, user_id)
    await show_reminder_menu(update, context, user_id, city_code)


async def prayer_reminder_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تیک زدن/برداشتن یکی از اذان‌ها توی منوی یادآور"""
    query = update.callback_query

    if not check_ownership(update, context):
        await query.answer("❌ این دکمه متعلق به شما نیست!", show_alert=True)
        return

    # callback_data به شکل: prayer_remind_toggle_{azan}_{user_id}
    parts = query.data.split("_")
    azan_key = parts[3]
    user_id = update.effective_user.id
    city_code = context.user_data.get("prayer_city", 1)
    _capture_reminder_context(update, user_id)

    new_value = toggle_prayer_reminder_azan(user_id, azan_key)

    if new_value == 0 and context.job_queue:
        # اگر این اذان خاموش شد، جاب امروزش (اگه ساخته شده بود) رو هم لغو کن
        job_name = f"prayer_reminder_{user_id}_{azan_key}_{datetime.now(IRAN_TZ).date()}"
        for j in context.job_queue.get_jobs_by_name(job_name):
            j.schedule_removal()

    reminder = get_prayer_reminder(user_id)
    any_on = any([reminder["remind_fajr"], reminder["remind_noon"], reminder["remind_maghrib"]])
    upsert_prayer_reminder(user_id, city_code=city_code, enabled=1 if any_on else 0)

    if any_on:
        await schedule_reminders_for_user(user_id, context)

    await query.answer("✅ فعال شد" if new_value else "❌ غیرفعال شد")
    await show_reminder_menu(update, context, user_id, city_code)


async def prayer_reminder_setmin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست از کاربر برای وارد کردن تعداد دقیقه‌ی قبل از اذان"""
    query = update.callback_query

    if not check_ownership(update, context):
        await query.answer("❌ این دکمه متعلق به شما نیست!", show_alert=True)
        return

    await query.answer()
    context.user_data["awaiting_reminder_minutes"] = True
    _capture_reminder_context(update, update.effective_user.id)

    await query.edit_message_text(
        "⏱ چند دقیقه قبل از اذان یادآوری بفرستم؟\n\n"
        "یه عدد بین ۱ تا ۱۸۰ بفرست (مثلاً 15)."
    )


async def prayer_reminder_minutes_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    گرفتن عدد دقیقه‌ای که کاربر بعد از زدن دکمه‌ی تنظیم دقیقه تایپ می‌کنه.
    این هندلر باید قبل از هندلر عمومی متن (general_text_handler) و در یک
    گروه جدا ثبت بشه تا وقتی کاربر منتظر این ورودی نیست، مزاحم بقیه‌ی
    پیام‌های متنی نشه (چون فقط وقتی پرچم awaiting_reminder_minutes ست
    شده باشه کاری انجام می‌ده، وگرنه بی‌سروصدا برمی‌گرده).
    """
    if not context.user_data.get("awaiting_reminder_minutes"):
        return

    text = (update.message.text or "").strip()
    user_id = update.effective_user.id

    if not text.isdigit() or not (1 <= int(text) <= 180):
        await update.message.reply_text("⚠️ لطفاً فقط یه عدد بین ۱ تا ۱۸۰ بفرست.")
        return

    minutes = int(text)
    context.user_data["awaiting_reminder_minutes"] = False
    _capture_reminder_context(update, user_id)
    set_prayer_reminder_minutes(user_id, minutes)
    await schedule_reminders_for_user(user_id, context)

    await update.message.reply_text(f"✅ یادآور روی {minutes} دقیقه‌ی قبل تنظیم شد.")
    city_code = context.user_data.get("prayer_city", 1)
    await show_reminder_menu(update, context, user_id, city_code)