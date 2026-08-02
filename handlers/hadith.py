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
    
    # Sort topics alphabetically for better organization
    sorted_topics = sorted(topics)

    # Categorize topics by first letter for better organization
    categorized = {}
    for t in sorted_topics:
        if t and len(t) > 0:
            first_letter = t[0]
            if first_letter not in categorized:
                categorized[first_letter] = []
            categorized[first_letter].append(t)
    
    # Create keyboard with organized topics
    buttons = []
    
    # Add topic buttons in groups of 3 for better layout
    for letter, topic_list in sorted(categorized.items()):
        # Add section separator if multiple letters
        if len(categorized) > 1:
            buttons.append([InlineKeyboardButton(f"────────── {letter} ──────────", callback_data="noop")])
        
        # Add topics in rows of 3
        for i in range(0, len(topic_list), 3):
            row = []
            for topic in topic_list[i:i+3]:
                row.append(InlineKeyboardButton(
                    f"• {topic[:15]}{'...' if len(topic) > 15 else ''}", 
                    callback_data=f"topic_{topic_hash(topic)}"
                ))
            buttons.append(row)
    
    # Add feature buttons with emoji
    buttons.append([InlineKeyboardButton("🎲 حدیث تصادفی", callback_data="hadith_random")])
    buttons.append([InlineKeyboardButton("🔍 جستجو پیشرفته در احادیث", callback_data="search_start_hadith")])
    buttons.append([InlineKeyboardButton("📖 جستجو با شناسه حدیث", callback_data="id_search_hadith")])
    buttons.append([InlineKeyboardButton("⭐ علاقهمندیهای من", callback_data="show_favorites")])
    buttons.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_back")])

    if topics:
        text = "📚 *گنجینه احادیث معصومین* 📚\n\n"
        text += f"🌿 تعداد احادیث: *{len(topics)} موضوع*\n"
        text += "────────────\n"
        text += "📌 *موضوعات:*\n"
        text += "برای مشاهده احادیث هر موضوع، یکی از موارد زیر را انتخاب کنید:\n\n"
        
        # Add topic list in bullet points
        for i, t in enumerate(sorted_topics, 1):
            text += f"{i}. {t}\n"
            
        text += "\n────────────\n"
        text += "🎯 *ویژگیهای جدید:*\n"
        text += "• جستجوی پیشرفته\n"
        text += "• جستجو با شناسه حدیث\n"
        text += "• مشاهده علاقهمندیها\n"
    else:
        text = "📿 *گنجینه احادیث* 📿\n\n"
        text += "هنوز موضوعی ثبت نشده است.\n"
        text += "برای افزودن حدیث جدید از دستور /addhadith استفاده کنید."

    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


def format_hadith(row):
    # Header with emoji
    header = "📿 *حدیثی از معصومین* 📿\n"
    
    # Narration chain if available
    text = ""
    if row['narrator']:
        text += f"👤 *ناقل*: {row['narrator']}\n\n"
    
    # Arabic text with beautiful formatting
    text += f"*📜 متن عربی:*\n{row['arabic_text']}\n\n"
    
    # Translation with separator
    text += f"────────────\n"
    text += f"*🔸 ترجمه فارسی:*\n{row['translation_text']}\n\n"
    
    # Commentary if exists
    if row["tafsir_text"]:
        text += f"────────────\n"
        text += f"*📖 تفسیر و توضیح:*\n{row['tafsir_text']}\n\n"
    
    # Source information box
    source = row["source_book"] or ""
    chapter = row["chapter"] or ""
    number = row["hadith_number"] or ""
    
    if source:
        text += f"────────────\n"
        text += f"*📚 مشخصات منبع:*\n"
        text += f"• کتاب: {source}\n"
        if chapter:
            text += f"• باب/فصل: {chapter}\n"
        if number:
            text += f"• شماره حدیث: {number}\n"
    
    # Footer with ID
    text += f"────────────\n"
    text += f"🆔 *شناسه حدیث*: `{row['id']}`"
    
    return header + text


