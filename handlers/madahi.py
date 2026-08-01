# handlers/madahi.py
import logging
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, filters as tg_filters

from config import ADMIN_IDS
from database import (
    add_madahi,
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

# ==========================================
# دسته‌بندی ثابتِ مناسبت‌ها (جدا برای مداحی و مولودی، با عمق دلخواه)
# این ساختار دیگه از دیتابیس خونده نمی‌شه؛ ثابت و از قبل تعریف شده‌ست.
# هر گره (node) یه دیکشنریه با کلید "label" (متن نمایشی) و به‌صورت اختیاری
# "children" (لیستی از زیرگره‌ها). اگه "children" نداشته باشه یا خالی باشه،
# یعنی اون گره خودش یه «مناسبت»ه و با انتخابش مستقیم لیست فایل‌ها نشون داده
# می‌شه. اگه "children" داشته باشه، با انتخابش یه منوی زیرشاخه باز می‌شه؛
# این تو در تو شدن محدودیتی نداره (مثلاً محرم -> دهه اول محرم -> حضرت مسلم).
#
# نکته‌ی مهم برای ادمین: وقتی با /addmadahi یا ویزارد داخل منو مداحی/مولودی
# اضافه می‌کنی، «مناسبت» باید دقیقاً همون "label"ِ برگ (بدون 🏴 یا ❇️) باشه،
# چون همین متن برای پیدا کردن فایل‌ها توی دیتابیس استفاده می‌شه.
# ==========================================

MADAHI_TREE = [
    {"label": "ماه‌ محرم و صفر", "children": [
        {"label": "دهه اول محرم", "children": [
            {"label": "حضرت مسلم"},
{"label": "جناب حر"},
{"label": "حضرت رقیه (سلام الله علیها)"},
{"label": "حضرت عون و عبدالله"},
{"label": "حضرت قاسم"},
{"label": "حضرت علی اصغر (علیه السلام)"},
{"label": "حضرت علی اکبر (علیه السلام)"},
{"label": "حضرت ابالفضل (علیه السلام)"},
]},
{"label": "امام حسین (علیه السلام)"},
{"label": "حضرت زینب (سلام الله علیها)"},
{"label": "اربعین حسینی"},
]},
{"label": "حضرت زهرا (سلام الله علیها)"},
{"label": "امیرالمومنین (علیه السلام)"},
{"label": "مناجات با امام زمان (عجل الله تعالی فرجه الشریف)"},
{"label": "پیامبراکرم (صلی الله علیه و آله) و امام حسن (علیه السلام)"},
{"label": "امام سجاد (علیه السلام)"},
{"label": "امام باقر (علیه السلام)"},
{"label": "امام صادق (علیه السلام)"},
{"label": "امام کاظم (علیه السلام)"},
{"label": "امام رضا (علیه السلام)"},
{"label": "امام جواد (علیه السلام)"},
{"label": "امام هادی (علیه السلام)"},
{"label": "امام حسن عسکری (علیه السلام)"},
]

MOLODI_TREE = [
    {"label": "اعیاد شعبانیه", "children": [
        {"label": "ولادت امام حسین (علیه السلام)"},
{"label": "ولادت امام سجاد (علیه السلام)"},
{"label": "ولادت حضرت ابالفضل (علیه السلام)"},
{"label": "ولادت حضرت علی اکبر (علیه السلام)"},
]},
{"label": "پیامبر اکرم (صل الله علیه و آله و سلم) و امام صادق (علیه السلام)", "children": [
    {"label": "ولادت پیامبر اکرم (صل الله علیه و آله و سلم)"},
    {"label": "ولادت امام صادق (علیه السلام)"},
    {"label": "عید مبعث"},
]},
{"label": "حضرت زهرا (سلام الله علیها)"},
{"label": "امیرالمومنین (علیه السلام)", "children": [
    {"label": "ولادت"},
    {"label": "عید غدیر"},
]},
{"label": "امام حسن (علیه السلام)"},
{"label": "💐امام زمان (عجل الله تعالی فرجه الشریف)", "children": [
    {"label": "ولادت"},
    {"label": "امامت"},
]},
{"label": "امام باقر (علیه السلام)"},
{"label": "امام کاظم (علیه السلام)"},
{"label": "امام رضا (علیه السلام)"},
{"label": "امام جواد (علیه السلام)"},
{"label": "امام هادی (علیه السلام)"},
{"label": "امام حسن عسکری (علیه السلام)"},
]

# نگاشتِ نوع محتوا به درخت و ایموجیِ مخصوص خودش
_CATEGORY_CONFIG = {
    "madahi": {"flag": "🏴", "tree": MADAHI_TREE},
    "molodi": {"flag": "💐", "tree": MOLODI_TREE},
}


def _tree(content_type: str):
    return _CATEGORY_CONFIG.get(content_type, {}).get("tree", [])


def _flag(content_type: str, text: str) -> str:
    emoji = _CATEGORY_CONFIG.get(content_type, {}).get("flag", "")
    return f"{emoji}{text}"


def _resolve_node(content_type: str, path: str):
    """path یه رشته‌ی اندیس‌های جدا شده با "-"ه که از ریشه‌ی درخت شروع می‌شه
    (مثلاً "0-0-3" یعنی: گره ۰ام -> زیرگره ۰ام -> زیرِ زیرگره‌ی ۳ام).
    خروجی: دیکشنریِ همون گره، یا None اگه مسیر نامعتبر بود."""
    if not path:
        return None
    nodes = _tree(content_type)
    node = None
    try:
        for idx_str in path.split("-"):
            idx = int(idx_str)
            if not (0 <= idx < len(nodes)):
                return None
            node = nodes[idx]
            nodes = node.get("children") or []
    except (ValueError, TypeError):
        return None
    return node


def _parent_path(path: str):
    """مسیرِ گره‌ی والد رو برمی‌گردونه؛ اگه گره توی ریشه باشه، None."""
    parts = path.split("-")
    if len(parts) <= 1:
        return None
    return "-".join(parts[:-1])


def _child_button(content_type: str, path_prefix: str, idx: int, node: dict) -> InlineKeyboardButton:
    """یه دکمه برای یه زیرگره می‌سازه. اگه اون زیرگره خودش زیرشاخه داشته باشه
    (یعنی یه دسته‌ست)، callback از نوع "madahi_cat_"ه؛ وگرنه (یعنی خودش یه
    مناسبتِ نهاییه) از نوع "madahi_occ_"ه."""
    full_path = f"{path_prefix}-{idx}" if path_prefix else str(idx)
    if node.get("children"):
        callback = f"madahi_cat_{content_type}_{full_path}"
    else:
        callback = f"madahi_occ_{content_type}_{full_path}"
    return InlineKeyboardButton(_flag(content_type, node["label"]), callback_data=callback)


def _type_keyboard():
    keyboard = [
        [InlineKeyboardButton("(مداحی)", callback_data="madahi_type_madahi")],
        [InlineKeyboardButton("(مولودی)", callback_data="madahi_type_molodi")],
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
    """کاربر بین مداحی/مولودی یکی رو انتخاب کرده (یا از دکمه‌ی «بازگشت» به
    این‌جا برگشته)؛ حالا لیست دسته‌های اصلیِ ثابت رو نشون بده"""
    query = update.callback_query
    await query.answer()

    content_type = query.data.split("_")[-1]  # madahi_type_madahi -> madahi
    context.user_data["madahi_type"] = content_type
    await show_category_menu(update, context, content_type)


async def show_category_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, content_type: str):
    """نمایش لیست ثابتِ دسته‌های ریشه (مخصوص هر نوع محتوا: مداحی یا مولودی)"""
    keyboard = [[_child_button(content_type, "", idx, node)] for idx, node in enumerate(_tree(content_type))]
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


def _list_keyboard(content_type: str, path: str, rows, page: int, is_admin: bool = False, back_callback: str = None):
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
        nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"madahi_page_{content_type}_{path}_{page - 1}"))
    if start + PAGE_SIZE < len(rows):
        nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"madahi_page_{content_type}_{path}_{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    if is_admin:
        keyboard.append([InlineKeyboardButton("➕ افزودن مداحی به این مناسبت", callback_data=f"madahi_addstart_{content_type}_{path}")])

    keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=back_callback or f"madahi_type_{content_type}")])
    return InlineKeyboardMarkup(keyboard)


