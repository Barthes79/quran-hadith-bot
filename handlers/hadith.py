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
    get_hadith_categories, get_hadiths_by_category,
    get_hadith_categories_with_count, get_subtopics_by_category,
    categorize_topics, get_category_emoji,
)
from config import ADMIN_IDS
from text_utils import normalize_input_text

logger = logging.getLogger(__name__)


def topic_hash(topic_name: str) -> str:
    return hashlib.md5(topic_name.encode("utf-8")).hexdigest()[:12]


# ============================================================
# توابع نمایش و فرمت‌دهی
# ============================================================

HADITH_HEADERS = [
    "پرتوی از کلام معصومین (ع)",
    "گوهری از دریای حکمت اهل‌بیت (ع)",
    "درسی از مکتب نور",
    "سخنی نورانی از خاندان وحی",
    "چراغی برای مسیر زندگی",
    "یادگاری از زبان معصوم (ع)",
]

HADITH_CLOSINGS = [
    "🕯 کلام اهل‌بیت، چراغ راه زندگی است.",
    "🕯 هر حدیث، چراغی برای دل‌های تشنه‌ی حقیقت است.",
    "🕯 در سخن معصومین (ع)، درمان همه‌ی دردهاست.",
    "🕯 این سخن را در زندگی خود جاری کنیم.",
    "🕯 یک جمله، یک دنیا معرفت.",
    "🕯 نور کلام اهل‌بیت، تاریکی دل را می‌زداید.",
]

DIVIDER = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄"


def format_hadith(row):
    header = HADITH_HEADERS[row["id"] % len(HADITH_HEADERS)]
    closing = HADITH_CLOSINGS[row["id"] % len(HADITH_CLOSINGS)]

    lines = [f"📿 《{header}》", ""]

    if row["narrator"]:
        lines.append(f"🕊 *{row['narrator']}* می‌فرماید:")
        lines.append("")

    lines.append(f"﴿ {row['arabic_text']} ﴾")
    lines.append("")
    lines.append(f"❝ {row['translation_text']} ❞")

    if row["tafsir_text"]:
        lines.append("")
        lines.append("📖 *شرح:*")
        lines.append(row["tafsir_text"])

    source = row["source_book"] or ""
    has_meta = bool(source or row["chapter"] or row["hadith_number"])
    has_category = False
    try:
        has_category = bool(row["category"])
    except (KeyError, TypeError):
        has_category = False

    if has_meta or has_category:
        lines.append("")
        lines.append(DIVIDER)

    if has_meta:
        if source:
            lines.append(f"📚 منبع: {source}")
        if row["chapter"]:
            lines.append(f"▫️ باب: {row['chapter']}")
        if row["hadith_number"]:
            lines.append(f"▫️ حدیث: {row['hadith_number']}")

    # نمایش دسته‌بندی — بدون تکرار ایموجی، چون خودِ row['category'] از قبل
    # با ایموجی ذخیره شده (مثلاً "🌿 اخلاق و رفتار")
    if has_category:
        lines.append(f"📂 {row['category']}")

    lines.append("")
    lines.append(closing)
    lines.append(f"🔖 شناسه: {row['id']}")

    return "\n".join(lines)


JUMP_STEP = 10  # اندازه‌ی هر صفحه (۱۰ تا ۱۰ تا)
JUMP_BUTTONS_PER_ROW = 5

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa_num(n):
    """تبدیل عدد به رقم فارسی، مثلاً 12 -> ۱۲"""
    return str(n).translate(_PERSIAN_DIGITS)