def hadith_keyboard(hadith_id, topic_name=None, index=None, total=None, show_search_back=False):
    buttons = []
    
    # Enhanced navigation row with better UX
    if topic_name is not None and total and total > 1:
        h = topic_hash(topic_name)
        nav_row = []
        
        # Previous button with emoji
        if index > 0:
            nav_row.append(InlineKeyboardButton("⏪ حدیث قبلی", callback_data=f"topicnav_{index-1}_{h}"))
        
        # Current position indicator with context
        nav_row.append(InlineKeyboardButton(f"📍 {index+1} از {total}", callback_data="noop"))
        
        # Next button with emoji
        if index < total - 1:
            nav_row.append(InlineKeyboardButton("حدیث بعدی ⏩", callback_data=f"topicnav_{index+1}_{h}"))
        
        buttons.append(nav_row)
    
    # Action buttons row - user interactions
    action_buttons = []
    action_buttons.append(InlineKeyboardButton("⭐ افزودن به علاقهمندیها", callback_data=f"fav_hadith_{hadith_id}"))
    action_buttons.append(InlineKeyboardButton("📤 اشتراکگذاری", callback_data=f"share_hadith_{hadith_id}"))
    buttons.append(action_buttons)
    
    # Shortcuts row - quick actions
    shortcuts = []
    shortcuts.append(InlineKeyboardButton("🔍 جستجو در همین موضوع", callback_data=f"search_in_topic_{hadith_id}"))
    shortcuts.append(InlineKeyboardButton("📝 یادداشت بنویس", callback_data=f"add_note_{hadith_id}"))
    buttons.append(shortcuts)
    
    # Navigation row - back buttons
    navigation = []
    if show_search_back:
        navigation.append(InlineKeyboardButton("↩️ بازگشت به نتایج جستجو", callback_data="search_back"))
    navigation.append(InlineKeyboardButton("📚 بازگشت به موضوعات", callback_data="menu_hadith"))
    navigation.append(InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_back"))
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
    show_back = bool(context.user_data.get("last_search_query"))
    await query.edit_message_text(
        format_hadith(row),
        reply_markup=hadith_keyboard(row["id"], show_search_back=show_back),
    )


async def id_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمهی «📖 جستجو با شناسه حدیث»: از کاربر شناسه میخواهد."""
    query = update.callback_query
    await query.answer()
    
    text = "📋 *جستجو با شناسه حدیث*\n\n"
    text += "لطفاً شناسه حدیث مورد نظر خود را وارد کنید.\n"
    text += "────────────\n"
    text += "ℹ️ *راهنما:*\n"
    text += "• شناسه عددی است که در انتهای هر حدیث نمایش داده میشود\n"
    text += "• مثال: برای جستجوی حدیث با شناسه ۱۲۳، عدد ۱۲۳ را ارسال کنید\n"
    text += "• برای لغو، دکمه «❌ لغو» را بزنید"
    
    buttons = [[InlineKeyboardButton("❌ لغو", callback_data="menu_hadith")]]
    
    context.user_data["id_search_mode"] = True
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


async def id_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت جستجو با شناسه حدیث"""
    if not context.user_data.get("id_search_mode"):
        return
        
    text = update.message.text.strip()
    context.user_data["id_search_mode"] = False
    
    # Check if input is numeric
    if not text.isdigit():
        await update.message.reply_text(
            "❌ شناسه باید یک عدد باشد. لطفاً دوباره تلاش کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📚 بازگشت به موضوعات", callback_data="menu_hadith")]])
        )
        return
    
    hadith_id = int(text)
    row = get_hadith_by_id(hadith_id)
    
    if not row:
        await update.message.reply_text(
            f"❌ حدیثی با شناسه `{hadith_id}` یافت نشد.\n\n"
            f"لطفاً شناسه را بررسی کرده و دوباره تلاش کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📚 بازگشت به موضوعات", callback_data="menu_hadith")]]),
            parse_mode="Markdown"
        )
        return
    
    # Successful search
    await update.message.reply_text(
        format_hadith(row),
        reply_markup=hadith_keyboard(row["id"], show_search_back=False),
        parse_mode="Markdown"
    )


