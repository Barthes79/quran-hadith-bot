# handlers/madahi.py
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from database import (
    add_madahi,
    get_madahi_occasions,
    get_madahi_by_occasion,
    get_madahi_by_id,
    delete_madahi,
    count_madahi,
)

logger = logging.getLogger(__name__)

PAGE_SIZE = 8

TYPE_LABELS = {
    "madahi": "🎙 مداحی",
    "molodi": "🎉 مولودی‌خوانی",
}


def _type_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎙 مداحی (محرم، فاطمیه، اربعین و...)", callback_data="madahi_type_madahi")],
        [InlineKeyboardButton("🎉 مولودی‌خوانی (اعیاد و میلادها)", callback_data="madahi_type_molodi")],
        [InlineKeyboardButton("⬅️ بازگشت به منو", callback_data="menu_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def madahi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /madahi - نمایش منوی اصلی مداحی/مولودی"""
    await update.message.reply_text(
        "🎙 *مداحی و مولودی*\n\nکدوم رو می‌خوای؟",
        parse_mode="Markdown",
        reply_markup=_type_keyboard(),
    )


async def madahi_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نسخه‌ی callback_query این منو، برای صدا زده شدن از منوی اصلی ربات
    (دکمه‌ی «🎙 مداحی و مولودی» توی start.py -> menu_madahi)."""
    query = update.callback_query
    await query.edit_message_text(
        "🎙 *مداحی و مولودی*\n\nکدوم رو می‌خوای؟",
        parse_mode="Markdown",
        reply_markup=_type_keyboard(),
    )


async def madahi_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاربر بین مداحی/مولودی یکی رو انتخاب کرده؛ حالا لیست مناسبت‌ها رو نشون بده"""
    query = update.callback_query
    await query.answer()

    content_type = query.data.split("_")[-1]  # madahi_type_madahi -> madahi
    context.user_data["madahi_type"] = content_type
    await show_occasion_menu(update, context, content_type)


async def show_occasion_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, content_type: str):
    occasions = get_madahi_occasions(content_type)

    # نکته‌ی مهم: توی callback_data به‌جای خودِ متن مناسبت، اندیسش توی لیست رو
    # می‌فرستیم (madahi_occ_{content_type}_{index})، چون callback_data تلگرام
    # حداکثر ۶۴ بایته و بعضی اسم‌های مناسبت (مثل «نیمه شعبان (امام زمان عج)»)
    # با پیشوندها روی هم از این حد رد می‌شن. هندلر بعدی دوباره همین لیست رو
    # می‌سازه و با همون اندیس متن واقعی رو پیدا می‌کنه.
    keyboard = []
    for idx, occ in enumerate(occasions):
        keyboard.append([InlineKeyboardButton(occ, callback_data=f"madahi_occ_{content_type}_{idx}")])
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="madahi_back_types")])

    text = f"{TYPE_LABELS[content_type]}\n\nمناسبت مورد نظرت رو انتخاب کن:"
    query = update.callback_query
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.effective_chat.send_message(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def madahi_back_types_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎙 *مداحی و مولودی*\n\nکدوم رو می‌خوای؟",
        parse_mode="Markdown",
        reply_markup=_type_keyboard(),
    )


def _list_keyboard(content_type: str, index_str: str, rows, page: int):
    start = page * PAGE_SIZE
    page_rows = rows[start:start + PAGE_SIZE]

    keyboard = []
    for row in page_rows:
        label = row["title"]
        if row["reciter"]:
            label += f" - {row['reciter']}"
        keyboard.append([InlineKeyboardButton(f"🎧 {label}", callback_data=f"madahi_play_{row['id']}")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"madahi_page_{content_type}_{index_str}_{page - 1}"))
    if start + PAGE_SIZE < len(rows):
        nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"madahi_page_{content_type}_{index_str}_{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("⬅️ بازگشت به مناسبت‌ها", callback_data=f"madahi_type_{content_type}")])
    return InlineKeyboardMarkup(keyboard)


def _resolve_occasion(content_type: str, index: int):
    """اندیسِ توی callback_data رو به متن واقعی مناسبت تبدیل می‌کنه.
    اگه لیست عوض شده باشه (مثلاً ادمین همزمان مناسبت جدید اضافه کرده) و
    اندیس دیگه معتبر نباشه، None برمی‌گردونه."""
    occasions = get_madahi_occasions(content_type)
    if 0 <= index < len(occasions):
        return occasions[index]
    return None