def _jump_buttons(index, total, callback_prefix, h):
    """
    ساخت دکمه‌های پرش صفحه‌ای (هر صفحه ۱۰ حدیث، مثلاً «صفحه ۱»، «صفحه ۲»، ...)
    به‌علاوه دو دکمه‌ی میانبر «اولین» و «آخرین»، تا کاربر مجبور نباشد
    پشت سر هم روی «بعدی» بزند تا به حدیث موردنظرش برسد.
    با زدن هر صفحه، به اولین حدیث همان صفحه منتقل می‌شود.
    """
    if not total or total <= JUMP_STEP:
        return []

    rows = []

    # ردیف میانبر اول/آخر
    shortcuts = []
    if index != 0:
        shortcuts.append(InlineKeyboardButton("⏮ اولین", callback_data=f"{callback_prefix}_0_{h}"))
    if index != total - 1:
        shortcuts.append(InlineKeyboardButton("آخرین ⏭", callback_data=f"{callback_prefix}_{total-1}_{h}"))
    if shortcuts:
        rows.append(shortcuts)

    # ردیف‌های صفحه‌ای (صفحه ۱، صفحه ۲، ...)
    page_starts = list(range(0, total, JUMP_STEP))
    current_row = []
    for page_num, start in enumerate(page_starts, start=1):
        end = min(start + JUMP_STEP, total) - 1
        label = f"صفحه {_fa_num(page_num)}"
        if start <= index <= end:
            label = f"· {label} ·"
        current_row.append(
            InlineKeyboardButton(label, callback_data=f"{callback_prefix}_{start}_{h}")
        )
        if len(current_row) == JUMP_BUTTONS_PER_ROW:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)

    return rows


def hadith_keyboard(hadith_id, topic_name=None, index=None, total=None, 
                    show_search_back=False, category_name=None, 
                    sub_topic=None):
    buttons = []
    
    # ناوبری در موضوع یا دسته
    if topic_name is not None and total and total > 1:
        h = topic_hash(topic_name)
        nav_row = []
        if index > 0:
            nav_row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"topicnav_{index-1}_{h}"))
        nav_row.append(InlineKeyboardButton(f"{index+1}/{total}", callback_data="noop"))
        if index < total - 1:
            nav_row.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"topicnav_{index+1}_{h}"))
        buttons.append(nav_row)
        buttons.extend(_jump_buttons(index, total, "topicnav", h))
    
    # ناوبری در دسته
    elif category_name is not None and total and total > 1:
        h = topic_hash(category_name)
        nav_row = []
        if index > 0:
            nav_row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"catnav_{index-1}_{h}"))
        nav_row.append(InlineKeyboardButton(f"{index+1}/{total}", callback_data="noop"))
        if index < total - 1:
            nav_row.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"catnav_{index+1}_{h}"))
        buttons.append(nav_row)
        buttons.extend(_jump_buttons(index, total, "catnav", h))
    
    action_row = [
        InlineKeyboardButton("⭐", callback_data=f"fav_hadith_{hadith_id}"),
        InlineKeyboardButton("📤 اشتراک", switch_inline_query=f"h{hadith_id}"),
    ]
    buttons.append(action_row)

    navigation = []
    if show_search_back:
        navigation.append(InlineKeyboardButton("↩️ نتایج جستجو", callback_data="search_back"))

    # دکمه‌ی بازگشت به صفحه‌ی دسته‌بندی احادیث (لیست همه‌ی دسته‌ها)
    # نکته: وقتی داخل یک دسته هستیم باید از callback مخصوص "cat_menu_" استفاده کنیم
    # (همان چیزی که قبلاً هم برای این حالت استفاده می‌شد و به category_menu_callback وصل است)
    if category_name:
        navigation.append(InlineKeyboardButton(
            "↩️ بازگشت به دسته‌بندی",
            callback_data=f"cat_menu_{topic_hash(category_name)}"
        ))
    else:
        navigation.append(InlineKeyboardButton(
            "↩️ بازگشت به دسته‌بندی",
            callback_data="menu_hadith_categories"
        ))

    navigation.append(InlineKeyboardButton("🏠 خانه", callback_data="menu_back"))
    buttons.append(navigation)
    
    return InlineKeyboardMarkup(buttons)