async def madahi_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاربر یه دسته (در هر عمقی از درخت) رو انتخاب کرده که خودش زیرشاخه
    داره؛ منوی زیرشاخه‌هاش رو نشون بده."""
    query = update.callback_query
    await query.answer()

    # callback_data: madahi_cat_{content_type}_{path}
    _, _, content_type, path = query.data.split("_")
    node = _resolve_node(content_type, path)
    if node is None or not node.get("children"):
        await query.answer("⚠️ این دسته پیدا نشد.", show_alert=True)
        await show_category_menu(update, context, content_type)
        return

    parent = _parent_path(path)
    back_callback = f"madahi_cat_{content_type}_{parent}" if parent else f"madahi_type_{content_type}"

    keyboard = [[_child_button(content_type, path, idx, child)] for idx, child in enumerate(node["children"])]
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=back_callback)])
    text = f"{TYPE_LABELS.get(content_type, '')}\n📌 {_flag(content_type, node['label'])}\n\nزیرمجموعه مورد نظرت رو انتخاب کن:"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def madahi_occasion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاربر یه مناسبتِ نهایی (برگِ درخت، در هر عمقی) رو انتخاب کرده؛ لیست
    فایل‌های همون مناسبت رو نشون بده"""
    query = update.callback_query
    await query.answer()

    # callback_data: madahi_occ_{content_type}_{path}   (path مثلاً "0-0-3")
    _, _, content_type, path = query.data.split("_")
    node = _resolve_node(content_type, path)
    if node is None:
        await query.answer("⚠️ این مناسبت پیدا نشد.", show_alert=True)
        await show_category_menu(update, context, content_type)
        return

    parent = _parent_path(path)
    back_callback = f"madahi_cat_{content_type}_{parent}" if parent else f"madahi_type_{content_type}"
    await _show_occasion_list(update, context, content_type, node["label"], path=path, page=0, back_callback=back_callback)


