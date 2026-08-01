import re
import logging
import hashlib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from database import (
    get_all_topics, get_hadiths_by_topic, get_random_hadith,
    search_hadiths, add_favorite, get_favorites, add_hadith,
    get_hadith_by_id, update_hadith_tafsir,
    update_hadith, delete_hadith, set_hadith_topics,
)
from config import ADMIN_IDS
from text_utils import normalize_input_text

logger = logging.getLogger(__name__)


def topic_hash(topic_name: str) -> str:
    """
    یک شناسه‌ی کوتاه (۱۲ کاراکتری) برای هر موضوع می‌سازد تا در callback_data
    استفاده شود. تلگرام محدودیت ۶۴ بایتی برای callback_data دارد و اسم موضوع
    (که فارسی و چندبایتی است) می‌تواند به‌راحتی از این محدودیت رد شود؛ به همین
    خاطر به‌جای خود متن، از هش کوتاهش استفاده می‌کنیم.
    """
    return hashlib.md5(topic_name.encode("utf-8")).hexdigest()[:12]


async def show_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    topics = get_all_topics()

    buttons = []
    row = []
    for t in topics:
        row.append(InlineKeyboardButton(t, callback_data=f"topic_{topic_hash(t)}"))
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
    text = f"{row['narrator'] or ''}\n\n"
    text += f"🌿 {row['arabic_text']}\n\n"
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
        h = topic_hash(topic_name)
        nav_row = []
        if index > 0:
            nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"topicnav_{index-1}_{h}"))
        nav_row.append(InlineKeyboardButton(f"{index+1}/{total}", callback_data="noop"))
        if index < total - 1:
            nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"topicnav_{index+1}_{h}"))
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("⭐ افزودن به علاقه‌مندی‌ها", callback_data=f"fav_hadith_{hadith_id}")])
    buttons.append([InlineKeyboardButton("⬅️ موضوعات", callback_data="menu_hadith")])
    return InlineKeyboardMarkup(buttons)


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


async def topic_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    topic_h = query.data.replace("topic_", "")
    topics = get_all_topics()
    topic_name = next((t for t in topics if topic_hash(t) == topic_h), None)
    if topic_name is None:
        await query.edit_message_text("این موضوع دیگر معتبر نیست. لطفاً دوباره از منو انتخاب کنید.")
        return
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
    _, index, topic_h = query.data.split("_", 2)
    index = int(index)

    topics = get_all_topics()
    topic_name = next((t for t in topics if topic_hash(t) == topic_h), None)
    if topic_name is None:
        await query.answer("این موضوع دیگر معتبر نیست.", show_alert=True)
        return

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


