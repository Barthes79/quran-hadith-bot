# handlers/madahi.py
import logging
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, filters as tg_filters

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
    "madahi": "مداحی",
    "molodi": "مولودی",
}


def _type_keyboard():
    keyboard = [
        [InlineKeyboardButton("مداحی)"), callback_data="madahi_type_madahi")],
        [InlineKeyboardButton("مولودی‌)"), callback_data="madahi_type_molodi")],
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


def _list_keyboard(content_type: str, index_str: str, rows, page: int, is_admin: bool = False):
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

    if is_admin:
        keyboard.append([InlineKeyboardButton("➕ افزودن مداحی به این مناسبت", callback_data=f"madahi_addstart_{content_type}_{index_str}")])

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
    is_admin = update.effective_user.id in ADMIN_IDS

    if not rows:
        text = f"{TYPE_LABELS.get(content_type, '')}\n📌 {occasion}\n\nهنوز چیزی برای این مناسبت اضافه نشده."
        keyboard = []
        if is_admin:
            keyboard.append([InlineKeyboardButton("➕ افزودن مداحی به این مناسبت", callback_data=f"madahi_addstart_{content_type}_{index_str}")])
        keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"madahi_type_{content_type}")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text = f"{TYPE_LABELS.get(content_type, '')}\n📌 {occasion}\n\n{len(rows)} مورد پیدا شد:"
    await query.edit_message_text(text, reply_markup=_list_keyboard(content_type, index_str, rows, page, is_admin=is_admin))


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


# ==========================================
# ویزارد افزودن سریع مداحی از توی خودِ منو
# (ادمین توی «مداحی و مولودی» تا مناسبت مورد نظر جلو می‌ره، دکمه‌ی
# «➕ افزودن مداحی به این مناسبت» رو می‌زنه، عنوان و اسم مداح رو می‌فرسته و
# در آخر فایل صوتی/ویس رو می‌فرسته؛ همون‌جا و بدون نوشتن دستور دستی ثبت می‌شه)
# ==========================================

# user_id ادمین -> وضعیت ویزارد جاری‌اش
# {"chat_id", "content_type", "occasion", "index_str", "step": "title"|"reciter"|"audio",
#  "title", "reciter", "updated_at"}
_PENDING_MADAHI_ADD: dict[int, dict] = {}

# اگه بیش از این مدت از آخرین قدمِ ویزارد بگذره، خودش خودکار لغو می‌شه؛ این
# جلوی این حالت رو می‌گیره که یه ویزاردِ نیمه‌کاره و فراموش‌شده برای همیشه
# فعال بمونه و بعداً پیام‌های عادیِ ادمین رو (حتی توی یه گروه بی‌ربط) قاپ بزنه.
_ADD_WIZARD_TIMEOUT_SECONDS = 10 * 60


def _get_active_state(user_id: int, chat_id: int = None):
    """وضعیت جاریِ ویزارد رو برمی‌گردونه، فقط اگه هنوز منقضی نشده باشه و
    (در صورت دادنِ chat_id) توی همون چتی باشه که ویزارد توش شروع شده. در غیر
    این صورت (منقضی شده یا چت فرق داره)، وضعیت رو پاک می‌کنه و None برمی‌گردونه."""
    state = _PENDING_MADAHI_ADD.get(user_id)
    if not state:
        return None

    if time.time() - state.get("updated_at", 0) > _ADD_WIZARD_TIMEOUT_SECONDS:
        _PENDING_MADAHI_ADD.pop(user_id, None)
        return None

    if chat_id is not None and state.get("chat_id") != chat_id:
        return None

    return state


def has_pending_madahi_add(user_id: int, chat_id: int) -> bool:
    """آیا این ادمین، توی همین چت، وسط ویزارد افزودن مداحیه (هر مرحله‌ای).
    برای فیلتر هندلر متنی توی main.py استفاده می‌شه، تا فقط وقتی این True
    باشه پیام متنی رو بگیریم، وگرنه general_text_handler عادی کار خودشو بکنه."""
    return _get_active_state(user_id, chat_id) is not None


def is_awaiting_madahi_audio(user_id: int, chat_id: int) -> bool:
    """آیا این ادمین، توی همین چت، دقیقاً منتظر فرستادن فایل صوتیه (مرحله‌ی
    آخر ویزارد). برای فیلتر هندلر صوتی توی main.py استفاده می‌شه."""
    state = _get_active_state(user_id, chat_id)
    return bool(state and state.get("step") == "audio")


class _MadahiPendingTextFilter(tg_filters.MessageFilter):
    """True فقط وقتی فرستنده‌ی پیام، توی همین چت، وسط ویزارد افزودن مداحیه."""

    def filter(self, message):
        user = message.from_user
        chat = message.chat
        if not user or not chat:
            return False
        return has_pending_madahi_add(user.id, chat.id)


class _MadahiPendingAudioFilter(tg_filters.MessageFilter):
    """True فقط وقتی فرستنده‌ی پیام، توی همین چت، دقیقاً منتظر فایل صوتیِ ویزارده."""

    def filter(self, message):
        user = message.from_user
        chat = message.chat
        if not user or not chat:
            return False
        return is_awaiting_madahi_audio(user.id, chat.id)


