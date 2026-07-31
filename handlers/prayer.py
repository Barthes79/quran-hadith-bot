# handlers/prayer.py
import logging
import html
import re
import asyncio
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


def _round_to_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_MINUTES_PATTERN = re.compile(r"(\d+)\s*دقیقه|دقیقه\s*(\d+)")


def _extract_minutes(text: str):
    """از روی متنی که کاربر برای «چند دقیقه قبل از اذان» فرستاده، عدد رو
    استخراج می‌کنه. فقط وقتی قبول می‌شه که کلمه‌ی «دقیقه» هم کنار عدد باشه
    (مثلاً «15 دقیقه» یا «۱۵ دقیقه»)؛ عدد تنها (مثل «15») دیگه قبول نیست.
    اگه چیزی پیدا نشه None برمی‌گرده."""
    normalized = text.strip().translate(_DIGIT_TRANSLATION)
    match = _MINUTES_PATTERN.search(normalized)
    if not match:
        return None
    num_str = match.group(1) or match.group(2)
    try:
        return int(num_str)
    except (TypeError, ValueError):
        return None


async def _rebuild_todays_schedule(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """کل زمان‌بندی امروز رو از صفر می‌سازه (جاب‌های قبلیِ امروز رو پاک می‌کنه
    و دوباره می‌سازه). این‌طوری هم جاب شبانه و هم هر تغییر تنظیماتِ لحظه‌ای
    یک کاربر، همیشه از یک منطق واحد رد می‌شن و باکت‌بندیِ پیام‌های گروهی
    (چند کاربر که هم‌زمان توی یه گروه یادآور دارن) درست می‌مونه.

    پیام خصوصی همیشه جدا جدا برای هر کاربر می‌ره (نمیشه پیوی چند نفر رو
    ادغام کرد)، ولی پیام تگِ گروهی برای کاربرهایی که توی یه گروه، برای
    همون اذان و همون لحظه یادآور فعال دارن، توی یک پیام واحد ادغام می‌شه
    تا گروه با چندتا پیام جدا شلوغ نشه. اون پیام گروهی هم بعد از رسیدن وقت
    اذان (+ چند دقیقه فرصت) خودکار حذف می‌شه تا توی تاریخچه‌ی گروه نمونه.

    برمی‌گردونه True اگه job_queue فعال بود و زمان‌بندی واقعاً انجام شد،
    وگرنه False (یعنی هیچ یادآوری‌ای هیچ‌وقت خودکار ارسال نمی‌شه)."""
    if not context.job_queue:
        logger.error("زمان‌بندی یادآور ممکن نیست: job_queue فعال نیست (احتمالاً پکیج APScheduler/job-queue نصب نشده)")
        return False

    now = datetime.now(IRAN_TZ)
    today_str = str(now.date())

    # پاک کردن جاب‌های امروز (خصوصی، گروهی و حذفِ گروهی) تا از صفر بسازیم
    for j in context.job_queue.jobs():
        if j.name and j.name.startswith("prayer_") and today_str in j.name:
            j.schedule_removal()

    rows = get_all_enabled_prayer_reminders()

    # کش اوقات شرعی هر شهر، چون معمولاً چند کاربر شهر یکسان دارن
    city_cache: dict = {}

    def _times_for(city_code):
        if city_code not in city_cache:
            city_cache[city_code] = get_prayer_times(city_code)
        return city_cache[city_code]

    # کلید: (group_chat_id, key, دقیقه‌ی رند شده) -> اطلاعات پیام ادغامی
    group_batches: dict = {}

    for row in rows:
        user_id = row["user_id"]
        result = _times_for(row["city_code"])
        if not result["success"]:
            logger.warning(f"عدم امکان زمان‌بندی یادآور برای کاربر {user_id}: خطا در دریافت اوقات شرعی")
            continue

        for key, (field, label) in PRAYER_FIELD_MAP.items():
            if not row[f"remind_{key}"]:
                continue

            remind_dt = _compute_remind_datetime(now, result.get(field, ""), row["minutes_before"])
            if not remind_dt:
                logger.warning(f"[یادآور] کاربر {user_id} / {key}: فرمت ساعت اذان نامعتبر بود: {result.get(field)!r}")
                continue
            if remind_dt <= now:
                continue

            # پیام خصوصی: مستقل برای هر کاربر
            context.job_queue.run_once(
                send_prayer_reminder_private,
                when=remind_dt,
                data={"user_id": user_id, "label": label, "minutes_before": row["minutes_before"]},
                name=f"prayer_private_{user_id}_{key}_{today_str}",
            )

            # پیام گروهی: توی باکتِ همون گروه/اذان/دقیقه جمع می‌شه
            if row["group_chat_id"]:
                azan_dt = remind_dt + timedelta(minutes=row["minutes_before"])
                bucket_key = (row["group_chat_id"], key, _round_to_minute(remind_dt))
                bucket = group_batches.setdefault(bucket_key, {
                    "remind_dt": remind_dt,
                    "azan_dt": azan_dt,
                    "label": label,
                    "minutes_before": row["minutes_before"],
                    "users": [],
                })
                bucket["users"].append((user_id, row["user_name"] or "کاربر"))

    for (group_chat_id, key, _minute), batch in group_batches.items():
        job_name = f"prayer_group_{group_chat_id}_{key}_{today_str}_{batch['remind_dt'].strftime('%H%M')}"
        logger.info(
            f"[یادآور] گروه {group_chat_id} / {key}: پیام ادغامی برای {len(batch['users'])} "
            f"کاربر در ساعت {batch['remind_dt'].strftime('%H:%M:%S')} زمان‌بندی شد"
        )
        context.job_queue.run_once(
            send_prayer_reminder_group,
            when=batch["remind_dt"],
            data={
                "group_chat_id": group_chat_id,
                "label": batch["label"],
                "minutes_before": batch["minutes_before"],
                "users": batch["users"],
                "azan_dt": batch["azan_dt"],
            },
            name=job_name,
        )

    return True


async def schedule_reminders_for_user(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """بلافاصله بعد از تغییر تنظیمات یادآور توسط کاربر صدا زده می‌شود تا همون روز
    هم اذان‌های باقی‌مانده زمان‌بندی بشن (منتظر جاب نیمه‌شب نمونیم). چون
    پیام‌های گروهی ادغام می‌شن، کل زمان‌بندی امروز از نو ساخته می‌شه.
    برمی‌گردونه True/False (نتیجه‌ی _rebuild_todays_schedule)."""
    return await _rebuild_todays_schedule(context)


async def schedule_daily_prayer_reminders(context: ContextTypes.DEFAULT_TYPE):
    """جاب روزانه: هر روز خیلی زود صبح اجرا می‌شود و زمان‌بندی امروز رو می‌سازه."""
    await _rebuild_todays_schedule(context)


async def _send_reminder_messages(context: ContextTypes.DEFAULT_TYPE, *, user_id: int, label: str,
                                   minutes_before: int, group_chat_id, user_name: str, is_test: bool = False):
    """پیام یادآوری رو هم در پیوی کاربر، هم (در صورت وجود) با تگ کردنش در گروه
    مربوطه می‌فرسته. هم توسط جاب واقعی زمان‌بندی‌شده استفاده می‌شه، هم توسط
    دستور تست /prayer_test_reminder."""
    safe_name = html.escape(user_name or "کاربر")
    prefix = "🧪 [تستی] " if is_test else ""

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"{prefix}⏰ {minutes_before} دقیقه تا {label} مانده است.",
        )
    except Exception as e:
        logger.error(f"خطا در ارسال یادآور اذان (پیوی) به کاربر {user_id}: {e}")
        raise

    if group_chat_id:
        mention = f'<a href="tg://user?id={user_id}">{safe_name}</a>'
        try:
            await context.bot.send_message(
                chat_id=group_chat_id,
                text=f"{prefix}⏰ {mention} {minutes_before} دقیقه تا {label} مانده است.",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"خطا در ارسال یادآور اذان (گروه {group_chat_id}) برای کاربر {user_id}: {e}")
            raise


async def send_prayer_reminder_private(context: ContextTypes.DEFAULT_TYPE):
    """جاب یک‌بارمصرف: فقط پیام خصوصی رو به یک کاربر می‌فرسته."""
    data = context.job.data
    try:
        await context.bot.send_message(
            chat_id=data["user_id"],
            text=f"⏰ {data['minutes_before']} دقیقه تا {data['label']} مانده است.",
        )
    except Exception as e:
        logger.error(f"خطا در ارسال یادآور اذان (پیوی) به کاربر {data['user_id']}: {e}")


async def send_prayer_reminder_group(context: ContextTypes.DEFAULT_TYPE):
    """جاب یک‌بارمصرف: یک پیام واحد که همه‌ی کاربرهایی که توی این گروه، برای
    همین اذان و همین لحظه یادآور فعال دارن رو با هم تگ می‌کنه (به‌جای یه پیام
    جدا برای هرکدوم که گروه رو شلوغ می‌کرد). بعد از رسیدن وقت اذان (+ ۱۰ دقیقه
    فرصت)، خودش رو از گروه پاک می‌کنه تا توی تاریخچه‌ی گروه انباشته نشه."""
    data = context.job.data
    mentions = "  ".join(
        f'<a href="tg://user?id={uid}">{html.escape(name)}</a>'
        for uid, name in data["users"]
    )
    try:
        msg = await context.bot.send_message(
            chat_id=data["group_chat_id"],
            text=f"⏰ {mentions}\n{data['minutes_before']} دقیقه تا {data['label']} مانده است.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"خطا در ارسال یادآور اذان (گروه {data['group_chat_id']}): {e}")
        return

    if context.job_queue:
        delete_at = data["azan_dt"] + timedelta(minutes=10)
        context.job_queue.run_once(
            _delete_group_reminder_message,
            when=delete_at,
            data={"chat_id": data["group_chat_id"], "message_id": msg.message_id},
            name=f"prayer_group_delete_{data['group_chat_id']}_{msg.message_id}",
        )


async def _delete_group_reminder_message(context: ContextTypes.DEFAULT_TYPE):
    """جاب پاکسازی: پیام یادآور گروهیِ ادغام‌شده رو بعد از گذشتن وقت اذان
    (+ چند دقیقه فرصت) حذف می‌کنه تا توی تاریخچه‌ی گروه باقی نمونه."""
    data = context.job.data
    try:
        await context.bot.delete_message(chat_id=data["chat_id"], message_id=data["message_id"])
    except Exception as e:
        logger.warning(f"عدم امکان حذف پیام یادآور گروهی (چت {data['chat_id']}, پیام {data['message_id']}): {e}")


async def prayer_test_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دستور /prayer_test_reminder -- برای تست فوریِ یادآور، بدون نیاز به صبر
    کردن تا ساعت واقعی اذان. دقیقاً همون مسیر ارسال واقعی رو طی می‌کنه
    (هم پیوی، هم تگ در گروه اگه قبلاً از داخل یه گروه یادآور تنظیم شده باشه)،
    فقط با متن «[تستی]» مشخص میشه که واقعی نیست.
    """
    user = update.effective_user
    reminder = get_prayer_reminder(user.id)

    group_chat_id = reminder["group_chat_id"] if reminder else None
    user_name = (reminder["user_name"] if reminder and reminder["user_name"] else None) or _display_name_fallback(user)
    minutes_before = reminder["minutes_before"] if reminder else 10

    try:
        await _send_reminder_messages(
            context,
            user_id=user.id,
            label="🌅 اذان صبح",
            minutes_before=minutes_before,
            group_chat_id=group_chat_id,
            user_name=user_name,
            is_test=True,
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ ارسال تستی با خطا مواجه شد: {e}\n\n"
            "نکته: اگه پیام پیوی می‌گیری ولی توی گروه نه، احتمالاً ربات دیگه "
            "توی اون گروه ادمین/عضو نیست یا اجازه‌ی ارسال پیام نداره."
        )
        return

    extra = " و پیام تگ‌شده توی گروهی که ازش تنظیمش کرده بودی" if group_chat_id else " (یادآور از پیوی تنظیم شده بود، پس فقط همینجا فرستاده شد)"
    await update.message.reply_text(f"✅ پیام تستی فرستاده شد{extra}.\n\nاگه این پیام رو دیدی، یعنی ارسال واقعی هم موقعش درست کار می‌کنه؛ فقط زمان‌بندیش رو تو لاگ سرور می‌تونی چک کنی.")


def _display_name_fallback(user) -> str:
    return user.first_name or user.full_name or "کاربر"


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
        [InlineKeyboardButton("⏰ تنظیم یادآور", callback_data=f"prayer_reminder_{user_id}")],
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
    """نمایش اوقات شرعی همه‌ی شهرهای موجود در CITY_CODES"""
    query = update.callback_query

    # بررسی مالکیت
    if not check_ownership(update, context):
        await query.answer("❌ این دکمه متعلق به شما نیست!", show_alert=True)
        return

    await query.answer("⏳ در حال دریافت اوقات شرعی همه‌ی شهرها...")
    user_id = update.effective_user.id

    # همه‌ی شهرهای CITY_CODES (نه فقط چندتای ثابت)، مرتب بر اساس نام
    all_cities = sorted(CITY_CODES.items())

    # درخواست‌ها رو هم‌زمان (نه یکی‌یکی) می‌گیریم چون ۳۰+ شهر داریم و
    # get_prayer_times یک تابع sync/بلاک‌کننده‌ست؛ اگه یکی‌یکی صدا بزنیم
    # ممکنه طول بکشه و کاربر فکر کنه ربات هنگ کرده.
    loop = asyncio.get_running_loop()
    results = await asyncio.gather(
        *[loop.run_in_executor(None, get_prayer_times, code) for _, code in all_cities]
    )

    blocks = []
    for (city_name, _), result in zip(all_cities, results):
        if result["success"]:
            blocks.append(
                f"**{city_name}:**\n"
                f"🌅 صبح: {result['fajr']}   🌤 ظهر: {result['noon']}   🌙 مغرب: {result['maghrib']}"
            )
        else:
            blocks.append(f"⚠️ {city_name}: خطا در دریافت")

    # چون همه‌ی شهرها با هم ممکنه از سقف ۴۰۹۶ کاراکتری پیام تلگرام رد بشن،
    # بلوک‌ها رو به چند پیام تقسیم می‌کنیم.
    MAX_CHARS = 3500
    chunks = []
    current = "🕌 *اوقات شرعی همه‌ی شهرها*\n\n"
    for block in blocks:
        if len(current) + len(block) + 2 > MAX_CHARS:
            chunks.append(current)
            current = ""
        current += block + "\n\n"
    if current:
        chunks.append(current)

    back_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"prayer_back_{user_id}")]
    ])

    # چانک اول جای همون پیامی میره که دکمه روش زده شده؛ بقیه پیام جدیدن
    await query.edit_message_text(
        chunks[0],
        parse_mode="Markdown",
        reply_markup=back_markup if len(chunks) == 1 else None,
    )
    for i, chunk in enumerate(chunks[1:], start=1):
        is_last = (i == len(chunks) - 1)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=chunk,
            parse_mode="Markdown",
            reply_markup=back_markup if is_last else None,
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

    reminder = get_prayer_reminder(user_id)
    any_on = any([reminder["remind_fajr"], reminder["remind_noon"], reminder["remind_maghrib"]])
    upsert_prayer_reminder(user_id, city_code=city_code, enabled=1 if any_on else 0)

    # همیشه زمان‌بندی امروز رو از نو می‌سازیم (چه فعال شده باشه چه خاموش)،
    # چون rebuild خودش جاب‌های قدیمی امروز رو پاک و از صفر می‌سازه؛ این‌طوری
    # خاموش کردن هم فوراً روی جاب‌های زمان‌بندی‌شده اثر می‌کنه.
    scheduled_ok = await schedule_reminders_for_user(user_id, context)

    await query.answer("✅ فعال شد" if new_value else "❌ غیرفعال شد")
    if new_value and not scheduled_ok:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "⚠️ تنظیماتت ذخیره شد، ولی زمان‌بند (Job Queue) ربات الان فعال نیست، "
                    "پس این یادآور واقعاً ارسال نمی‌شه. لطفاً به ادمین ربات بگو پکیج job-queue رو "
                    "نصب/فعال کنه: <code>pip install \"python-telegram-bot[job-queue]\"</code>"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.debug(f"عدم امکان ارسال هشدار job_queue به کاربر {user_id}: {e}")
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
        "عدد رو حتماً همراه با کلمه‌ی «دقیقه» بنویس، مثلاً: 15 دقیقه\n"
        "(بین ۱ تا ۱۸۰)"
    )


async def prayer_reminder_minutes_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    گرفتن عدد دقیقه‌ای که کاربر بعد از زدن دکمه‌ی تنظیم دقیقه تایپ می‌کنه.

    این تابع دیگه یک MessageHandler مستقل تلگرام نیست (قبلاً بود، ولی چون
    توی یک گروه جدا ثبت می‌شد، هم‌زمان با general_text_handler هم اجرا
    می‌شد -- یعنی وقتی کاربر عدد دقیقه رو می‌فرستاد، هم اینجا پردازش
    می‌شد هم به‌اشتباه به‌عنوان سرچ آزاد فرستاده می‌شد). حالا general_text_handler
    مستقیم این تابع رو صدا می‌زنه و مقدار برگشتی (True یعنی «این پیام مال
    من بود و مصرفش کردم») رو چک می‌کنه؛ اگه True بود، پردازش پیام همون‌جا
    متوقف می‌شه و به آیه‌یاب/سرچ نمی‌رسه.

    خروجی:
        True  -> پیام مربوط به این جریان بود (چه معتبر چه نامعتبر) و پردازش شد.
        False -> کاربر منتظر ورودی دقیقه نبود؛ پیام دست‌نخورده برای بقیه‌ی
                 هندلرها باقی می‌مونه.
    """
    if not context.user_data.get("awaiting_reminder_minutes"):
        return False

    text = (update.message.text or "").strip()
    user_id = update.effective_user.id

    minutes = _extract_minutes(text)
    if minutes is None or not (1 <= minutes <= 180):
        await update.message.reply_text(
            "⚠️ باید عدد رو حتماً همراه با کلمه‌ی «دقیقه» بنویسی، مثلاً: 15 دقیقه\n"
            "(عدد باید بین ۱ تا ۱۸۰ باشه.)"
        )
        return True

    context.user_data["awaiting_reminder_minutes"] = False
    _capture_reminder_context(update, user_id)
    set_prayer_reminder_minutes(user_id, minutes)
    scheduled_ok = await schedule_reminders_for_user(user_id, context)

    await update.message.reply_text(f"✅ یادآور روی {minutes} دقیقه‌ی قبل تنظیم شد.")
    if not scheduled_ok:
        await update.message.reply_text(
            "⚠️ ولی زمان‌بند (Job Queue) ربات الان فعال نیست، پس این یادآور واقعاً ارسال نمی‌شه. "
            "لطفاً به ادمین ربات اطلاع بده."
        )
    city_code = context.user_data.get("prayer_city", 1)
    await show_reminder_menu(update, context, user_id, city_code)
    return True