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
    return hashlib.md5(topic_name.encode("utf-8")).hexdigest()[:12]


async def show_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import get_connection
    
    query = update.callback_query
    topics = get_all_topics()
    
    conn = get_connection()
    total_hadiths = conn.execute("SELECT COUNT(*) FROM hadiths").fetchone()[0]
    conn.close()
    
    sorted_topics = sorted(topics)
    
    buttons = []
    for topic in sorted_topics:
        display_text = topic[:20] + ('…' if len(topic) > 20 else '')
        buttons.append([InlineKeyboardButton(display_text, callback_data=f"topic_{topic_hash(topic)}")])
    
    buttons.append([InlineKeyboardButton("🎲 حدیث تصادفی", callback_data="hadith_random")])
    buttons.append([InlineKeyboardButton("🔍 جستجو", callback_data="search_start_hadith")])
    buttons.append([InlineKeyboardButton("🆔 جستجو با شناسه", callback_data="id_search_hadith")])
    buttons.append([InlineKeyboardButton("⭐ علاقهمندیها", callback_data="show_favorites")])
    buttons.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_back")])

    if topics:
        text = f"📚 احادیث معصومین\n\n📊 {total_hadiths} حدیث در {len(topics)} موضوع\n\nیک موضوع انتخاب کنید:"
    else:
        text = "📚 احادیث معصومین\n\nهنوز حدیثی ثبت نشده.\nبرای افزودن: /addhadith"

    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


def format_hadith(row):
    text = "📿 حدیثی از معصومین\n\n"
    
    if row['narrator']:
        text += f"👤 ناقل: {row['narrator']}\n\n"
    
    text += f"{row['arabic_text']}\n\n"
    text += f"🔹 ترجمه:\n{row['translation_text']}\n"
    
    if row["tafsir_text"]:
        text += f"\n📖 توضیح:\n{row['tafsir_text']}\n"
    
    source = row["source_book"] or ""
    if source:
        text += f"\n📚 منبع: {source}"
        if row["chapter"]:
            text += f" • {row['chapter']}"
        if row["hadith_number"]:
            text += f" (#{row['hadith_number']})"
    
    text += f"\n\n🆔 شناسه: {row['id']}"
    
    return text


def hadith_keyboard(hadith_id, topic_name=None, index=None, total=None, show_search_back=False, source_book=None):
    buttons = []
    
    if topic_name is not None and total and total > 1:
        h = topic_hash(topic_name)
        nav_row = []
        
        if index > 0:
            nav_row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"topicnav_{index-1}_{h}"))
        
        nav_row.append(InlineKeyboardButton(f"{index+1}/{total}", callback_data="noop"))
        
        if index < total - 1:
            nav_row.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"topicnav_{index+1}_{h}"))
        
        buttons.append(nav_row)
    
    action_row = [
        InlineKeyboardButton("⭐", callback_data=f"fav_hadith_{hadith_id}"),
        InlineKeyboardButton("📋 کپی", callback_data=f"copy_hadith_{hadith_id}"),
        InlineKeyboardButton("📤 اشتراک", switch_inline_query=f"h{hadith_id}"),
    ]
    buttons.append(action_row)
    
    if source_book:
        display = source_book[:20] + ('…' if len(source_book) > 20 else '')
        buttons.append([InlineKeyboardButton(f"📖 {display}", callback_data=f"filter_source_{hadith_id}")])
    
    navigation = []
    if show_search_back:
        navigation.append(InlineKeyboardButton("↩️ نتایج جستجو", callback_data="search_back"))
    navigation.append(InlineKeyboardButton("📚 موضوعات", callback_data="menu_hadith"))
    navigation.append(InlineKeyboardButton("🏠 منو", callback_data="menu_back"))
    buttons.append(navigation)
    
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
        await query.edit_message_text(
            "این موضوع دیگر معتبر نیست.\n\n"
            "برای انتخاب مجدد، از منوی «📚 احادیث» استفاده کنید.",
            reply_markup=hadith_keyboard(-1)
        )
        return
    rows = get_hadiths_by_topic(topic_name)

    if not rows:
        await query.edit_message_text(
            f"حدیثی برای موضوع '{topic_name}' یافت نشد.\n\n"
            "شاید موضوع خالی از حدیث باشد. برای انتخاب مجدد، به «📚 احادیث» بازگردید.",
            reply_markup=hadith_keyboard(-1)
        )
        return

    row = rows[0]
    await query.edit_message_text(
        format_hadith(row),
        reply_markup=hadith_keyboard(row["id"], topic_name=topic_name, index=0, total=len(rows), source_book=row.get("source_book")),
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
        reply_markup=hadith_keyboard(row["id"], topic_name=topic_name, index=index, total=len(rows), source_book=row.get("source_book")),
    )


