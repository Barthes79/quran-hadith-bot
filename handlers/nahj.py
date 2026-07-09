import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import (
    get_nahj_item, get_nahj_numbers, add_nahj_item, update_nahj_tafsir,
    add_favorite,
)
from config import ADMIN_IDS

# شماره‌گذاری متعارف بر اساس نسخه‌ی صبحی صالح (رایج‌ترین نسخه‌ی چاپی نهج‌البلاغه)
NAHJ_TOTALS = {
    "khutbah": 241,
    "letter": 79,
    "hekmat": 480,
}

NAHJ_MENU_LABELS = {
    "khutbah": "📜 خطبه‌ها",
    "letter": "✉️ نامه‌ها",
    "hekmat": "💎 حکمت‌ها",
}

NAHJ_ITEM_LABELS = {
    "khutbah": "خطبه",
    "letter": "نامه",
    "hekmat": "حکمت",
}

PAGE_SIZE = 30
PER_ROW = 5


def _category_ok(category: str) -> bool:
    return category in NAHJ_TOTALS


async def show_nahj_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    buttons = [
        [InlineKeyboardButton(NAHJ_MENU_LABELS["khutbah"], callback_data="nahjcat_khutbah")],
        [InlineKeyboardButton(NAHJ_MENU_LABELS["letter"], callback_data="nahjcat_letter")],
        [InlineKeyboardButton(NAHJ_MENU_LABELS["hekmat"], callback_data="nahjcat_hekmat")],
        [InlineKeyboardButton("⬅️ منوی اصلی", callback_data="menu_back")],
    ]
    text = "🕌 نهج‌البلاغه\n\nیک بخش را انتخاب کنید:"
    markup = InlineKeyboardMarkup(buttons)
    if query:
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


async def nahj_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.replace("nahjcat_", "")
    await show_nahj_number_list(update, context, category, page=0)


async def show_nahj_number_list(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str, page: int = 0):
    query = update.callback_query
    if not _category_ok(category):
        if query:
            await query.answer("بخش نامعتبر است.", show_alert=True)
        return

    total = NAHJ_TOTALS[category]
    existing = set(get_nahj_numbers(category))

    start = page * PAGE_SIZE + 1
    end = min(start + PAGE_SIZE - 1, total)

    buttons = []
    row = []
    for n in range(start, end + 1):
        label = str(n) if n in existing else f"·{n}·"
        row.append(InlineKeyboardButton(label, callback_data=f"nahjitem_{category}_{n}"))
        if len(row) == PER_ROW:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"nahjpage_{category}_{page-1}"))
    if end < total:
        nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"nahjpage_{category}_{page+1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="nahjmenu")])

    item_label = NAHJ_ITEM_LABELS[category]
    text = (
        f"{NAHJ_MENU_LABELS[category]} — شماره‌ی {item_label} مورد نظر را انتخاب کنید:\n\n"
        f"({len(existing)} از {total} مورد تاکنون ثبت شده — شماره‌های داخل نقطه هنوز ثبت نشده‌اند)"
    )
    markup = InlineKeyboardMarkup(buttons)

    if query:
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


async def nahj_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, category, page = query.data.split("_")
    await show_nahj_number_list(update, context, category, page=int(page))


async def nahj_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_nahj_menu(update, context)


def _nahj_page_of(category: str, number: int) -> int:
    return (number - 1) // PAGE_SIZE


# حداکثر طول هر بخش از متن (کاراکتر) — تلگرام بیشتر از ۴۰۹۶ کاراکتر را در یک پیام قبول نمی‌کند
TEXT_CHUNK_SIZE = 500


def _split_text(full_text: str, chunk_size: int = TEXT_CHUNK_SIZE):
    """متن طولانی را به چند بخش با مرز پاراگراف/خط تقسیم می‌کند."""
    if len(full_text) <= chunk_size:
        return [full_text]

    paragraphs = full_text.split("\n")
    chunks = []
    current = ""

    def flush():
        nonlocal current
        if current:
            chunks.append(current.strip("\n"))
            current = ""

    for para in paragraphs:
        candidate = (current + "\n" + para) if current else para
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        # این پاراگراف به‌تنهایی یا در ادامه‌ی بخش فعلی جا نمی‌شود
        flush()
        if len(para) <= chunk_size:
            current = para
        else:
            # پاراگراف خیلی طولانی است؛ بر اساس کلمه تقسیم می‌شود
            words = para.split(" ")
            piece = ""
            for word in words:
                cand = (piece + " " + word) if piece else word
                if len(cand) <= chunk_size:
                    piece = cand
                else:
                    if piece:
                        chunks.append(piece)
                    piece = word
            if piece:
                current = piece

    flush()
    return chunks or [full_text]


def build_nahj_pages(category: str, number: int, row):
    """متن مورد نظر را به هدر + لیستی از بخش‌های متنی تقسیم می‌کند."""
    item_label = NAHJ_ITEM_LABELS[category]
    title = f" — {row['title']}" if row["title"] else ""
    header = f"{NAHJ_MENU_LABELS[category]} — {item_label} {number}{title}\n\n"

    body_parts = [row["arabic_text"], f"🔹 ترجمه:\n{row['translation_text']}"]
    if row["tafsir_text"]:
        body_parts.append(f"📝 شرح:\n{row['tafsir_text']}")
    full_body = "\n\n".join(body_parts)

    chunks = _split_text(full_body)
    return header, chunks


def format_nahj_item(category: str, number: int, row):
    """نسخه‌ی کامل و یک‌تکه‌ی متن (برای استفاده‌های دیگر مثل ارسال فایل و ...)."""
    header, chunks = build_nahj_pages(category, number, row)
    return header + "\n\n".join(chunks)


