from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ChatType
from database import get_group_settings, update_group_settings, get_all_active_daily_groups, get_random_hadith
from handlers.hadith import format_hadith
from services.quran_api import get_ayah, get_surah_list
import random


async def is_group_admin(update: Update) -> bool:
    if update.effective_chat.type == ChatType.PRIVATE:
        return True  # در چت خصوصی محدودیتی نیست
    member = await update.effective_chat.get_member(update.effective_user.id)
    return member.status in ("administrator", "creator")


async def group_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == ChatType.PRIVATE:
        await update.message.reply_text("این دستور فقط داخل گروه‌ها کاربرد دارد.")
        return

    if not await is_group_admin(update):
        await update.message.reply_text("فقط ادمین‌های گروه می‌توانند تنظیمات را تغییر دهند.")
        return

    settings = get_group_settings(update.effective_chat.id)
    status = "✅ فعال" if settings["daily_post_enabled"] else "❌ غیرفعال"

    buttons = [
        [InlineKeyboardButton(
            f"پست خودکار: {status}",
            callback_data="toggle_daily_post"
        )],
        [InlineKeyboardButton("⏱ فاصله ارسال: هر %s ساعت" % settings["post_interval_hours"], callback_data="set_interval_menu")],
        [InlineKeyboardButton("🎲 ارسال یک حدیث الان", callback_data="group_send_now")],
    ]
    await update.message.reply_text(
        "⚙️ تنظیمات گروه:\n\n"
        "هر 1 تا 24 ساعت یک آیه یا حدیث به صورت تصادفی ارسال می‌شود.",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def toggle_daily_post_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_group_admin(update):
        await query.answer("فقط ادمین می‌تواند این کار را انجام دهد.", show_alert=True)
        return

    settings = get_group_settings(update.effective_chat.id)
    new_value = 0 if settings["daily_post_enabled"] else 1
    update_group_settings(update.effective_chat.id, daily_post_enabled=new_value)
    await query.answer("بروزرسانی شد ✅")

    status = "✅ فعال" if new_value else "❌ غیرفعال"
    await query.edit_message_text(
        f"⚙️ تنظیمات گروه:\n\nپست روزانه: {status}"
    )


async def group_send_now_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    row = get_random_hadith()
    if row:
        await context.bot.send_message(update.effective_chat.id, format_hadith(row))
    else:
        await context.bot.send_message(update.effective_chat.id, "هنوز حدیثی ثبت نشده است.")


async def interval_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_group_admin(update):
        await query.answer("فقط ادمین می‌تواند این کار را انجام دهد.", show_alert=True)
        return
    buttons = [[InlineKeyboardButton(f"هر {i} ساعت", callback_data=f"set_interval_{i}")] for i in range(1,25)]
    await query.edit_message_reply_markup(InlineKeyboardMarkup(buttons))


async def set_interval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_group_admin(update):
        await query.answer("فقط ادمین می‌تواند این کار را انجام دهد.", show_alert=True)
        return
    hours = int(query.data.split("_")[-1])
    update_group_settings(update.effective_chat.id, post_interval_hours=hours)
    await query.answer("ذخیره شد ✅")
    await query.edit_message_text(f"✅ زمان‌بندی روی هر {hours} ساعت تنظیم شد.\nبرای فعال/غیرفعال کردن از /groupsettings استفاده کنید.")


async def daily_post_job(context: ContextTypes.DEFAULT_TYPE):
    """
    این تابع باید هر ساعت (یا هر چند دقیقه) توسط JobQueue اجرا شود
    و بررسی کند کدام گروه‌ها باید در این ساعت پست دریافت کنند.
    """
    import datetime
    now = datetime.datetime.now()

    groups = get_all_active_daily_groups()
    for g in groups:
        # اجرای تقریبی بر اساس فاصله انتخابی
        interval = g["post_interval_hours"] or 1
        if now.hour % interval != 0:
            continue

        # به‌صورت تصادفی بین حدیث و آیه انتخاب کن
        if random.choice([True, False]):
            row = get_random_hadith()
            if row:
                text = format_hadith(row)
            else:
                continue
        else:
            surahs = await get_surah_list()
            surah = random.choice(surahs)
            ayah_num = random.randint(1, surah["numberOfAyahs"])
            data = await get_ayah(surah["number"], ayah_num)
            if not data:
                continue
            text = f"📖 سوره {surah['name']} - آیه {ayah_num}\n\n{data['arabic']}\n\n🔹 {data['translation']}"

        try:
            await context.bot.send_message(g["chat_id"], text)
        except Exception:
            # ربات ممکن است از گروه حذف شده باشد؛ می‌توان اینجا لاگ گرفت
            pass