# ============================================================
# منوی اصلی دسته‌بندی
# ============================================================

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    نمایش منوی دسته‌بندی احادیث
    """
    query = update.callback_query
    
    # دریافت تعداد حدیث در هر دسته
    categories_with_count = get_hadith_categories_with_count()
    
    # دسته‌ی «موضوعات دیگر» یک دسته‌ی کاتچ‌آل موقتی بود که دیگر نمایش داده نمی‌شود
    # (تمام حدیث‌ها بعد از اصلاح دسته‌بندی، یک دسته‌ی معنادار دارند)
    categories_with_count = {
        cat: count for cat, count in categories_with_count.items()
        if cat != "💎 موضوعات دیگر"
    }
    total_hadiths = sum(categories_with_count.values())
    
    buttons = []
    row = []
    
    for category, count in categories_with_count.items():
        # نکته: category خودش از قبل با ایموجی ذخیره شده (مثلاً "🌿 اخلاق و رفتار")
        # پس دیگر نیازی به اضافه کردن دوباره‌ی ایموجی نیست
        label = category
        if count > 0:
            label += f" ({count})"
        
        btn = InlineKeyboardButton(label, callback_data=f"category_{topic_hash(category)}")
        
        if len(row) < 2:
            row.append(btn)
        else:
            buttons.append(row)
            row = [btn]
    
    if row:
        buttons.append(row)
    
    # دکمه‌های اضافی
    buttons.append([
        InlineKeyboardButton("🎲 حدیث تصادفی", callback_data="hadith_random"),
        InlineKeyboardButton("🔍 جستجو", callback_data="search_start_hadith"),
    ])
    buttons.append([
        InlineKeyboardButton("⭐ علاقه‌مندی‌ها", callback_data="menu_favorites"),
        InlineKeyboardButton("🏠 خانه", callback_data="menu_back"),
    ])
    
    text = (
        "📜 **گنجینه‌ی احادیث اهل‌بیت (ع)**\n"
        "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n"
        f"✨ {total_hadiths} حدیث نورانی در {len(categories_with_count)} دسته\n\n"
        "یک دسته را انتخاب کنید 👇"
    )
    
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def category_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    نمایش حدیث‌های یک دسته (با ناوبری)
    """
    query = update.callback_query
    await query.answer()
    
    cat_h = query.data.replace("category_", "")
    categories = get_hadith_categories()
    
    category_name = None
    for cat in categories:
        if topic_hash(cat) == cat_h:
            category_name = cat
            break
    
    if category_name is None:
        await query.edit_message_text(
            "این دسته دیگر معتبر نیست.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 دسته‌بندی", callback_data="menu_hadith_categories")],
                [InlineKeyboardButton("🏠 خانه", callback_data="menu_back")]
            ])
        )
        return
    
    # دریافت حدیث‌های این دسته
    rows = get_hadiths_by_category(category_name)
    
    if not rows:
        await query.edit_message_text(
            f"حدیثی در دسته «{category_name}» یافت نشد.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 دسته‌بندی", callback_data="menu_hadith_categories")],
                [InlineKeyboardButton("🏠 خانه", callback_data="menu_back")]
            ])
        )
        return
    
    # نمایش اولین حدیث
    row = rows[0]
    await query.edit_message_text(
        format_hadith(row),
        reply_markup=hadith_keyboard(
            row["id"], 
            category_name=category_name, 
            index=0, 
            total=len(rows)
        ),
        parse_mode="Markdown"
    )


