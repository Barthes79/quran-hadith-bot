import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import (
    get_all_topics, get_hadiths_by_topic, get_random_hadith,
    search_hadiths, add_favorite, get_favorites, add_hadith,
    get_hadith_by_id, update_hadith_tafsir,
)
from config import ADMIN_IDS
from text_utils import normalize_input_text


async def show_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    topics = get_all_topics()

    buttons = []
    row = []
    for t in topics:
        row.append(InlineKeyboardButton(t, callback_data=f"topic_{t}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("🎲 حدیث تصادفی", callback_data="hadith_random")])
    buttons.append([InlineKeyboardButton("⬅️ منوی اصلی", callback_data="menu_back")])

    text = "📿 یک موضوع را انتخاب کنید:" if topics else (
        "📿 هنوز موضوعی ثبت نشده است.\n"
        "می‌توانید با دستور /addhadith (فقط ادمین) حدیث جدید اضافه کنید."
    )

    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


def format_hadith(row):
    text = f"📿 {row['narrator'] or ''}\n\n"
    text += f"{row['arabic_text']}\n\n"
    text += f"🔹 ترجمه:\n{row['translation_text']}\n"
    if row["tafsir_text"]:
        text += f"\n📝 تفسیر/توضیح:\n{row['tafsir_text']}\n"
    source = row["source_book"] or ""
    chapter = row["chapter"] or ""
    number = row["hadith_number"] or ""
    if source:
        text += f"\n📚 منبع: {source}"
        if chapter:
            text += f" - {chapter}"
        if number:
            text += f" (حدیث {number})"
    text += f"\n\n🆔 شناسه: {row['id']}"
    return text


def hadith_keyboard(hadith_id, topic_name=None, index=None, total=None):
    buttons = []
    if topic_name is not None and total and total > 1:
        nav_row = []
        if index > 0:
            nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"topicnav_{index-1}_{topic_name}"))
        nav_row.append(InlineKeyboardButton(f"{index+1}/{total}", callback_data="noop"))
        if index < total - 1:
            nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"topicnav_{index+1}_{topic_name}"))
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("⭐ افزودن به علاقه‌مندی‌ها", callback_data=f"fav_hadith_{hadith_id}")])
    buttons.append([InlineKeyboardButton("⬅️ موضوعات", callback_data="menu_hadith")])
    return InlineKeyboardMarkup(buttons)


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


async def topic_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    topic_name = query.data.replace("topic_", "")
    rows = get_hadiths_by_topic(topic_name)

    if not rows:
        await query.edit_message_text("حدیثی برای این موضوع یافت نشد.")
        return

    row = rows[0]
    await query.edit_message_text(
        format_hadith(row),
        reply_markup=hadith_keyboard(row["id"], topic_name=topic_name, index=0, total=len(rows)),
    )


async def topic_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, index, topic_name = query.data.split("_", 2)
    index = int(index)

    rows = get_hadiths_by_topic(topic_name)
    if not rows or index < 0 or index >= len(rows):
        await query.answer("موردی یافت نشد.", show_alert=True)
        return

    row = rows[index]
    await query.edit_message_text(
        format_hadith(row),
        reply_markup=hadith_keyboard(row["id"], topic_name=topic_name, index=index, total=len(rows)),
    )


async def random_hadith_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    row = get_random_hadith()
    if not row:
        await query.edit_message_text("هنوز حدیثی در دیتابیس ثبت نشده است.")
        return
    await query.edit_message_text(format_hadith(row), reply_markup=hadith_keyboard(row["id"]))


async def fav_hadith_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    hadith_id = query.data.replace("fav_hadith_", "")
    add_favorite(query.from_user.id, "hadith", hadith_id)
    await query.answer("به علاقه‌مندی‌ها اضافه شد ⭐")


async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    favs = get_favorites(query.from_user.id)
    if not favs:
        await query.edit_message_text(
            "شما هنوز موردی به علاقه‌مندی‌ها اضافه نکرده‌اید.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ منوی اصلی", callback_data="menu_back")]]
            ),
        )
        return

    lines = ["⭐ علاقه‌مندی‌های شما:\n"]
    for f in favs:
        if f["item_type"] == "hadith":
            hadith = get_hadith_by_id(int(f["item_ref"]))
            if hadith:
                lines.append(
                    f"📿 {hadith['arabic_text']}\n\n"
                    f"📖 ترجمه:\n{hadith['translation_text']}\n"
                )
                if hadith["tafsir_text"]:
                    lines.append(f"\n📝 شرح:\n{hadith['tafsir_text']}")
                lines.append("\n────────────\n")
        else:
            lines.append(f"📖 آیه {f['item_ref']}\n────────────\n")

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ منوی اصلی", callback_data="menu_back")]]
        ),
    )