async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    favs = get_favorites(query.from_user.id)
    if not favs:
        await query.edit_message_text(
            "شما هنوز موردی به علاقهمندیها اضافه نکردهاید.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ منوی اصلی", callback_data="menu_back")]]
            ),
        )
        return

    # Categorize favorites by type
    hadith_favs = []
    quran_favs = []
    
    for f in favs:
        if f["item_type"] == "hadith":
            hadith_favs.append(f)
        else:
            quran_favs.append(f)
    
    text = "⭐ *گنجینه علاقهمندیهای شما* ⭐\n\n"
    
    # Hadith favorites section
    if hadith_favs:
        text += "📿 *احادیث مورد علاقه*:\n"
        text += "────────────\n"
        
        for i, f in enumerate(hadith_favs, 1):
            hadith = get_hadith_by_id(int(f["item_ref"]))
            if hadith:
                text += f"{i}. *حدیث #{hadith['id']}*\n"
                text += f"   📜 {hadith['arabic_text'][:50]}...\n"
                text += f"   🔸 {hadith['translation_text'][:40]}...\n"
                if hadith['source_book']:
                    text += f"   📚 {hadith['source_book']}"
                    if hadith['hadith_number']:
                        text += f" (حدیث {hadith['hadith_number']})"
                    text += "\n"
                text += f"   ────────────\n"
    
    # Quran favorites section
    if quran_favs:
        text += "\n📖 *آیات مورد علاقه*:\n"
        text += "────────────\n"
        for i, f in enumerate(quran_favs, 1):
            text += f"{i}. آیه {f['item_ref']}\n"
    
    if not hadith_favs and not quran_favs:
        text += "💭 *هنوز موردی اضافه نکردهاید*\n\n"
        text += "برای اضافه کردن حدیث یا آیه به علاقهمندیها:\n"
        text += "۱. حدیث یا آیه مورد نظر را پیدا کنید\n"
        text += "۲. روی دکمه «⭐ افزودن به علاقهمندیها» کلیک کنید"
        
        buttons = [[InlineKeyboardButton("📚 مشاهده احادیث", callback_data="menu_hadith")],
                  [InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_back")]]
    else:
        # Create buttons for each hadith favorite
        buttons = []
        for f in hadith_favs:
            hadith = get_hadith_by_id(int(f["item_ref"]))
            if hadith:
                preview = hadith['translation_text'][:30] if hadith['translation_text'] else hadith['arabic_text'][:30]
                buttons.append([
                    InlineKeyboardButton(
                        f"📿 مشاهده حدیث #{hadith['id']}", 
                        callback_data=f"hadithview_{hadith['id']}"
                    )
                ])
        
        # Add navigation buttons
        buttons.append([InlineKeyboardButton("🗑️ حذف همه علاقهمندیها", callback_data="clear_favorites")])
        buttons.append([InlineKeyboardButton("📚 مشاهده احادیث", callback_data="menu_hadith")])
        buttons.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_back")])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


# ==========================================================================
# جستجوی محدود به هر بخش (احادیث / نهج‌البلاغه / مفاتیح‌الجنان)
# ==========================================================================
# قبلاً یک دکمه‌ی «🔍 جستجو» در منوی اصلی بود که هم‌زمان بین هر سه بخش
# جستجو می‌کرد. حالا هر بخش دکمه‌ی جستجوی مخصوص خودش را دارد و فقط داخل
# همان بخش جستجو انجام می‌شود (types در search_all محدود می‌شود).
SEARCH_SCOPES = {
    "hadith": {
        "types": ["hadith"],
        "title": "📿 گنجینه احادیث معصومین",
        "prompt": (
            "✨ *حالت جستجوی پیشرفته در احادیث* ✨\n\n"
            "📝 **چه میتوانید جستجو کنید:**\n"
            "• متن عربی حدیث\n"
            "• ترجمه فارسی\n"
            "• تفسیر و توضیح\n"
            "• نام راوی\n"
            "• موضوعات مرتبط\n\n"
            "🔍 **ویژگیهای جستجو:**\n"
            "• پشتیبانی از اشتباهات تایپی\n"
            "• تطبیق خودکار حروف عربی/فارسی\n"
            "• جستجوی چند کلمهای\n\n"
            "✅ **دستورالعمل:**\n"
            "کلمات یا عبارات مورد نظر خود را وارد کنید.\n"
            "مثال: «صبر و تحمل»، «امام علی»، «توکل بر خدا»\n\n"
            "برای خروج، دکمه «🚪 خروج از حالت جستجو» را بزنید."
        ),
    },
    "nahj": {
        "types": ["nahj"],
        "title": "🕌 نهجالبلاغه",
        "prompt": (
            "🔍 حالا هر عبارتی بفرستید تا فقط بین *نهجالبلاغه* جستجو شود.\n\n"
            "برای خروج از حالت جستجو، دکمهی زیر را بزنید."
        ),
    },
    "mafatih": {
        "types": ["mafatih"],
        "title": "📗 مفاتیحالجنان",
        "prompt": (
            "🔍 حالا هر عبارتی بفرستید تا فقط بین *مفاتیحالجنان* جستجو شود.\n\n"
            "برای خروج از حالت جستجو، دکمهی زیر را بزنید."
        ),
    },
    "madahi": {
        "types": ["madahi"],
        "title": "🎙 مداحی و مولودی",
        "prompt": (
            "🔍 حالا هر عبارتی بفرستید تا فقط بین *عنوان، نام مداح و مناسبتِ فایلهای مداحی/مولودی* جستجو شود.\n\n"
            "برای خروج از حالت جستجو، دکمهی زیر را بزنید."
        ),
    },
}


async def search_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌ی «🔍 جستجو در ...» داخل منوی هر بخش. callback_data به شکل
    search_start_hadith / search_start_nahj / search_start_mafatih است."""
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
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🚪 خروج از حالت جستجو", callback_data="search_exit")]]
        ),
    )


def _build_search_message(text: str, results: list, scope_info: dict = None):
    """پیام و کیبورد نتایج سرچ رو می‌سازه. هم توسط ارسال اولیه‌ی نتایج و هم
    توسط دکمه‌ی «بازگشت به نتایج جستجو» استفاده می‌شه تا منطق تکرار نشه."""
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
        elif item["type"] == "mafatih":
            identifier = row["slug"] if row["slug"] else row["id"]
            # به‌جای ستون category در دیتابیس (که فقط چند مقدار کلی دارد و
            # لزوماً با ساختار واقعی منو یکی نیست)، از مسیر واقعی‌اش در منو
            # استفاده می‌کنیم — همان چیزی که کاربر با کلیک‌کردن در منو می‌بیند.
            location = MAFATIH_ITEM_LOCATION.get(str(identifier))
            sub_label = location[1] if location else "📗 مفاتیح‌الجنان"
            label = f"{sub_label} — {row['title']}"
            callback_data = f"mafitem_{identifier}"
        else:  # madahi
            flag = "🏴" if row["content_type"] == "madahi" else "💐"
            preview = row["title"] or ""
            if row["reciter"]:
                preview += f" - {row['reciter']}"
            label = f"{flag} {preview}"
            callback_data = f"madahi_play_{row['id']}"
        buttons.append([InlineKeyboardButton(label[:LABEL_LEN], callback_data=callback_data)])

    if len(results) > MAX_BUTTONS:
        # یه فاصله‌ی اضافه در انتهای متن پیش‌پرشده می‌ذاریم؛ بدونش بعضی وقتا
        # کلاینت تلگرام کوئری اینلاین رو خودکار اجرا نمی‌کنه مگه با یه تغییر
        # واقعی (تایپ/پاک‌کردن) در باکس، که تجربه‌ی کاربری بدی می‌سازه.
        buttons.append([
            InlineKeyboardButton(
                "🔎 دیدن همه‌ی نتایج (حالت اینلاین)",
                switch_inline_query_current_chat=text + " ",
            )
        ])

    buttons.append([InlineKeyboardButton("🚪 خروج از حالت جستجو", callback_data="search_exit")])

    if scope_info:
        message_text = (
            f"🔍 {len(results)} نتیجه برای «{text}» در {scope_info['title']} پیدا شد؛ یکی را انتخاب کنید:"
        )
    else:
        message_text = f"🔍 {len(results)} نتیجه برای «{text}» پیدا شد؛ یکی را انتخاب کنید:"
    return message_text, InlineKeyboardMarkup(buttons)


async def text_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """
    جستجوی متن آزاد در چت خصوصی، محدود به همان بخشی که کاربر دکمه‌ی «🔍
    جستجو در ...» آن را زده (احادیث / نهج‌البلاغه / مفاتیح‌الجنان)؛ پرچم
    context.user_data["search_scope"] مشخص می‌کند کدام بخش است. از همان
    موتور جستجوی یکپارچه‌ای استفاده می‌کند که سرچ Inline (@Laheghbot عبارت)
    هم استفاده می‌کند (search_all در database.py) و در برابر غلط تایپی و
    تفاوت حروف عربی/فارسی مقاوم است.
    """
    from database import search_all

    scope = context.user_data.get("search_scope")
    scope_info = SEARCH_SCOPES.get(scope)
    types = scope_info["types"] if scope_info else None

    results = search_all(text, limit=15, types=types)

    if not results:
        await update.message.reply_text(
            "چیزی با این عبارت پیدا نشد.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🚪 خروج از حالت جستجو", callback_data="search_exit")]]
            ),
        )
        return

    # آخرین عبارت سرچ رو نگه می‌داریم تا دکمه‌ی «بازگشت به نتایج جستجو» (روی
    # نمایش تک‌آیتم‌ها) بتونه دوباره همین لیست رو بسازه.
    context.user_data["last_search_query"] = text

    # اگر فقط یک حدیث پیدا شد، مثل قبل مستقیم متن کامل را نشان بده
    if len(results) == 1 and results[0]["type"] == "hadith":
        row = results[0]["row"]
        await update.message.reply_text(
            format_hadith(row),
            reply_markup=hadith_keyboard(row["id"], show_search_back=False),
        )
        return

    message_text, reply_markup = _build_search_message(text, results, scope_info)

    try:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    except BadRequest as e:
        # اگر بازهم (مثلاً به دلیل کاراکترهای خاص) از حد تلگرام رد شدیم، حداقل
        # یک پیام متنی بدون دکمه بفرست تا کاربر بی‌پاسخ نماند.
        logger.warning(f"reply_markup سرچ رد شد ({e})؛ ارسال fallback بدون دکمه.")
        await update.message.reply_text(
            f"🔍 {len(results)} نتیجه برای «{text}» پیدا شد، اما نمایش دکمه‌ها با خطا مواجه شد.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🔎 دیدن نتایج (حالت اینلاین)", switch_inline_query_current_chat=text + " ")],
                    [InlineKeyboardButton("🚪 خروج از حالت جستجو", callback_data="search_exit")],
                ]
            ),
        )


async def search_exit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌ی «🚪 خروج از حالت جستجو»: هم پرچم search_mode رو خاموش می‌کنه، هم
    کاربر رو به منوی همون بخشی که توش جستجو می‌کرد برمی‌گردونه (نه لزوماً
    منوی اصلی)."""
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
        # mafatih_menu_callback خودش query.answer() رو صدا می‌زنه
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
    """دکمه‌ی «⬅️ بازگشت به نتایج جستجو» که زیر نمایش تک‌آیتم‌ها (حدیث/نهج/
    مفاتیح) نشون داده می‌شه. آخرین عبارت سرچِ کاربر رو دوباره اجرا می‌کنه."""
    from database import search_all

    query = update.callback_query
    await query.answer()

    last_query = context.user_data.get("last_search_query")
    if not last_query:
        await query.answer("جستجوی قبلی‌ای پیدا نشد.", show_alert=True)
        return

    scope = context.user_data.get("search_scope")
    scope_info = SEARCH_SCOPES.get(scope)
    types = scope_info["types"] if scope_info else None

    results = search_all(last_query, limit=15, types=types)
    if not results:
        await query.edit_message_text("چیزی با این عبارت پیدا نشد.")
        return

    message_text, reply_markup = _build_search_message(last_query, results, scope_info)
    try:
        await query.edit_message_text(message_text, reply_markup=reply_markup)
    except BadRequest as e:
        logger.warning(f"reply_markup بازگشت به سرچ رد شد ({e}).")
        await query.edit_message_text(
            f"🔍 {len(results)} نتیجه برای «{last_query}» پیدا شد، اما نمایش دکمه‌ها با خطا مواجه شد."
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


async def clear_favorites_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمهی حذف همه علاقهمندیها"""
    from database import clear_user_favorites
    
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    clear_user_favorites(user_id)
    
    await query.edit_message_text(
        "✅ *همه علاقهمندیهای شما حذف شد*\n\n"
        "علاقهمندیها شامل احادیث و آیات قرآن شده بودند.\n"
        "برای اضافه کردن مجدد، از دکمه «⭐ افزودن به علاقهمندیها» استفاده کنید.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 مشاهده احادیث", callback_data="menu_hadith")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_back")]
        ]),
        parse_mode="Markdown"
    )