async def random_hadith_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    row = get_random_hadith()
    if not row:
        await query.edit_message_text("هنوز حدیثی در دیتابیس ثبت نشده است.")
        return
    await query.edit_message_text(format_hadith(row), reply_markup=hadith_keyboard(row["id"], source_book=row.get("source_book")))


async def fav_hadith_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    hadith_id = query.data.replace("fav_hadith_", "")
    add_favorite(query.from_user.id, "hadith", hadith_id)
    await query.answer("به علاقهمندیها اضافه شد ⭐")


async def copy_hadith_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    hadith_id = query.data.replace("copy_hadith_", "")
    row = get_hadith_by_id(int(hadith_id))
    
    if not row:
        await query.answer("حدیث یافت نشد.", show_alert=True)
        return
    
    text = f"📿 {row['narrator'] or 'حدیث'}\n\n"
    text += f"{row['arabic_text']}\n\n"
    text += f"🔹 ترجمه:\n{row['translation_text']}\n"
    
    if row["tafsir_text"]:
        text += f"\n📖 توضیح:\n{row['tafsir_text']}\n"
    
    source = row["source_book"] or ""
    if source:
        text += f"\n📚 منبع: {source}"
        if row["chapter"]:
            text += f" - {row['chapter']}"
        if row["hadith_number"]:
            text += f" (#{row['hadith_number']})"
    
    await query.answer("متن کپی شد ✅")
    await context.bot.send_message(chat_id=query.from_user.id, text=text)


async def filter_source_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    hadith_id = query.data.replace("filter_source_", "")
    current_hadith = get_hadith_by_id(int(hadith_id))
    
    if not current_hadith:
        await query.answer("حدیث یافت نشد.", show_alert=True)
        return
    
    source_book = current_hadith.get("source_book")
    if not source_book:
        await query.answer("منبع مشخص نیست.", show_alert=True)
        return
    
    from database import list_hadiths
    rows = list_hadiths(source_book=source_book, limit=50)
    
    if not rows or len(rows) == 1:
        await query.answer("حدیث دیگری از این منبع نیست.", show_alert=True)
        return
    
    text = f"📖 احادیث {source_book}\n\nتعداد: {len(rows)} حدیث\n\n"
    
    for i, row in enumerate(rows[:10], 1):
        preview = (row["translation_text"] or "")[:40].replace("\n", " ")
        text += f"{i}. {preview}...\n"
    
    if len(rows) > 10:
        text += f"\n... و {len(rows) - 10} حدیث دیگر"
    
    buttons = []
    for row in rows[:8]:
        preview = (row["translation_text"] or row["arabic_text"] or "")[:25]
        buttons.append([InlineKeyboardButton(f"#{row['id']} {preview}", callback_data=f"hadithview_{row['id']}")])
    
    buttons.append([InlineKeyboardButton("📚 موضوعات", callback_data="menu_hadith")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def hadith_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    hadith_id = int(query.data.replace("hadithview_", ""))
    row = get_hadith_by_id(hadith_id)
    if not row:
        await query.edit_message_text("این حدیث دیگر در دسترس نیست.")
        return
    show_back = bool(context.user_data.get("last_search_query"))
    await query.edit_message_text(
        format_hadith(row),
        reply_markup=hadith_keyboard(row["id"], show_search_back=show_back, source_book=row.get("source_book")),
    )


async def id_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = "🆔 جستجو با شناسه حدیث\n\n"
    text += "شناسه حدیث مورد نظر را وارد کنید.\n"
    text += "شناسه عددی است که در انتهای هر حدیث نمایش داده میشود."
    
    buttons = [[InlineKeyboardButton("❌ لغو", callback_data="menu_hadith")]]
    
    context.user_data["id_search_mode"] = True
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def id_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("id_search_mode"):
        return
        
    text = update.message.text.strip()
    context.user_data["id_search_mode"] = False
    
    if not text.isdigit():
        await update.message.reply_text(
            "❌ شناسه باید عدد باشد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📚 موضوعات", callback_data="menu_hadith")]])
        )
        return
    
    hadith_id = int(text)
    row = get_hadith_by_id(hadith_id)
    
    if not row:
        await update.message.reply_text(
            f"❌ حدیثی با شناسه {hadith_id} یافت نشد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📚 موضوعات", callback_data="menu_hadith")]])
        )
        return
    
    await update.message.reply_text(
        format_hadith(row),
        reply_markup=hadith_keyboard(row["id"], source_book=row.get("source_book"))
    )