async def category_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ناوبری بین حدیث‌های یک دسته
    """
    query = update.callback_query
    await query.answer()
    
    _, index, cat_h = query.data.split("_", 2)
    index = int(index)
    
    categories = get_hadith_categories()
    category_name = None
    for cat in categories:
        if topic_hash(cat) == cat_h:
            category_name = cat
            break
    
    if category_name is None:
        await query.answer("این دسته دیگر معتبر نیست.", show_alert=True)
        return
    
    rows = get_hadiths_by_category(category_name)
    if not rows or index < 0 or index >= len(rows):
        await query.answer("موردی یافت نشد.", show_alert=True)
        return
    
    row = rows[index]
    await query.edit_message_text(
        format_hadith(row),
        reply_markup=hadith_keyboard(
            row["id"], 
            category_name=category_name, 
            index=index, 
            total=len(rows)
        ),
        parse_mode="Markdown"
    )


async def category_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    بازگشت به منوی دسته‌بندی از داخل یک دسته
    """
    query = update.callback_query
    await query.answer()
    await show_categories(update, context)


# ============================================================
# بقیه توابع (موضوعات قدیمی، تصادفی، علاقه‌مندی‌ها، جستجو و...)
# ============================================================

async def show_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    نمایش منوی قدیمی موضوعات (برای سازگاری با نسخه‌های قبلی)
    """
    from database import get_connection

    query = update.callback_query
    conn = get_connection()
    total_hadiths = conn.execute("SELECT COUNT(*) FROM hadiths").fetchone()[0]
    topic_rows = conn.execute(
        "SELECT topic_name, COUNT(*) AS cnt FROM hadith_topics "
        "GROUP BY topic_name ORDER BY topic_name"
    ).fetchall()
    conn.close()

    buttons = []
    pending = None
    for t in topic_rows:
        topic, cnt = t["topic_name"], t["cnt"]
        label = f"🔖 {topic} ({cnt})"
        if len(label) > 28:
            label = label[:26] + "…"
        btn = InlineKeyboardButton(label, callback_data=f"topic_{topic_hash(topic)}")
        if pending is None:
            pending = btn
        else:
            buttons.append([pending, btn])
            pending = None
    if pending is not None:
        buttons.append([pending])

    buttons.append([InlineKeyboardButton("📂 دسته‌بندی جدید", callback_data="menu_hadith_categories")])
    buttons.append([InlineKeyboardButton("🎲 حدیث تصادفی", callback_data="hadith_random")])
    buttons.append([InlineKeyboardButton("🔍 جستجو", callback_data="search_start_hadith")])
    buttons.append([InlineKeyboardButton("⭐ علاقه‌مندی‌ها", callback_data="menu_favorites")])
    buttons.append([InlineKeyboardButton("🏠 خانه", callback_data="menu_back")])

    if topic_rows:
        text = (
            "📿 ✦ موضوعات احادیث ✦\n"
            "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n"
            f"✨ {total_hadiths} حدیث نورانی\n\n"
            "⚠️ این منو قدیمی است. از «دسته‌بندی جدید» استفاده کنید."
        )
    else:
        text = "📿 احادیث معصومین (ع)\n\nهنوز حدیثی ثبت نشده."

    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def topic_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # کد قدیمی برای سازگاری
    query = update.callback_query
    await query.answer()
    topic_h = query.data.replace("topic_", "")
    topics = get_all_topics()
    topic_name = next((t for t in topics if topic_hash(t) == topic_h), None)
    if topic_name is None:
        await query.edit_message_text(
            "این موضوع دیگر معتبر نیست.\n\n"
            "از منوی «دسته‌بندی جدید» استفاده کنید.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 دسته‌بندی", callback_data="menu_hadith_categories")],
                [InlineKeyboardButton("🏠 خانه", callback_data="menu_back")]
            ])
        )
        return
    rows = get_hadiths_by_topic(topic_name)

    if not rows:
        await query.edit_message_text(
            f"حدیثی برای موضوع '{topic_name}' یافت نشد.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 دسته‌بندی", callback_data="menu_hadith_categories")],
                [InlineKeyboardButton("🏠 خانه", callback_data="menu_back")]
            ])
        )
        return

    row = rows[0]
    await query.edit_message_text(
        format_hadith(row),
        reply_markup=hadith_keyboard(row["id"], topic_name=topic_name, index=0, total=len(rows)),
        parse_mode="Markdown"
    )


async def topic_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # کد قدیمی برای سازگاری
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
        parse_mode="Markdown"
    )


async def random_hadith_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    row = get_random_hadith()
    if not row:
        await query.edit_message_text("هنوز حدیثی در دیتابیس ثبت نشده است.")
        return
    
    # پیدا کردن دسته حدیث
    category = row.get("category")
    await query.edit_message_text(
        format_hadith(row), 
        reply_markup=hadith_keyboard(row["id"], category_name=category if category else None),
        parse_mode="Markdown"
    )


async def fav_hadith_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    hadith_id = query.data.replace("fav_hadith_", "")
    add_favorite(query.from_user.id, "hadith", hadith_id)
    await query.answer("به علاقهمندیها اضافه شد ⭐")


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # کد قبلی
    query = update.callback_query
    favs = get_favorites(query.from_user.id)
    if not favs:
        await query.edit_message_text(
            "هنوز موردی به علاقهمندیها اضافه نکردهاید.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 خانه", callback_data="menu_back")]]
            ),
        )
        return

    hadith_favs = [f for f in favs if f["item_type"] == "hadith"]
    
    text = "⭐ علاقهمندیهای شما\n\n"
    
    if hadith_favs:
        text += "📿 احادیث:\n"
        for i, f in enumerate(hadith_favs[:10], 1):
            hadith = get_hadith_by_id(int(f["item_ref"]))
            if hadith:
                preview = (hadith['translation_text'] or '')[:30]
                text += f"{i}. {preview}...\n"
    
    buttons = []
    for f in hadith_favs[:5]:
        hadith = get_hadith_by_id(int(f["item_ref"]))
        if hadith:
            buttons.append([InlineKeyboardButton(f"📿 #{hadith['id']}", callback_data=f"hadithview_{hadith['id']}")])
    
    buttons.append([InlineKeyboardButton("🗑 پاک کردن همه", callback_data="clear_favorites")])
    buttons.append([InlineKeyboardButton("🏠 خانه", callback_data="menu_back")])

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
            [InlineKeyboardButton("📂 دسته‌بندی", callback_data="menu_hadith_categories")],
            [InlineKeyboardButton("🏠 خانه", callback_data="menu_back")]
        ])
    )


# ============================================================
# توابع کمکی برای کپی و فیلتر منبع
# ============================================================

async def copy_hadith_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کپی متن حدیث و ارسال به کاربر"""
    query = update.callback_query
    hadith_id = query.data.replace("copy_hadith_", "")
    row = get_hadith_by_id(int(hadith_id))

    if not row:
        await query.answer("حدیث یافت نشد.", show_alert=True)
        return

    try:
        await context.bot.send_message(chat_id=query.from_user.id, text=format_hadith(row))
        await query.answer("📋 متن حدیث به همین چت فرستاده شد")
    except Exception as e:
        logger.warning(f"copy_hadith_callback: ارسال پیام کپی شکست خورد: {e}")
        await query.answer("مشکلی توی فرستادن متن پیش اومد. دوباره امتحان کن.", show_alert=True)