async def madahi_occasion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاربر یه مناسبت رو انتخاب کرده؛ لیست مداحی‌های همون مناسبت رو نشون بده"""
    query = update.callback_query
    await query.answer()

    # callback_data: madahi_occ_{content_type}_{index}
    _, _, content_type, index_str = query.data.split("_")
    occasion = _resolve_occasion(content_type, int(index_str))
    if occasion is None:
        await query.answer("⚠️ لیست به‌روزرسانی شد، دوباره امتحان کن.", show_alert=True)
        await show_occasion_menu(update, context, content_type)
        return
    await _show_occasion_list(update, context, content_type, occasion, index_str, page=0)


async def madahi_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # callback_data: madahi_page_{content_type}_{index}_{page}
    _, _, content_type, index_str, page_str = query.data.split("_")
    occasion = _resolve_occasion(content_type, int(index_str))
    if occasion is None:
        await query.answer("⚠️ لیست به‌روزرسانی شد، دوباره امتحان کن.", show_alert=True)
        await show_occasion_menu(update, context, content_type)
        return
    await _show_occasion_list(update, context, content_type, occasion, index_str, page=int(page_str))


async def _show_occasion_list(update: Update, context: ContextTypes.DEFAULT_TYPE, content_type: str, occasion: str, index_str: str, page: int):
    rows = get_madahi_by_occasion(content_type, occasion)
    query = update.callback_query

    if not rows:
        text = f"{TYPE_LABELS.get(content_type, '')}\n📌 {occasion}\n\nهنوز چیزی برای این مناسبت اضافه نشده."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"madahi_type_{content_type}")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    text = f"{TYPE_LABELS.get(content_type, '')}\n📌 {occasion}\n\n{len(rows)} مورد پیدا شد:"
    await query.edit_message_text(text, reply_markup=_list_keyboard(content_type, index_str, rows, page))


async def madahi_play_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال فایل صوتی انتخاب‌شده"""
    query = update.callback_query
    await query.answer()

    item_id = int(query.data.split("_")[-1])
    row = get_madahi_by_id(item_id)
    if not row:
        await query.answer("❌ این فایل دیگه در دسترس نیست.", show_alert=True)
        return

    caption = row["title"]
    if row["reciter"]:
        caption += f"\n🎙 {row['reciter']}"
    caption += f"\n📌 {row['occasion']}"

    try:
        await context.bot.send_audio(
            chat_id=update.effective_chat.id,
            audio=row["audio_file_id"],
            caption=caption,
        )
    except Exception as e:
        logger.error(f"خطا در ارسال فایل مداحی/مولودی {item_id}: {e}")
        await query.answer("❌ ارسال فایل با خطا مواجه شد.", show_alert=True)


# ==========================================
# دستورات ادمین
# ==========================================

async def add_madahi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دستور ادمین برای اضافه کردن یه فایل مداحی/مولودی تکی:
    /addmadahi <madahi|molodi> | <مناسبت> | <عنوان> | <اسم مداح یا -> | <audio_file_id>

    مثال:
    /addmadahi madahi | محرم و عاشورا | السلام علیک یا اباعبدالله | کریمی | AwACAgIC...
    """
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    raw = update.message.text.split(" ", 1)
    if len(raw) < 2:
        await update.message.reply_text(
            "فرمت درست:\n"
            "`/addmadahi madahi | مناسبت | عنوان | اسم مداح یا - | audio_file_id`",
            parse_mode="Markdown",
        )
        return

    parts = [p.strip() for p in raw[1].split("|")]
    if len(parts) != 5:
        await update.message.reply_text("❌ باید دقیقاً ۵ بخش با `|` جدا شده بفرستی.")
        return

    content_type, occasion, title, reciter, audio_file_id = parts
    if content_type not in ("madahi", "molodi"):
        await update.message.reply_text("❌ نوع محتوا باید `madahi` یا `molodi` باشه.")
        return

    reciter = None if reciter == "-" else reciter
    item_id = add_madahi(content_type, occasion, title, audio_file_id, reciter=reciter)
    await update.message.reply_text(f"✅ اضافه شد (id={item_id}).")


async def delete_madahi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور ادمین: /delmadahi <id>"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("فرمت درست: `/delmadahi <id>`", parse_mode="Markdown")
        return

    item_id = int(args[0])
    row = get_madahi_by_id(item_id)
    if not row:
        await update.message.reply_text("❌ همچین آیدی‌ای پیدا نشد.")
        return

    delete_madahi(item_id)
    await update.message.reply_text(f"🗑 حذف شد: {row['title']}")


async def madahi_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور ادمین: /madahistats - تعداد فایل‌های ثبت‌شده"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    total = count_madahi()
    madahi_count = count_madahi("madahi")
    molodi_count = count_madahi("molodi")
    await update.message.reply_text(
        f"📊 آمار مداحی/مولودی:\n"
        f"🎙 مداحی: {madahi_count}\n"
        f"🎉 مولودی: {molodi_count}\n"
        f"جمع کل: {total}"
    )