async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    favs = get_favorites(query.from_user.id)
    if not favs:
        await query.edit_message_text(
            "هنوز موردی به علاقهمندیها اضافه نکردهاید.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_back")]]
            ),
        )
        return

    hadith_favs = [f for f in favs if f["item_type"] == "hadith"]
    quran_favs = [f for f in favs if f["item_type"] != "hadith"]
    
    text = "⭐ علاقهمندیهای شما\n\n"
    
    if hadith_favs:
        text += "📿 احادیث:\n"
        for i, f in enumerate(hadith_favs[:10], 1):
            hadith = get_hadith_by_id(int(f["item_ref"]))
            if hadith:
                preview = (hadith['translation_text'] or '')[:30]
                text += f"{i}. {preview}...\n"
    
    if quran_favs:
        text += f"\n📖 آیات: {len(quran_favs)} آیه\n"
    
    buttons = []
    for f in hadith_favs[:5]:
        hadith = get_hadith_by_id(int(f["item_ref"]))
        if hadith:
            buttons.append([InlineKeyboardButton(f"📿 #{hadith['id']}", callback_data=f"hadithview_{hadith['id']}")])
    
    buttons.append([InlineKeyboardButton("🗑 پاک کردن همه", callback_data="clear_favorites")])
    buttons.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_back")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def clear_favorites_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import clear_user_favorites
    
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    clear_user_favorites(user_id)
    
    await query.edit_message_text(
        "✅ همه علاقهمندیها حذف شد.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 احادیث", callback_data="menu_hadith")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_back")]
        ])
    )


SEARCH_SCOPES = {
    "hadith": {
        "types": ["hadith"],
        "title": "📿 احادیث",
        "prompt": (
            "🔍 جستجوی پیشرفته در احادیث\n\n"
            "میتوانید جستجو کنید:\n"
            "• متن عربی یا فارسی\n"
            "• نام راوی\n"
            "• موضوع\n\n"
            "عبارت مورد نظر را بنویسید:"
        ),
    },
    "nahj": {
        "types": ["nahj"],
        "title": "🕌 نهجالبلاغه",
        "prompt": "🔍 جستجو در نهجالبلاغه\n\nعبارت مورد نظر را بنویسید:",
    },
    "mafatih": {
        "types": ["mafatih"],
        "title": "📗 مفاتیحالجنان",
        "prompt": "🔍 جستجو در مفاتیحالجنان\n\nعبارت مورد نظر را بنویسید:",
    },
    "madahi": {
        "types": ["madahi"],
        "title": "🎙 مداحی",
        "prompt": "🔍 جستجو در مداحی\n\nعبارت مورد نظر را بنویسید:",
    },
}


