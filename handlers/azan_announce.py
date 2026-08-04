# handlers/azan_announce.py
"""
اعلام اذان در گروه‌ها.

جریان کار:
1. کاربر توی پیوی، از منوی «اوقات شرعی»، دکمه‌ی «📢 افزودن اعلام اذان به گروه»
   رو می‌زنه. این دکمه از نوع switch_inline_query_chosen_chat هست؛ یعنی
   تلگرام یه لیست انتخاب گروه (فقط گروه/سوپرگروه) به کاربر نشون می‌ده.
2. کاربر یه گروه رو انتخاب می‌کنه. تلگرام خودکار یه inline query با متن
   AZAN_SETUP_TOKEN می‌فرسته که توی handlers/inline.py گرفته می‌شه و یه
   نتیجه‌ی تکی (پنل تنظیمات با مقادیر پیش‌فرض) برمی‌گردونه.
3. کاربر همون نتیجه رو تایید می‌کنه و پیام پنل مستقیم توی همون گروه که
   انتخاب کرده فرستاده می‌شه.
4. از اونجا به بعد، فقط ادمین‌های همون گروه می‌تونن با دکمه‌های پنل
   (که همه با پیشوند azangrp_ هستن) شهر/فعال‌بودن هر اذان/پخش صوت رو
   تغییر بدن. اولین تغییر، ردیف تنظیمات اون گروه رو توی دیتابیس می‌سازه.

زمان‌بندی واقعیِ ارسال پیام سرِ وقتِ اذان هم شبیه یادآور اذان (handlers/prayer.py)
با جاب روزانه + rebuild فوری بعد از هر تغییر تنظیمات انجام می‌شه.
"""

import logging
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQueryResultArticle, InputTextMessageContent,
)
from telegram.ext import ContextTypes, filters

from config import ADMIN_IDS
from database import (
    get_azan_group_settings, update_azan_group_settings,
    get_all_azan_enabled_groups, get_azan_audio_asset, set_azan_audio_asset,
)
from handlers.prayer import CITY_CODES, get_prayer_times
from handlers.admin import is_group_admin

logger = logging.getLogger(__name__)

IRAN_TZ = ZoneInfo("Asia/Tehran")

# متنی که به‌عنوان query در switch_inline_query_chosen_chat فرستاده می‌شه و
# توی handlers/inline.py گرفته می‌شه. اگه این رو عوض کردی، همون‌جا هم عوض کن.
AZAN_SETUP_TOKEN = "azan_setup"

# سطر اول متن پنل (هم توی placeholder و هم توی پنل واقعی)، برای شناسایی
# پیامِ inline که وارد گروه شده استفاده می‌شود.
AZAN_PANEL_MARKER = "🔔 تنظیمات اعلام اذان این گروه"

CITY_CODE_TO_NAME = {code: name for name, code in CITY_CODES.items()}

_DEFAULT_AZAN_SETTINGS = {
    "city_code": 1,
    "azan_fajr": 0,
    "azan_noon": 0,
    "azan_maghrib": 0,
    "audio_on": 1,
}

AZAN_FIELD_MAP = {
    # کلید داخلی -> (فیلد پاسخ get_prayer_times, ستون دیتابیس, برچسب فارسی)
    "fajr": ("fajr", "azan_fajr", "🌅 اذان صبح"),
    "noon": ("noon", "azan_noon", "🌤 اذان ظهر"),
    "maghrib": ("maghrib", "azan_maghrib", "🌙 اذان مغرب"),
}

# یک جمله‌ی خاص و دل‌نشین، مخصوص هر اذان (زیر متن اصلی اعلام اذان نوشته می‌شه)
AZAN_TAGLINES = {
    "fajr": "🌅 در سکوت سحر، دلی بیدار برای او کافی‌ست.",
    "noon": "🌤 لحظه‌ای دست از دنیا بکشیم، رو به قبله و رو به آرامش.",
    "maghrib": "🌙 هوا رو به تاریکی می‌رود و دل رو به نور؛ وقتِ راز و نیاز است.",
}

TOGGLE_COLUMN_MAP = {
    "audio": "audio_on",
    "fajr": "azan_fajr",
    "noon": "azan_noon",
    "maghrib": "azan_maghrib",
}


def _mark(flag) -> str:
    return "✅" if flag else "❌"


def _city_name(code) -> str:
    return CITY_CODE_TO_NAME.get(code, "تهران")


def _azan_panel_text(settings) -> str:
    return (
        f"*{AZAN_PANEL_MARKER}*\n\n"
        f"🏙 شهر: *{_city_name(settings['city_code'])}*\n"
        f"🔊 پخش صوت اذان: {_mark(settings['audio_on'])}\n"
        f"🌅 اذان صبح: {_mark(settings['azan_fajr'])}\n"
        f"🌤 اذان ظهر: {_mark(settings['azan_noon'])}\n"
        f"🌙 اذان مغرب: {_mark(settings['azan_maghrib'])}\n\n"
        "با دکمه‌های زیر تنظیمش کن. فقط ادمین‌های همین گروه می‌تونن تغییرش بدن."
    )


