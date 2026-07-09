import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import (
    get_mafatih_by_category, get_mafatih_by_id, add_mafatih_item,
    add_favorite,
)
from config import ADMIN_IDS
from text_utils import normalize_input_text

MAFATIH_MENU_LABELS = {
    "daily": "🌅 ادعیه روزانه",
    "ziyarat": "🕋 زیارت‌نامه‌ها",
    "weekly": "📅 اعمال ایام هفته",
    "monthly": "🌙 اعمال ماه‌های قمری",
    "munajat": "🤲 مناجات‌ها",
    "special": "🕌 نمازها و اعمال خاص",
}

CATEGORY_FA_TO_KEY = {
    "روزانه": "daily",
    "زیارت": "ziyarat",
    "هفتگی": "weekly",
    "ماهانه": "monthly",
    "مناجات": "munajat",
    "خاص": "special",
}


async def show_mafatih_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    buttons = [[InlineKeyboardButton(label, callback_data=f"mafcat_{key}")]
               for key, label in MAFATIH_MENU_LABELS.items()]
    buttons.append([InlineKeyboardButton("⬅️ منوی اصلی", callback_data="menu_back")])
    text = "📗 مفاتیح‌الجنان\n\nیک بخش را انتخاب کنید:"
    markup = InlineKeyboardMarkup(buttons)
    if query:
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


async def mafatih_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_mafatih_menu(update, context)


async def show_mafatih_list(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    query = update.callback_query
    if category not in MAFATIH_MENU_LABELS:
        if query:
            await query.answer("بخش نامعتبر است.", show_alert=True)
        return

    rows = get_mafatih_by_category(category)
    buttons = []
    for i, r in enumerate(rows):
        buttons.append([InlineKeyboardButton(r["title"], callback_data=f"mafitem_{category}_{i}")])
    buttons.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="mafmenu")])

    label = MAFATIH_MENU_LABELS[category]
    text = f"{label}\n\nیک مورد را انتخاب کنید:" if rows else (
        f"{label}\n\nهنوز موردی در این بخش ثبت نشده است.\n"
        "ادمین می‌تواند با دستور /addmafatih آن را اضافه کند."
    )
    markup = InlineKeyboardMarkup(buttons)

    if query:
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


async def mafatih_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.replace("mafcat_", "")
    await show_mafatih_list(update, context, category)


def format_mafatih_item(row):
    text = f"📗 {row['title']}\n\n"
    text += f"{row['arabic_text']}\n\n"
    if row["translation_text"]:
        text += f"🔹 ترجمه:\n{row['translation_text']}\n"
    if row["tafsir_text"]:
        text += f"\n📝 توضیح:\n{row['tafsir_text']}\n"
    return text


def mafatih_item_keyboard(category: str, index: int, total: int, item_id: int):
    buttons = []
    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"mafitem_{category}_{index-1}"))
    nav_row.append(InlineKeyboardButton(f"{index+1}/{total}", callback_data="noop"))
    if index < total - 1:
        nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"mafitem_{category}_{index+1}"))
    buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("⭐ افزودن به علاقه‌مندی‌ها", callback_data=f"favmaf_{item_id}")])
    buttons.append([
        InlineKeyboardButton("🔢 لیست موارد", callback_data=f"mafcat_{category}"),
        InlineKeyboardButton("⬅️ بخش‌ها", callback_data="mafmenu"),
    ])
    return InlineKeyboardMarkup(buttons)


async def mafatih_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, category, index = query.data.split("_")
    index = int(index)

    rows = get_mafatih_by_category(category)
    if not rows or index < 0 or index >= len(rows):
        await query.answer("موردی یافت نشد.", show_alert=True)
        return

    row = rows[index]
    await query.edit_message_text(
        format_mafatih_item(row),
        reply_markup=mafatih_item_keyboard(category, index, len(rows), row["id"]),
    )


async def fav_mafatih_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    item_id = query.data.replace("favmaf_", "")
    add_favorite(query.from_user.id, "mafatih", item_id)
    await query.answer("به علاقه‌مندی‌ها اضافه شد ⭐")


# ---------------- دستور ادمین برای افزودن مورد جدید به مفاتیح‌الجنان ----------------
# فرمت پیام بعد از دستور /addmafatih:
# دسته: روزانه یا زیارت یا هفتگی یا ماهانه یا مناجات یا خاص
# عنوان: ... (مثلاً «دعای کمیل» یا «زیارت عاشورا»)
# عربی: ...
# ترجمه: ... (اختیاری)
# توضیح: ... (اختیاری)

async def add_mafatih_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه‌ی این دستور را ندارید.")
        return

    full_text = update.message.text.split(" ", 1)
    if len(full_text) < 2:
        await update.message.reply_text(
            "فرمت صحیح استفاده:\n\n"
            "/addmafatih\n"
            "دسته: روزانه یا زیارت یا هفتگی یا ماهانه یا مناجات یا خاص\n"
            "عنوان: ...\n"
            "عربی: ...\n"
            "ترجمه: ... (اختیاری)\n"
            "توضیح: ... (اختیاری)"
        )
        return

    body = normalize_input_text(full_text[1])
    field_labels = ["دسته", "عنوان", "عربی", "ترجمه", "توضیح"]
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
    title = fields.get("عنوان", "").strip()
    arabic = fields.get("عربی", "").strip()
    translation = fields.get("ترجمه", "").strip() or None
    tafsir = fields.get("توضیح", "").strip() or None

    if not category:
        await update.message.reply_text(
            "فیلد «دسته» باید یکی از این مقادیر باشد: روزانه، زیارت، هفتگی، ماهانه، مناجات، خاص"
        )
        return

    if not title or not arabic:
        await update.message.reply_text("حداقل فیلدهای «عنوان» و «عربی» الزامی هستند.")
        return

    item_id = add_mafatih_item(category, title, arabic, translation_text=translation, tafsir_text=tafsir)
    await update.message.reply_text(f"✅ «{title}» با شناسه {item_id} در بخش «{category_fa}» ثبت شد.")