# این دوتا رو مستقیماً توی main.py ایمپورت و به‌عنوان فیلترِ MessageHandler
# استفاده کن (پایین‌تر توضیح داده شده).
madahi_pending_text_filter = _MadahiPendingTextFilter()
madahi_pending_audio_filter = _MadahiPendingAudioFilter()


async def madahi_add_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاربر دکمه‌ی «➕ افزودن مداحی به این مناسبت» رو زده."""
    query = update.callback_query
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.answer("فقط ادمین‌ها می‌تونن مداحی اضافه کنن.", show_alert=True)
        return

    # callback_data: madahi_addstart_{content_type}_{index_str}
    _, _, content_type, index_str = query.data.split("_")
    occasion = _resolve_occasion(content_type, int(index_str))
    if occasion is None:
        await query.answer("⚠️ لیست به‌روزرسانی شد، دوباره امتحان کن.", show_alert=True)
        await show_occasion_menu(update, context, content_type)
        return

    await query.answer()
    _PENDING_MADAHI_ADD[user_id] = {
        "chat_id": update.effective_chat.id,
        "content_type": content_type,
        "occasion": occasion,
        "index_str": index_str,
        "step": "title",
        "updated_at": time.time(),
    }
    await query.edit_message_text(
        f"➕ *افزودن مداحی جدید*\n"
        f"{TYPE_LABELS.get(content_type, '')} | 📌 {occasion}\n\n"
        "عنوان مداحی رو بفرست (مثلاً «السلام علیک یا اباعبدالله»).\n"
        "برای لغو، در هر مرحله بنویس «لغو».",
        parse_mode="Markdown",
    )


async def madahi_add_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پیام‌های متنیِ ادمین رو وقتی وسط ویزارد افزودن مداحیه (مرحله‌ی عنوان
    یا اسم مداح) می‌گیره. اگه این ادمین وسط ویزارد نباشه، کاری نمی‌کنه تا
    هندلرهای دیگه‌ی پیام متنی (مثل جستجوی حدیث/آیه) خودشون پیام رو بگیرن."""
    user_id = update.effective_user.id
    state = _get_active_state(user_id, update.effective_chat.id)
    if not state:
        return

    message = update.message
    text = (message.text or "").strip()

    if text in ("لغو", "/cancel", "cancel"):
        _PENDING_MADAHI_ADD.pop(user_id, None)
        await message.reply_text("❌ عملیات افزودن مداحی لغو شد.")
        return

    state["updated_at"] = time.time()

    if state["step"] == "title":
        if not text:
            await message.reply_text("عنوان نمی‌تونه خالی باشه. دوباره بفرست:")
            return
        state["title"] = text
        state["step"] = "reciter"
        await message.reply_text("اسم مداح رو بفرست (اگه نداری بنویس «-»):")
        return

    if state["step"] == "reciter":
        state["reciter"] = None if text == "-" else text
        state["step"] = "audio"
        await message.reply_text("🎧 حالا فایل صوتی (audio) یا ویس همین مداحی رو بفرست.")
        return

    if state["step"] == "audio":
        await message.reply_text("این مرحله باید یه فایل صوتی یا ویس بفرستی، نه متن. (یا بنویس «لغو»)")


async def madahi_add_audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی ادمینی که وسط ویزارد افزودن مداحیه و منتظر فایل صوتیه، audio یا
    voice بفرسته، همینجا در دیتابیس ثبتش می‌کنه."""
    user_id = update.effective_user.id
    state = _get_active_state(user_id, update.effective_chat.id)
    if not state or state.get("step") != "audio":
        return

    message = update.message
    file_id = None
    if message.audio:
        file_id = message.audio.file_id
    elif message.voice:
        file_id = message.voice.file_id

    if not file_id:
        return

    item_id = add_madahi(
        state["content_type"], state["occasion"], state["title"],
        file_id, reciter=state.get("reciter"),
    )

    content_type = state["content_type"]
    occasion = state["occasion"]
    index_str = state["index_str"]
    title = state["title"]

    # بعد از ثبت، ویزارد رو کامل می‌بندیم؛ دکمه‌ی زیر دوباره یه ویزارد تازه
    # برای همین مناسبت شروع می‌کنه تا اضافه کردن پشت‌سرهم راحت باشه.
    _PENDING_MADAHI_ADD.pop(user_id, None)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن مداحی بعدی به همین مناسبت", callback_data=f"madahi_addstart_{content_type}_{index_str}")],
        [InlineKeyboardButton("🏁 پایان و بازگشت به لیست", callback_data=f"madahi_occ_{content_type}_{index_str}")],
    ])
    await message.reply_text(
        f"✅ اضافه شد (id={item_id})\n🎙 {title}\n📌 مناسبت: {occasion}\n\n"
        "می‌خوای همین‌جا یکی دیگه هم برای همین مناسبت اضافه کنی؟",
        reply_markup=keyboard,
    )
