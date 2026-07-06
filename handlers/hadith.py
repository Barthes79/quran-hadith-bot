import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import (
    get_all_topics, get_hadiths_by_topic, get_random_hadith,
    search_hadiths, add_favorite, get_favorites, add_hadith,
)
from config import ADMIN_IDS


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
    return text


def hadith_keyboard(hadith_id):
    buttons = [
        [InlineKeyboardButton("⭐ افزودن به علاقه‌مندی‌ها", callback_data=f"fav_hadith_{hadith_id}")],
        [InlineKeyboardButton("⬅️ موضوعات", callback_data="menu_hadith")],
    ]
    return InlineKeyboardMarkup(buttons)


async def topic_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    topic_name = query.data.replace("topic_", "")
    rows = get_hadiths_by_topic(topic_name)

    if not rows:
        await query.edit_message_text("حدیثی برای این موضوع یافت نشد.")
        return

    row = rows[0]
    await query.edit_message_text(format_hadith(row), reply_markup=hadith_keyboard(row["id"]))


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
        if f["item_type"] == "ayah":
            lines.append(f"📖 آیه {f['item_ref']}")
        else:
            lines.append(f"📿 حدیث شماره {f['item_ref']}")

    lines.append("\n(برای مشاهده کامل هرکدام، از منوی قرآن/احادیث دوباره وارد شوید.)")
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
            "راوی: ...\n"
            "منبع: ...\n"
            "باب: ...\n"
            "شماره: ...\n"
            "موضوعات: صبر، تقوا"
        )
        return

    body = full_text[1]

    # پارسینگ مقاوم: چون تلگرام گاهی خط‌های جدا را با فاصله جایگزین می‌کند،
    # به‌جای تکیه بر خط جدید، بر اساس خود برچسب‌های شناخته‌شده (عربی:، ترجمه: و...) جدا می‌کنیم.
    field_labels = ["عربی", "ترجمه", "راوی", "منبع", "باب", "شماره", "موضوعات"]
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

    hadith_id = add_hadith(arabic, translation, narrator, source, chapter, number, topics=topics)
    await update.message.reply_text(f"✅ حدیث با شناسه {hadith_id} با موفقیت ثبت شد.")
