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
            f"پست روزانه: {status}",
            callback_data="toggle_daily_post"
        )],
        [InlineKeyboardButton("🎲 ارسال یک حدیث الان", callback_data="group_send_now")],
    ]
    await update.message.reply_text(
        f"⚙️ تنظیمات گروه:\n\nساعت پست روزانه (به وقت سرور): {settings['daily_post_hour']}:00",
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


async def daily_post_job(context: ContextTypes.DEFAULT_TYPE):
    """
    این تابع باید هر ساعت (یا هر چند دقیقه) توسط JobQueue اجرا شود
    و بررسی کند کدام گروه‌ها باید در این ساعت پست دریافت کنند.
    """
    import datetime
    current_hour = datetime.datetime.now().hour

    groups = get_all_active_daily_groups()
    for g in groups:
        if g["daily_post_hour"] != current_hour:
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