def nahj_item_keyboard(category: str, number: int, page: int = 0, total_pages: int = 1):
    total = NAHJ_TOTALS[category]
    buttons = []

    # دکمه‌های ادامه/قسمت قبل برای متن‌های طولانی
    if total_pages > 1:
        text_nav_row = []
        if page > 0:
            text_nav_row.append(InlineKeyboardButton("◀️ قسمت قبل", callback_data=f"nahjtxt_{category}_{number}_{page-1}"))
        if page < total_pages - 1:
            text_nav_row.append(InlineKeyboardButton("ادامه ▶️", callback_data=f"nahjtxt_{category}_{number}_{page+1}"))
        if text_nav_row:
            buttons.append(text_nav_row)

    nav_row = []
    if number > 1:
        nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"nahjitem_{category}_{number-1}"))
    if number < total:
        nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"nahjitem_{category}_{number+1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("⭐ افزودن به علاقه‌مندی‌ها", callback_data=f"favnahj_{category}_{number}")])
    buttons.append([
        InlineKeyboardButton("🔢 لیست شماره‌ها", callback_data=f"nahjpage_{category}_{_nahj_page_of(category, number)}"),
        InlineKeyboardButton("⬅️ بخش‌ها", callback_data="nahjmenu"),
    ])
    return InlineKeyboardMarkup(buttons)


async def show_nahj_item(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str, number: int, page: int = 0):
    query = update.callback_query
    if not _category_ok(category) or number < 1 or number > NAHJ_TOTALS[category]:
        if query:
            await query.answer("مورد نامعتبر است.", show_alert=True)
        return

    row = get_nahj_item(category, number)
    item_label = NAHJ_ITEM_LABELS[category]

    if not row:
        text = (
            f"{NAHJ_MENU_LABELS[category]} — {item_label} {number}\n\n"
            "😕 متن این مورد هنوز در ربات ثبت نشده است."
        )
        markup = nahj_item_keyboard(category, number)
    else:
        header, chunks = build_nahj_pages(category, number, row)
        total_pages = len(chunks)
        page = max(0, min(page, total_pages - 1))

        text = header
        if total_pages > 1:
            text += f"(قسمت {page + 1} از {total_pages})\n\n"
        text += chunks[page]

        markup = nahj_item_keyboard(category, number, page=page, total_pages=total_pages)

    if query:
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


async def nahj_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, category, number = query.data.split("_")
    await show_nahj_item(update, context, category, int(number))


async def nahj_text_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, category, number, page = query.data.split("_")
    await show_nahj_item(update, context, category, int(number), page=int(page))


async def fav_nahj_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, category, number = query.data.split("_")
    row = get_nahj_item(category, int(number))
    if not row:
        await query.answer("این مورد هنوز ثبت نشده و قابل ذخیره نیست.", show_alert=True)
        return
    add_favorite(query.from_user.id, "nahj", f"{category}:{number}")
    await query.answer("به علاقه‌مندی‌ها اضافه شد ⭐")


# ---------------- دستور ادمین برای افزودن/ویرایش یک مورد نهج‌البلاغه ----------------
# فرمت پیام بعد از دستور /addnahj باید به این شکل باشد:
# دسته: خطبه یا نامه یا حکمت
# شماره: ...
# عنوان: ... (اختیاری)
# عربی: ...
# ترجمه: ...
# شرح: ... (اختیاری)

CATEGORY_FA_TO_KEY = {
    "خطبه": "khutbah",
    "نامه": "letter",
    "حکمت": "hekmat",
}


async def add_nahj_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه‌ی این دستور را ندارید.")
        return

    full_text = update.message.text.split(" ", 1)
    if len(full_text) < 2:
        await update.message.reply_text(
            "فرمت صحیح استفاده:\n\n"
            "/addnahj\n"
            "دسته: خطبه یا نامه یا حکمت\n"
            "شماره: ...\n"
            "عنوان: ... (اختیاری)\n"
            "عربی: ...\n"
            "ترجمه: ...\n"
            "شرح: ... (اختیاری)"
        )
        return

    body = full_text[1]
    field_labels = ["دسته", "شماره", "عنوان", "عربی", "ترجمه", "شرح"]
    pattern = r"(?=(?:" + "|".join(field_labels) + r")\s*:)"
    chunks = re.split(pattern, body.strip())

    fields = {}
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        key, value = chunk.split(":", 1)
        key = key.strip()
        if key in field_labels:
            fields[key] = value.strip()

    category_fa = fields.get("دسته", "").strip()
    category = CATEGORY_FA_TO_KEY.get(category_fa)
    number_raw = fields.get("شماره", "")
    title = fields.get("عنوان") or None
    arabic = fields.get("عربی", "")
    translation = fields.get("ترجمه", "")
    tafsir = fields.get("شرح") or None

    if not category:
        await update.message.reply_text("فیلد «دسته» باید یکی از این مقادیر باشد: خطبه، نامه، حکمت")
        return

    try:
        number = int(number_raw)
    except ValueError:
        await update.message.reply_text("فیلد «شماره» باید یک عدد باشد.")
        return

    if number < 1 or number > NAHJ_TOTALS[category]:
        await update.message.reply_text(
            f"شماره باید بین 1 تا {NAHJ_TOTALS[category]} باشد (برای {category_fa})."
        )
        return

    if not arabic or not translation:
        await update.message.reply_text("حداقل فیلدهای «عربی» و «ترجمه» الزامی هستند.")
        return

    add_nahj_item(category, number, arabic, translation, title=title, tafsir_text=tafsir)
    await update.message.reply_text(f"✅ {category_fa} شماره {number} با موفقیت ثبت/به‌روزرسانی شد.")