async def hadith_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش کامل یک حدیث با شناسه مشخص (استفاده‌شده از جمله در دکمه‌ی
    «مشاهده کامل» زیر نتایج سرچ اینلاین، وقتی متن حدیث طولانی بوده و در
    پیام اینلاین جا نشده است)."""
    query = update.callback_query
    await query.answer()
    hadith_id = int(query.data.replace("hadithview_", ""))
    row = get_hadith_by_id(hadith_id)
    if not row:
        await query.edit_message_text("این حدیث دیگر در دسترس نیست.")
        return
    await query.edit_message_text(format_hadith(row), reply_markup=hadith_keyboard(row["id"]))


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
    """
    جستجوی متن آزاد در چت خصوصی. قبلاً این تابع فقط جدول hadiths را با
    search_hadiths() جستجو می‌کرد و همیشه پیام «حدیثی با این عبارت یافت نشد»
    را نشان می‌داد، حتی وقتی عبارت مربوط به مفاتیح یا نهج‌البلاغه بود.
    حالا از همان موتور جستجوی یکپارچه‌ای استفاده می‌کند که سرچ Inline
    (@نام_ربات عبارت) هم استفاده می‌کند (search_all در database.py):
    هم‌زمان روی حدیث + نهج‌البلاغه + مفاتیح جستجو می‌کند و در برابر غلط
    تایپی و تفاوت حروف عربی/فارسی مقاوم است.
    """
    from database import search_all

    results = search_all(text, limit=15)

    if not results:
        await update.message.reply_text("چیزی با این عبارت پیدا نشد.")
        return

    # اگر فقط یک حدیث پیدا شد، مثل قبل مستقیم متن کامل را نشان بده
    if len(results) == 1 and results[0]["type"] == "hadith":
        row = results[0]["row"]
        await update.message.reply_text(format_hadith(row), reply_markup=hadith_keyboard(row["id"]))
        return

    from handlers.nahj import NAHJ_MENU_LABELS, NAHJ_ITEM_LABELS
    from handlers.mafatih import MAFATIH_ITEM_LOCATION

    # تلگرام حجم reply_markup را محدود می‌کند؛ با نتایج زیاد (لیبل‌های فارسی
    # چندبایتی) به‌راحتی از این حد رد می‌شویم و کل پیام با خطای «Reply markup
    # is too long» رد می‌شود (بدون هیچ پیامی به کاربر). برای امنیت، حداکثر
    # ۱۰ دکمه نشان می‌دهیم و لیبل هر کدام را کوتاه‌تر می‌کنیم.
    MAX_BUTTONS = 10
    LABEL_LEN = 35
    shown_results = results[:MAX_BUTTONS]

    buttons = []
    for item in shown_results:
        row = item["row"]
        if item["type"] == "hadith":
            preview = (row["translation_text"] or row["arabic_text"] or "")[:LABEL_LEN]
            label = f"📿 {preview}"
            callback_data = f"hadithview_{row['id']}"
        elif item["type"] == "nahj":
            cat_label = NAHJ_MENU_LABELS.get(row["category"], "🕌")
            item_label = NAHJ_ITEM_LABELS.get(row["category"], "")
            title_part = f" — {row['title']}" if row["title"] else ""
            label = f"{cat_label} {item_label} {row['number']}{title_part}"
            callback_data = f"nahjitem_{row['category']}_{row['number']}"
        else:  # mafatih
            identifier = row["slug"] if row["slug"] else row["id"]
            # به‌جای ستون category در دیتابیس (که فقط چند مقدار کلی دارد و
            # لزوماً با ساختار واقعی منو یکی نیست)، از مسیر واقعی‌اش در منو
            # استفاده می‌کنیم — همان چیزی که کاربر با کلیک‌کردن در منو می‌بیند.
            location = MAFATIH_ITEM_LOCATION.get(str(identifier))
            sub_label = location[1] if location else "📗 مفاتیح‌الجنان"
            label = f"{sub_label} — {row['title']}"
            callback_data = f"mafitem_{identifier}"
        buttons.append([InlineKeyboardButton(label[:LABEL_LEN], callback_data=callback_data)])

    count_note = (
        f" (۱۰ مورد اول نشان داده شد؛ برای دیدن همه‌ی نتایج از @Laheghbot {text} استفاده کنید)"
        if len(results) > MAX_BUTTONS else ""
    )
    message_text = f"🔍 {len(results)} نتیجه برای «{text}» پیدا شد؛ یکی را انتخاب کنید:{count_note}"

    try:
        await update.message.reply_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    except BadRequest as e:
        # اگر بازهم (مثلاً به دلیل کاراکترهای خاص) از حد تلگرام رد شدیم، حداقل
        # یک پیام متنی بدون دکمه بفرست تا کاربر بی‌پاسخ نماند.
        logger.warning(f"reply_markup سرچ رد شد ({e})؛ ارسال fallback بدون دکمه.")
        await update.message.reply_text(
            f"🔍 {len(results)} نتیجه برای «{text}» پیدا شد، اما نمایش دکمه‌ها با خطا مواجه شد.\n"
            f"برای دیدن نتایج از حالت اینلاین استفاده کنید: @Laheghbot {text}"
        )


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
    logger.info("DEBUG addhadith raw=%r", full_text[1])
    logger.info("DEBUG addhadith normalized=%r", body)

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
    logger.info("DEBUG addhadith fields_keys=%r arabic_len=%d translation_len=%d", list(fields.keys()), len(arabic), len(translation))
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


# ---------------- دستور ادمین برای پیدا کردن شناسه‌ی یک حدیث ----------------
# فرمت: /findhadith <بخشی از متن عربی یا ترجمه>
# مثال: /findhadith صبر

async def find_hadith_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه‌ی این دستور را ندارید.")
        return

    parts = update.message.text.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text(
            "فرمت صحیح استفاده:\n"
            "/findhadith بخشی از متن عربی یا ترجمه\n\n"
            "مثال:\n"
            "/findhadith صبر"
        )
        return

    query = parts[1].strip()
    rows = search_hadiths(query)
    if not rows:
        await update.message.reply_text("هیچ حدیثی با این عبارت پیدا نشد.")
        return

    lines = [f"🔎 {len(rows)} نتیجه برای «{query}»:\n"]
    for row in rows:
        preview = (row["translation_text"] or "")[:60].replace("\n", " ")
        lines.append(f"🆔 {row['id']} | {row['source_book'] or '-'}\n{preview}...\n")

    lines.append("برای ویرایش: /edithadith <شناسه>\nبرای حذف: /delhadith <شناسه>")
    await update.message.reply_text("\n".join(lines))


# ---------------- دستور ادمین برای ویرایش یک حدیث موجود ----------------
# فرمت (شناسه بلافاصله بعد از دستور و یک فاصله، بقیه فقط فیلدهایی که می‌خواهید عوض شود):
# /edithadith 12
# ترجمه: ترجمه جدید
# شرح: توضیح جدید
# موضوعات: صبر، تقوا
#
# نیازی نیست همه‌ی فیلدها را بنویسید؛ فقط همان‌هایی که می‌خواهید تغییر کنند.

async def edit_hadith_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه‌ی این دستور را ندارید.")
        return

    full_text = update.message.text.split(" ", 1)
    if len(full_text) < 2:
        await update.message.reply_text(
            "فرمت صحیح استفاده (شناسه بلافاصله بعد از دستور، بقیه فقط فیلدهایی که می‌خواهید تغییر کند):\n\n"
            "/edithadith 12\n"
            "ترجمه: ترجمه جدید\n"
            "شرح: توضیح جدید\n"
            "راوی: ...\n"
            "منبع: ...\n"
            "باب: ...\n"
            "شماره: ...\n"
            "موضوعات: صبر، تقوا\n\n"
            "برای پیدا کردن شناسه از /findhadith استفاده کنید."
        )
        return

    raw = full_text[1].strip()
    first_line, _, rest = raw.partition("\n")
    first_line = first_line.strip()

    if not first_line.isdigit():
        await update.message.reply_text(
            "خط اول باید فقط شناسه (عدد) حدیث باشد. برای پیدا کردن شناسه از /findhadith استفاده کنید."
        )
        return

    hadith_id = int(first_line)
    existing = get_hadith_by_id(hadith_id)
    if not existing:
        await update.message.reply_text(f"حدیثی با شناسه‌ی {hadith_id} یافت نشد.")
        return

    body = normalize_input_text(rest)
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

    if not fields:
        await update.message.reply_text(
            "هیچ فیلدی برای تغییر پیدا نشد. حداقل یک فیلد مثل «ترجمه: ...» بنویسید."
        )
        return

    topics_raw = fields.pop("موضوعات", None)

    update_hadith(
        hadith_id,
        arabic_text=fields.get("عربی"),
        translation_text=fields.get("ترجمه"),
        tafsir_text=fields.get("شرح"),
        narrator=fields.get("راوی"),
        source_book=fields.get("منبع"),
        chapter=fields.get("باب"),
        hadith_number=fields.get("شماره"),
    )

    if topics_raw is not None:
        topics = [t.strip() for t in topics_raw.split("،") if t.strip()] or \
                  [t.strip() for t in topics_raw.split(",") if t.strip()]
        set_hadith_topics(hadith_id, topics)

    updated_row = get_hadith_by_id(hadith_id)
    await update.message.reply_text(
        f"✅ حدیث شماره {hadith_id} به‌روزرسانی شد.\n\n" + format_hadith(updated_row)
    )


# ---------------- دستور ادمین برای حذف یک یا چند حدیث ----------------
# فرمت: /delhadith <شناسه> یا چند شناسه با کاما جدا شده
# مثال: /delhadith 12
# مثال: /delhadith 12,13,14

async def del_hadith_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه‌ی این دستور را ندارید.")
        return

    parts = update.message.text.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text(
            "فرمت صحیح استفاده:\n"
            "/delhadith شناسه\n"
            "/delhadith شناسه۱,شناسه۲,شناسه۳\n\n"
            "برای پیدا کردن شناسه از /findhadith استفاده کنید."
        )
        return

    raw_ids = parts[1].strip().split(",")
    try:
        ids = [int(x.strip()) for x in raw_ids if x.strip()]
    except ValueError:
        await update.message.reply_text("شناسه‌ها باید عدد باشند، مثال: /delhadith 12,13")
        return

    deleted = []
    not_found = []
    for hid in ids:
        row = get_hadith_by_id(hid)
        if not row:
            not_found.append(hid)
            continue
        delete_hadith(hid)
        deleted.append(hid)

    lines = []
    if deleted:
        lines.append(f"✅ {len(deleted)} حدیث حذف شد: {', '.join(map(str, deleted))}")
    if not_found:
        lines.append(f"⚠️ این شناسه‌ها پیدا نشدند: {', '.join(map(str, not_found))}")

    await update.message.reply_text("\n".join(lines) or "کاری انجام نشد.")