async def search_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    scope = query.data.replace("search_start_", "")
    scope_info = SEARCH_SCOPES.get(scope)
    if not scope_info:
        return

    context.user_data["search_mode"] = True
    context.user_data["search_scope"] = scope

    await query.edit_message_text(
        scope_info["prompt"],
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🚪 خروج", callback_data="search_exit")]]
        ),
    )


def _build_search_message(text: str, results: list, scope_info: dict = None):
    from handlers.nahj import NAHJ_MENU_LABELS, NAHJ_ITEM_LABELS
    from handlers.mafatih import MAFATIH_ITEM_LOCATION

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
        elif item["type"] == "mafatih":
            identifier = row["slug"] if row["slug"] else row["id"]
            location = MAFATIH_ITEM_LOCATION.get(str(identifier))
            sub_label = location[1] if location else "📗 مفاتیحالجنان"
            label = f"{sub_label} — {row['title']}"
            callback_data = f"mafitem_{identifier}"
        else:
            flag = "🏴" if row["content_type"] == "madahi" else "💐"
            preview = row["title"] or ""
            if row["reciter"]:
                preview += f" - {row['reciter']}"
            label = f"{flag} {preview}"
            callback_data = f"madahi_play_{row['id']}"
        buttons.append([InlineKeyboardButton(label[:LABEL_LEN], callback_data=callback_data)])

    if len(results) > MAX_BUTTONS:
        buttons.append([
            InlineKeyboardButton(
                "🔎 همه نتایج",
                switch_inline_query_current_chat=text + " ",
            )
        ])

    buttons.append([InlineKeyboardButton("🚪 خروج", callback_data="search_exit")])

    if scope_info:
        message_text = f"🔍 {len(results)} نتیجه برای «{text}» در {scope_info['title']}"
    else:
        message_text = f"🔍 {len(results)} نتیجه برای «{text}»"
    return message_text, InlineKeyboardMarkup(buttons)


async def text_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    from database import search_all

    scope = context.user_data.get("search_scope")
    scope_info = SEARCH_SCOPES.get(scope)
    types = scope_info["types"] if scope_info else None

    results = search_all(text, limit=15, types=types)

    if not results:
        await update.message.reply_text(
            "چیزی پیدا نشد.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🚪 خروج", callback_data="search_exit")]]
            ),
        )
        return

    context.user_data["last_search_query"] = text

    if len(results) == 1 and results[0]["type"] == "hadith":
        row = results[0]["row"]
        await update.message.reply_text(
            format_hadith(row),
            reply_markup=hadith_keyboard(row["id"], source_book=row.get("source_book")),
        )
        return

    message_text, reply_markup = _build_search_message(text, results, scope_info)

    try:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    except BadRequest as e:
        logger.warning(f"reply_markup error: {e}")
        await update.message.reply_text(
            f"🔍 {len(results)} نتیجه پیدا شد.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🔎 نتایج", switch_inline_query_current_chat=text + " ")],
                    [InlineKeyboardButton("🚪 خروج", callback_data="search_exit")],
                ]
            ),
        )


async def search_exit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    scope = context.user_data.get("search_scope")
    context.user_data["search_mode"] = False
    context.user_data["search_scope"] = None

    if scope == "hadith":
        await query.answer()
        await show_topics(update, context)
    elif scope == "nahj":
        await query.answer()
        from handlers.nahj import show_nahj_menu
        await show_nahj_menu(update, context)
    elif scope == "mafatih":
        from handlers.mafatih import mafatih_menu_callback
        await mafatih_menu_callback(update, context)
    elif scope == "madahi":
        await query.answer()
        from handlers.madahi import madahi_menu_callback
        await madahi_menu_callback(update, context)
    else:
        from handlers.start import main_menu_keyboard
        await query.answer()
        await query.edit_message_text("منوی اصلی:", reply_markup=main_menu_keyboard())