def _azan_panel_keyboard(settings) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(f"🏙 شهر: {_city_name(settings['city_code'])}", callback_data="azangrp_citylist_0")],
        [InlineKeyboardButton(f"🔊 صوت اذان {_mark(settings['audio_on'])}", callback_data="azangrp_toggle_audio")],
        [
            InlineKeyboardButton(f"🌅 صبح {_mark(settings['azan_fajr'])}", callback_data="azangrp_toggle_fajr"),
            InlineKeyboardButton(f"🌤 ظهر {_mark(settings['azan_noon'])}", callback_data="azangrp_toggle_noon"),
        ],
        [InlineKeyboardButton(f"🌙 مغرب {_mark(settings['azan_maghrib'])}", callback_data="azangrp_toggle_maghrib")],
        [InlineKeyboardButton("✖️ بستن", callback_data="azangrp_close")],
    ]
    return InlineKeyboardMarkup(buttons)


# ==========================================
# ساخت نتیجه‌ی اینلاین (مرحله‌ی انتخاب گروه)
# ==========================================

def build_azan_setup_inline_result() -> InlineQueryResultArticle:
    """
    این پیام صرفاً یک placeholder موقته که با انتخاب گروه توی همون گروه فرستاده
    می‌شه. نکته‌ی مهم: پیامی که از طریق inline mode فرستاده می‌شه، از دید تلگرام
    «پیامِ ارسالی توسط ربات» حساب نمی‌شه (بلکه با inline_message_id شناخته
    می‌شه، نه chat_id/message_id عادی)، پس دکمه‌های callback روش هیچ‌وقت
    نمی‌تونن بفهمن توی کدوم گروهن. برای همین این پیام هیچ دکمه‌ای نداره؛
    handle_incoming_azan_panel_message به‌محض دیدنش (به‌عنوان یک پیام معمولی
    داخل گروه) اون رو پاک می‌کنه و یک پیام *واقعی* از طرف ربات با پنل کامل
    و دکمه‌های کاربردی جایگزینش می‌کنه.
    """
    text = (
        f"{AZAN_PANEL_MARKER}\n\n"
        "⏳ در حال آماده‌سازی پنل تنظیمات...\n"
        "(اگه چند ثانیه بعد چیزی عوض نشد، یعنی ربات هنوز عضو این گروه نیست؛ "
        "اول ربات رو به گروه اضافه کن، بعد دوباره امتحان کن.)"
    )
    return InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title="🔔 راه‌اندازی اعلام اذان در این گروه",
        description="با انتخاب این گزینه، پنل تنظیمات اعلام اذان توی همین گروه فرستاده می‌شه.",
        input_message_content=InputTextMessageContent(text),
    )