async def madahi_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # callback_data: madahi_page_{content_type}_{path}_{page}
    _, _, content_type, path, page_str = query.data.split("_")
    node = _resolve_node(content_type, path)
    if node is None:
        await query.answer("⚠️ این مناسبت پیدا نشد.", show_alert=True)
        await show_category_menu(update, context, content_type)
        return

    parent = _parent_path(path)
    back_callback = f"madahi_cat_{content_type}_{parent}" if parent else f"madahi_type_{content_type}"
    await _show_occasion_list(update, context, content_type, node["label"], path=path, page=int(page_str), back_callback=back_callback)


async def _show_occasion_list(update: Update, context: ContextTypes.DEFAULT_TYPE, content_type: str,
                               occasion: str, path: str, page: int, back_callback: str = None):
    rows = get_madahi_by_occasion(content_type, occasion)
    query = update.callback_query
    is_admin = update.effective_user.id in ADMIN_IDS

    if not rows:
        text = f"{TYPE_LABELS.get(content_type, '')}\n📌 {_flag(content_type, occasion)}\n\nهنوز چیزی برای این مناسبت اضافه نشده."
        keyboard = []
        if is_admin:
            keyboard.append([InlineKeyboardButton("➕ افزودن مداحی به این مناسبت", callback_data=f"madahi_addstart_{content_type}_{path}")])
        keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=back_callback or f"madahi_type_{content_type}")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text = f"{TYPE_LABELS.get(content_type, '')}\n📌 {_flag(content_type, occasion)}\n\n{len(rows)} مورد پیدا شد:"
    await query.edit_message_text(
        text,
        reply_markup=_list_keyboard(content_type, path, rows, page, is_admin=is_admin, back_callback=back_callback),
    )


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

    # callback_data: madahi_addstart_{content_type}_{path}
    _, _, content_type, path = query.data.split("_")
    node = _resolve_node(content_type, path)
    if node is None:
        await query.answer("⚠️ این مناسبت پیدا نشد.", show_alert=True)
        await show_category_menu(update, context, content_type)
        return
    occasion = node["label"]

    await query.answer()
    _PENDING_MADAHI_ADD[user_id] = {
        "chat_id": update.effective_chat.id,
        "content_type": content_type,
        "occasion": occasion,
        "index_str": path,
        "step": "title",
        "updated_at": time.time(),
    }
    await query.edit_message_text(
        f"➕ *افزودن مداحی جدید*\n"
        f"{TYPE_LABELS.get(content_type, '')} | 📌 {_flag(content_type, occasion)}\n\n"
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
        f"✅ اضافه شد (id={item_id})\n🎙 {title}\n📌 مناسبت: {_flag(content_type, occasion)}\n\n"
        "می‌خوای همین‌جا یکی دیگه هم برای همین مناسبت اضافه کنی؟",
        reply_markup=keyboard,
    )