async def search_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import search_all

    query = update.callback_query
    await query.answer()

    last_query = context.user_data.get("last_search_query")
    if not last_query:
        await query.answer("جستجویی پیدا نشد.", show_alert=True)
        return

    scope = context.user_data.get("search_scope")
    scope_info = SEARCH_SCOPES.get(scope)
    types = scope_info["types"] if scope_info else None

    results = search_all(last_query, limit=15, types=types)
    if not results:
        await query.edit_message_text("چیزی پیدا نشد.")
        return

    message_text, reply_markup = _build_search_message(last_query, results, scope_info)
    try:
        await query.edit_message_text(message_text, reply_markup=reply_markup)
    except BadRequest as e:
        logger.warning(f"search_back error: {e}")


async def add_hadith_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه این دستور را ندارید.")
        return

    full_text = update.message.text.split(" ", 1)
    if len(full_text) < 2:
        await update.message.reply_text(
            "فرمت صحیح:\n\n"
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
            "فیلدهای «عربی» و «ترجمه» الزامی هستند."
        )
        return

    hadith_id = add_hadith(
        arabic, translation, narrator, source, chapter, number,
        tafsir_text=tafsir, topics=topics,
    )
    await update.message.reply_text(f"✅ حدیث با شناسه {hadith_id} ثبت شد.")


async def add_tafsir_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه این دستور را ندارید.")
        return

    parts = update.message.text.split(" ", 2)
    if len(parts) < 3:
        await update.message.reply_text(
            "فرمت:\n"
            "/addtafsir شناسه متن شرح\n\n"
            "مثال:\n"
            "/addtafsir 3 این حدیث درباره اخلاص است."
        )
        return

    try:
        hadith_id = int(parts[1])
    except ValueError:
        await update.message.reply_text("شناسه باید عدد باشد.")
        return

    tafsir_text = parts[2].strip()
    row = get_hadith_by_id(hadith_id)
    if not row:
        await update.message.reply_text(f"حدیثی با شناسه {hadith_id} یافت نشد.")
        return

    update_hadith_tafsir(hadith_id, tafsir_text)
    await update.message.reply_text(f"✅ شرح حدیث {hadith_id} ثبت شد.")


async def find_hadith_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه این دستور را ندارید.")
        return

    parts = update.message.text.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text("فرمت: /findhadith متن جستجو")
        return

    query = parts[1].strip()
    rows = search_hadiths(query)
    if not rows:
        await update.message.reply_text("حدیثی پیدا نشد.")
        return

    lines = [f"🔎 {len(rows)} نتیجه:\n"]
    for row in rows:
        preview = (row["translation_text"] or "")[:60].replace("\n", " ")
        lines.append(f"#{row['id']} | {row['source_book'] or '-'}\n{preview}...\n")

    await update.message.reply_text("\n".join(lines))


async def edit_hadith_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه این دستور را ندارید.")
        return

    full_text = update.message.text.split(" ", 1)
    if len(full_text) < 2:
        await update.message.reply_text(
            "فرمت:\n"
            "/edithadith شناسه\n"
            "ترجمه: ...\n"
            "شرح: ..."
        )
        return

    raw = full_text[1].strip()
    first_line, _, rest = raw.partition("\n")
    first_line = first_line.strip()

    if not first_line.isdigit():
        await update.message.reply_text("خط اول باید شناسه حدیث باشد.")
        return

    hadith_id = int(first_line)
    existing = get_hadith_by_id(hadith_id)
    if not existing:
        await update.message.reply_text(f"حدیثی با شناسه {hadith_id} یافت نشد.")
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
        await update.message.reply_text("حداقل یک فیلد بنویسید.")
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
    await update.message.reply_text(f"✅ حدیث {hadith_id} بهروزرسانی شد.\n\n" + format_hadith(updated_row))


async def del_hadith_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه این دستور را ندارید.")
        return

    parts = update.message.text.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text("فرمت: /delhadith شناسه")
        return

    raw_ids = parts[1].strip().split(",")
    try:
        ids = [int(x.strip()) for x in raw_ids if x.strip()]
    except ValueError:
        await update.message.reply_text("شناسهها باید عدد باشند.")
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
        lines.append(f"⚠️ یافت نشد: {', '.join(map(str, not_found))}")

    await update.message.reply_text("\n".join(lines) or "کاری انجام نشد.")