async def handle_incoming_azan_panel_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    وقتی همون پیامِ inline (placeholder بالا) واقعاً توی یه گروه فرود بیاد،
    این تابع به‌عنوان یک پیام معمولی گروهی می‌بیندش (چون ربات عضو گروهه)،
    پاکش می‌کنه و یک پیام *واقعی* با پنل کامل جایگزینش می‌کند تا دکمه‌ها
    درست کار کنن.

    باید از general_text_handler (توی main.py) صدا زده بشه، قبل از هر
    پردازش دیگه‌ای. خروجی True یعنی «این پیام مصرف شد»، False یعنی «ربطی
    نداشت، بذار بقیه‌ی هندلرها پردازشش کنن».
    """
    message = update.message
    if not message or not message.via_bot or message.via_bot.id != context.bot.id:
        return False
    if not message.text or not message.text.startswith(AZAN_PANEL_MARKER):
        return False

    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        return False

    chat_id = chat.id
    settings = get_azan_group_settings(chat_id)  # اگه ردیفی نبود، همین‌جا با مقادیر پیش‌فرض ساخته می‌شه

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=_azan_panel_text(settings),
            parse_mode="Markdown",
            reply_markup=_azan_panel_keyboard(settings),
        )
    except Exception as e:
        logger.error(f"خطا در ارسال پنل واقعیِ اعلام اذان برای گروه {chat_id}: {e}")
        return True

    try:
        await message.delete()
    except Exception:
        pass  # اگه ربات دسترسی حذف نداشت مهم نیست؛ فقط placeholder قدیمی می‌مونه (بی‌ضرر)

    return True


# ==========================================
# رندر پنل و لیست شهرها
# ==========================================

async def _render_panel(query, chat_id: int):
    settings = get_azan_group_settings(chat_id)
    try:
        await query.edit_message_text(
            _azan_panel_text(settings),
            parse_mode="Markdown",
            reply_markup=_azan_panel_keyboard(settings),
        )
    except Exception as e:
        logger.debug(f"عدم امکان ویرایش پنل اعلام اذان گروه {chat_id}: {e}")


async def _render_city_list(query, page: int):
    items = sorted(CITY_CODES.items())
    page_size = 10
    total_pages = (len(items) + page_size - 1) // page_size
    page = max(0, min(page, total_pages - 1))

    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(items))

    buttons = [
        [InlineKeyboardButton(f"📍 {name}", callback_data=f"azangrp_city_{code}")]
        for name, code in items[start_idx:end_idx]
    ]

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"azangrp_citylist_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"azangrp_citylist_{page + 1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="azangrp_main")])

    await query.edit_message_text(
        f"🏙 انتخاب شهر برای اعلام اذان (صفحه {page + 1} از {total_pages}):",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ==========================================
# روتر مرکزی دکمه‌های پنل (پیشوند azangrp_)
# ==========================================

async def azan_setup_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat = update.effective_chat

    if chat.type not in ("group", "supergroup"):
        await query.answer("این قابلیت فقط داخل گروه‌ها کار می‌کند.", show_alert=True)
        return

    chat_id = chat.id

    if data == "azangrp_close":
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    if not await is_group_admin(update):
        await query.answer("فقط ادمین‌های گروه می‌تونن این تنظیمات رو تغییر بدن.", show_alert=True)
        return

    if data == "azangrp_main":
        await query.answer()
        await _render_panel(query, chat_id)
        return

    if data.startswith("azangrp_toggle_"):
        field = data.replace("azangrp_toggle_", "")
        column = TOGGLE_COLUMN_MAP.get(field)
        if not column:
            await query.answer()
            return
        settings = get_azan_group_settings(chat_id)
        new_val = 0 if settings[column] else 1
        update_azan_group_settings(chat_id, **{column: new_val})
        await _rebuild_todays_azan_schedule(context)
        await query.answer("✅ ذخیره شد")
        await _render_panel(query, chat_id)
        return

    if data.startswith("azangrp_citylist_"):
        await query.answer()
        try:
            page = int(data.replace("azangrp_citylist_", ""))
        except ValueError:
            page = 0
        await _render_city_list(query, page)
        return

    if data.startswith("azangrp_city_"):
        try:
            code = int(data.replace("azangrp_city_", ""))
        except ValueError:
            await query.answer()
            return
        update_azan_group_settings(chat_id, city_code=code)
        await _rebuild_todays_azan_schedule(context)
        await query.answer("✅ شهر ذخیره شد")
        await _render_panel(query, chat_id)
        return

    await query.answer()


# ==========================================
# زمان‌بندی و ارسال واقعیِ اعلام اذان
# ==========================================

async def _rebuild_todays_azan_schedule(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """زمان‌بندیِ امروزِ همه‌ی گروه‌هایی که اعلام اذان فعال دارن رو از صفر می‌سازه.
    برمی‌گردونه True اگه job_queue فعال بود، وگرنه False."""
    if not context.job_queue:
        logger.error("زمان‌بندی اعلام اذان ممکن نیست: job_queue فعال نیست.")
        return False

    now = datetime.now(IRAN_TZ)
    today_str = str(now.date())

    for j in context.job_queue.jobs():
        if j.name and j.name.startswith("azangrp_job_") and today_str in j.name:
            j.schedule_removal()

    rows = get_all_azan_enabled_groups()

    city_cache: dict = {}

    def _times_for(city_code):
        if city_code not in city_cache:
            city_cache[city_code] = get_prayer_times(city_code)
        return city_cache[city_code]

    for row in rows:
        chat_id = row["chat_id"]
        result = _times_for(row["city_code"])
        if not result["success"]:
            logger.warning(f"عدم امکان زمان‌بندی اعلام اذان برای گروه {chat_id}: خطا در دریافت اوقات شرعی")
            continue

        city_name = result.get("city") or _city_name(row["city_code"])

        for key, (field, col, label) in AZAN_FIELD_MAP.items():
            if not row[col]:
                continue

            time_str = result.get(field, "")
            try:
                hh, mm = map(int, time_str.strip().split(":")[:2])
            except (ValueError, AttributeError):
                logger.warning(f"[اعلام اذان] گروه {chat_id} / {key}: فرمت ساعت نامعتبر: {time_str!r}")
                continue

            azan_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if azan_dt <= now:
                continue

            context.job_queue.run_once(
                send_azan_announcement,
                when=azan_dt,
                data={
                    "chat_id": chat_id,
                    "label": label,
                    "city_name": city_name,
                    "audio_on": bool(row["audio_on"]),
                    "key": key,
                },
                name=f"azangrp_job_{chat_id}_{key}_{today_str}",
            )

    return True


async def schedule_daily_azan_announcements(context: ContextTypes.DEFAULT_TYPE):
    """جاب روزانه: هر روز زمان‌بندی اعلام اذان امروز رو برای همه‌ی گروه‌های فعال می‌سازه."""
    await _rebuild_todays_azan_schedule(context)


async def send_azan_announcement(context: ContextTypes.DEFAULT_TYPE):
    """جاب یک‌بارمصرف: سرِ وقتِ اذان، پیام (و در صورت فعال بودن، صوت) رو به گروه می‌فرسته.

    نکته‌ی مهم درباره‌ی کپشن در تلگرام: برخلاف عکس/ویدیو (که کپشن پایینشونه)،
    برای فایل صوتی (send_audio) کپشن *بالای* پلیر نمایش داده می‌شه. برای همین
    فرستادن متن به‌عنوان caption همون پیام صوتی، دقیقاً همون چیدمانِ «متن بالا،
    پلیر پایین، همه در یک پیام» رو می‌ده که خواسته شده بود.
    """
    data = context.job.data
    chat_id = data["chat_id"]
    tagline = AZAN_TAGLINES.get(data.get("key"), "")
    text = f"🕌 وقت {data['label']} به افق {data['city_name']} فرا رسید."
    if tagline:
        text += f"\n\n{tagline}"

    asset = None
    if data.get("audio_on"):
        candidate = get_azan_audio_asset()
        if candidate and candidate["file_id"]:
            asset = candidate

    if asset:
        try:
            if asset["file_type"] == "voice":
                await context.bot.send_voice(chat_id=chat_id, voice=asset["file_id"], caption=text)
            else:
                await context.bot.send_audio(chat_id=chat_id, audio=asset["file_id"], caption=text)
            return
        except Exception as e:
            logger.error(f"خطا در ارسال صوت اذان (با کپشن) به گروه {chat_id}: {e}")
            # اگه ارسال صوت fail شد، حداقل متن رو جدا بفرست تا گروه بی‌خبر نمونه

    try:
        await context.bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        logger.error(f"خطا در ارسال اعلام اذان به گروه {chat_id}: {e}")


# ==========================================
# آپلود صوت سراسری اذان (فقط ادمین‌های ربات - ADMIN_IDS)
# ==========================================

# کلید: (user_id, chat_id) — عمداً chat_id هم توی کلید هست، با اینکه صوتِ
# ذخیره‌شده در نهایت سراسری و برای همه‌ی گروه‌هاست. دلیلش اینه که اگه فقط
# user_id کلید باشه، اولین ویس/صوتی که همون ادمین توی *هر چت دیگه‌ای* (مثلاً
# پیوی با یه دوست، یا یه گروه نامرتبط) بفرسته هم اشتباهی به‌عنوان صدای اذان
# بلعیده و سراسری پخش می‌شه. با scope کردن به همون چتی که /setazanaudio توش
# زده شده، فقط صوتی که ادمین *در همون مکالمه* می‌فرسته گرفته می‌شه.
_PENDING_AZAN_AUDIO: set = set()


class _AzanAudioPendingFilter(filters.MessageFilter):
    def filter(self, message):
        return (
            bool(message.from_user)
            and (message.from_user.id, message.chat_id) in _PENDING_AZAN_AUDIO
        )


azan_audio_pending_filter = _AzanAudioPendingFilter()


async def set_azan_audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /setazanaudio - فقط ادمین‌های ربات. فایل صوتی بعدی که *در همین چت*
    بفرستن، به‌عنوان صدای مشترکِ اعلام اذان توی همه‌ی گروه‌ها ذخیره می‌شه."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه‌ی این دستور را ندارید.")
        return

    _PENDING_AZAN_AUDIO.add((update.effective_user.id, update.effective_chat.id))
    await update.message.reply_text(
        "🔊 الان فایل صوتیِ اذان رو (audio یا voice) همین‌جا برام بفرست تا به‌عنوان صدای پخش‌شده "
        "توی اعلام اذان همه‌ی گروه‌ها ذخیره بشه."
    )


async def azan_audio_upload_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    key = (user_id, chat_id)
    if key not in _PENDING_AZAN_AUDIO:
        return  # این ادمین توی این چت منتظر آپلود صدای اذان نیست؛ به هندلرهای دیگر بسپار

    message = update.message
    file_id, file_type = None, None
    if message.audio:
        file_id, file_type = message.audio.file_id, "audio"
    elif message.voice:
        file_id, file_type = message.voice.file_id, "voice"

    if not file_id:
        return

    set_azan_audio_asset(file_id, file_type)
    _PENDING_AZAN_AUDIO.discard(key)
    await message.reply_text("✅ صدای اذان با موفقیت ذخیره شد و از این به بعد توی اعلام اذانِ گروه‌ها پخش می‌شه.")