async def filter_source_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فیلتر حدیث‌ها بر اساس منبع"""
    query = update.callback_query
    await query.answer()
    
    hadith_id = query.data.replace("filter_source_", "")
    current_hadith = get_hadith_by_id(int(hadith_id))
    
    if not current_hadith:
        await query.answer("حدیث یافت نشد.", show_alert=True)
        return
    
    source_book = current_hadith["source_book"]
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
    
    buttons.append([InlineKeyboardButton("📂 دسته‌بندی", callback_data="menu_hadith_categories")])
    buttons.append([InlineKeyboardButton("🏠 خانه", callback_data="menu_back")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# ============================================================
# جستجو
# ============================================================

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
        category = row.get("category")
        await update.message.reply_text(
            format_hadith(row),
            reply_markup=hadith_keyboard(row["id"], category_name=category if category else None),
            parse_mode="Markdown"
        )
        return

    # نمایش نتایج
    buttons = []
    for item in results[:10]:
        row = item["row"]
        if item["type"] == "hadith":
            preview = (row["translation_text"] or row["arabic_text"] or "")[:30]
            label = f"📿 {preview}..."
            callback_data = f"hadithview_{row['id']}"
        else:
            continue
        buttons.append([InlineKeyboardButton(label, callback_data=callback_data)])

    buttons.append([InlineKeyboardButton("🚪 خروج", callback_data="search_exit")])

    await update.message.reply_text(
        f"🔍 {len(results)} نتیجه برای «{text}»",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def search_exit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data["search_mode"] = False
    context.user_data["search_scope"] = None
    await query.answer()
    await show_categories(update, context)


async def search_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await search_exit_callback(update, context)


async def hadith_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    hadith_id = int(query.data.replace("hadithview_", ""))
    row = get_hadith_by_id(hadith_id)
    if not row:
        await query.edit_message_text("این حدیث دیگر در دسترس نیست.")
        return
    
    category = row.get("category")
    await query.edit_message_text(
        format_hadith(row),
        reply_markup=hadith_keyboard(row["id"], category_name=category if category else None),
        parse_mode="Markdown"
    )


# ============================================================
# جستجو با شناسه حدیث
# ============================================================

async def id_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش صفحه جستجو با شناسه حدیث"""
    query = update.callback_query
    await query.answer()
    
    text = "🆔 جستجو با شناسه حدیث\n\n"
    text += "شناسه عددی را که در انتهای هر حدیث نمایش داده میشود وارد کنید.\n"
    text += "مثال: 123"
    
    buttons = [[InlineKeyboardButton("❌ لغو", callback_data="menu_hadith_categories")]]
    
    context.user_data["id_search_mode"] = True
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def id_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش ورودی شناسه حدیث از کاربر"""
    if not context.user_data.get("id_search_mode"):
        return
        
    text = update.message.text.strip()
    context.user_data["id_search_mode"] = False
    
    if not text.isdigit():
        await update.message.reply_text(
            "❌ شناسه باید عدد باشد.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 دسته‌بندی", callback_data="menu_hadith_categories")]
            ])
        )
        return
    
    hadith_id = int(text)
    row = get_hadith_by_id(hadith_id)
    
    if not row:
        await update.message.reply_text(
            f"❌ حدیثی با شناسه {hadith_id} یافت نشد.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 دسته‌بندی", callback_data="menu_hadith_categories")]
            ])
        )
        return
    
    category = row.get("category")
    await update.message.reply_text(
        format_hadith(row),
        reply_markup=hadith_keyboard(row["id"], category_name=category if category else None),
        parse_mode="Markdown"
    )


# ============================================================
# دستورات ادمین
# ============================================================

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
    
    # دسته‌بندی خودکار
    category = categorize_topics(topics)
    from database import update_hadith_category
    update_hadith_category(hadith_id, category)
    
    await update.message.reply_text(f"✅ حدیث با شناسه {hadith_id} ثبت شد.\n📂 دسته: {category}")


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
        cat = row.get("category", "بدون دسته")
        lines.append(f"#{row['id']} | {cat}\n{preview}...\n")

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
        # به‌روزرسانی دسته
        category = categorize_topics(topics)
        from database import update_hadith_category
        update_hadith_category(hadith_id, category)

    updated_row = get_hadith_by_id(hadith_id)
    await update.message.reply_text(
        f"✅ حدیث {hadith_id} به‌روزرسانی شد.\n\n" + format_hadith(updated_row),
        parse_mode="Markdown"
    )


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