async def text_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    rows = search_hadiths(text)
    if not rows:
        await update.message.reply_text("حدیثی با این عبارت یافت نشد.")
        return
    row = rows[0]
    await update.message.reply_text(format_hadith(row), reply_markup=hadith_keyboard(row["id"]))


# ---------------- دستور ادمین برای افزودن حدیث ----------------
# فرمت پیام بعد از دستور /addhadith باید به این شکل باشد (هر خط جدا):
# عربی: ...
# ترجمه: ...
# راوی: ...
# منبع: ...
# باب: ...
# شماره: ...
# موضوعات: صبر، تقوا، اخلاق

async def add_hadith_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه‌ی این دستور را ندارید.")
        return

    full_text = update.message.text.split(" ", 1)
    if len(full_text) < 2:
        await update.message.reply_text(
            "فرمت صحیح استفاده:\n\n"
            "/addhadith\n"
            "عربی: ...\n"
            "ترجمه: ...\n"
            "شرح: ... (اختیاری)\n"
            "راوی: ...\n"
            "منبع: ...\n"
            "باب: ...\n"
            "شماره: ...\n"
            "موضوعات: صبر، تقوا"
        )
        return

    body = normalize_input_text(full_text[1])

    # پارسینگ مقاوم: چون تلگرام گاهی خط‌های جدا را با فاصله جایگزین می‌کند،
    # به‌جای تکیه بر خط جدید، بر اساس خود برچسب‌های شناخته‌شده (عربی:، ترجمه: و...) جدا می‌کنیم.
    field_labels = ["عربی", "ترجمه", "شرح", "راوی", "منبع", "باب", "شماره", "موضوعات"]
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

    arabic = fields.get("عربی", "")
    translation = fields.get("ترجمه", "")
    tafsir = fields.get("شرح", "") or None
    narrator = fields.get("راوی", "")
    source = fields.get("منبع", "")
    chapter = fields.get("باب", "")
    number = fields.get("شماره", "")
    topics_raw = fields.get("موضوعات", "")
    topics = [t.strip() for t in topics_raw.split("،") if t.strip()] or \
              [t.strip() for t in topics_raw.split(",") if t.strip()]

    if not arabic or not translation:
        await update.message.reply_text(
            "حداقل فیلدهای «عربی» و «ترجمه» الزامی هستند.\n"
            "مطمئن شوید هر فیلد را دقیقاً با همان برچسب (مثلاً «عربی:») نوشته‌اید."
        )
        return

    hadith_id = add_hadith(
        arabic, translation, narrator, source, chapter, number,
        tafsir_text=tafsir, topics=topics,
    )
    await update.message.reply_text(f"✅ حدیث با شناسه {hadith_id} با موفقیت ثبت شد.")


# ---------------- دستور ادمین برای افزودن/ویرایش شرح یک حدیث موجود ----------------
# فرمت: /addtafsir <شناسه_حدیث> <متن شرح>
# مثال: /addtafsir 3 این حدیث اشاره به اهمیت اخلاص در عمل دارد.

async def add_tafsir_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه‌ی این دستور را ندارید.")
        return

    parts = update.message.text.split(" ", 2)
    if len(parts) < 3:
        await update.message.reply_text(
            "فرمت صحیح استفاده:\n"
            "/addtafsir شناسه_حدیث متن شرح\n\n"
            "مثال:\n"
            "/addtafsir 3 این حدیث اشاره به اهمیت اخلاص در عمل دارد.\n\n"
            "برای پیدا کردن شناسه‌ی حدیث، از منوی احادیث یا حدیث تصادفی استفاده کنید "
            "(شناسه در پایین کارت حدیث یا هنگام افزودن نمایش داده می‌شود)."
        )
        return

    try:
        hadith_id = int(parts[1])
    except ValueError:
        await update.message.reply_text("شناسه‌ی حدیث باید یک عدد باشد.")
        return

    tafsir_text = parts[2].strip()
    row = get_hadith_by_id(hadith_id)
    if not row:
        await update.message.reply_text(f"حدیثی با شناسه‌ی {hadith_id} یافت نشد.")
        return

    update_hadith_tafsir(hadith_id, tafsir_text)
    await update.message.reply_text(f"✅ شرح حدیث شماره {hadith_id} با موفقیت ثبت/به‌روزرسانی شد.")
