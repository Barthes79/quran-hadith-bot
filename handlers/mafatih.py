import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

logger = logging.getLogger(__name__)

# --- کیبوردها (همان کدهای قبلی شما) ---
def get_main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗓️ تعقیبات و اعمال هفته", callback_data="mafcat_daily_weekly")],
        [InlineKeyboardButton("🤲 ادعیه و مناجات‌های مشهور", callback_data="mafcat_famous_supplications")],
        [InlineKeyboardButton("🌙 اعمال ماه‌های سال", callback_data="mafcat_lunar_months")],
        [InlineKeyboardButton("🕌 زیارات و عتبات", callback_data="mafcat_ziyarats")],
        [InlineKeyboardButton("📚 باقیات صالحات و ملحقات", callback_data="mafcat_appendices_baqiyat")],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی ربات", callback_data="menu_main")]
    ])

# [نکته: سایر توابع get_keyboard_... که در فایل قبلی داشتید را دقیقاً در همین جای فایل قرار دهید]
# (برای صرفه‌جویی در فضا اینجا تکرار نشد، اما شما حتماً همه را کپی کنید)

# ==========================================
# بخش اصلاح شده برای نمایش متن و صوت
# ==========================================

async def _render_mafatih_item(query, context: ContextTypes.DEFAULT_TYPE, item_id: str, page: int = 0):
    item = db.get_mafatih_item_flexible(item_id)
    if not item:
        await query.message.reply_text("❌ محتوا یافت نشد.")
        return

    # متن اصلی
    header = f"✨ <b>{item['title']}</b>\n\n"
    full_body = (item.get('arabic_text') or "") + "\n\n" + (item.get('translation_text') or "")
    
    # صفحه‌بندی ساده
    chunks = [full_body[i:i+3500] for i in range(0, len(full_body), 3500)]
    total_pages = len(chunks)
    page = max(0, min(page, total_pages - 1))
    text = header + chunks[page]

    # دکمه‌ها
    buttons = [[InlineKeyboardButton("🏠 منوی اصلی", callback_data="mafmenu")]]
    markup = InlineKeyboardMarkup(buttons)

    # بخش جدید: ارسال صوت
    audio_id = item.get('audio_file_id')
    
    try:
        await query.message.delete() # حذف پیام قبلی
        if audio_id and page == 0:
            await query.message.reply_audio(audio=audio_id, caption=text[:1024], parse_mode="HTML", reply_markup=markup)
        else:
            await query.message.chat.send_message(text, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        logger.error(f"خطا در ارسال: {e}")
        await query.message.chat.send_message(text, parse_mode="HTML", reply_markup=markup)

async def mafatih_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = query.data.replace("mafitem_", "")
    await _render_mafatih_item(query, context, item_id)

async def mafatih_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📖 بخش مفاتیح الجنان:", reply_markup=get_main_menu_keyboard())

async def mafatih_menu_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📖 بخش مفاتیح الجنان:", reply_markup=get_main_menu_keyboard())

# [سایر هندلرهای دسته‌بندی mafatih_category_callback و غیره را هم اینجا قرار دهید]