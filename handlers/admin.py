import random
import re
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ChatType, ParseMode  # ✅ ParseMode اضافه شد
from database import (
    get_group_settings, update_group_settings, get_all_active_daily_groups,
    get_random_hadith, get_random_nahj_item, get_random_mafatih_item, get_connection,
    get_mafatih_item_flexible, update_mafatih_audio,
    upsert_chat, get_active_groups, count_users, register_user,
)
from config import ADMIN_IDS
from handlers.hadith import format_hadith
from handlers.nahj import NAHJ_MENU_LABELS, NAHJ_ITEM_LABELS
from services.quran_api import get_ayah, get_surah_list
from gamification.events import dispatch_event
from gamification.config import EVENT_DAILY_LOGIN, pigeon_feature_level_for_count, get_pigeon_level_up_message
from gamification.pigeon import get_pigeon_feature_progress
from gamification.db import set_pigeon_salavat_count
from text_utils import to_persian_digits

MAFATIH_CATEGORY_FA = {
    "daily": "🕋 اعمال روزانه",
    "ziyarat": "🕌 زیارت",
    "weekly": "📅 اعمال هفتگی",
    "monthly": "🌙 اعمال ماهانه",
    "munajat": "💬 مناجات",
    "special": "✨ مناسبت خاص",
}

CONTENT_TYPES = ("hadith", "ayah", "nahj", "mafatih")
CONTENT_TYPE_LABELS = {
    "hadith": "📿 حدیث",
    "ayah": "📖 آیه قرآن",
    "nahj": "🕌 نهج‌البلاغه",
    "mafatih": "🤲 دعای مفاتیح",
}

DEFAULT_WELCOME_TEXT = "سلام {name} عزیز 🌙\nخوش اومدی به جمع‌مون! امیدواریم لحظات خوبی رو اینجا سپری کنی."
DEFAULT_QUIET_START = 23
DEFAULT_QUIET_END = 7

def _code(value) -> str:
    return f"`{value}`"

# ============================================================
# دستورات ادمین برای تست
# ============================================================

async def set_salavat_count_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دستور /setsalavat <تعداد>  -- فقط برای ادمین‌ها
    تعداد صلوات کامل کاربر را به مقدار دلخواه تنظیم می‌کند (برای تست).
    """
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ این دستور فقط برای ادمین‌ها در دسترس است.")
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ لطفاً تعداد را مشخص کنید.\n"
            "مثال: `/setsalavat 25`\n"
            "تعداد کل صلوات کامل را تنظیم می‌کند (سطح بر اساس آن محاسبه می‌شود)."
        )
        return

    try:
        new_count = int(context.args[0])
        if new_count < 0:
            new_count = 0
    except ValueError:
        await update.message.reply_text("⚠️ مقدار وارد شده باید یک عدد صحیح باشد.")
        return

    # تنظیم تعداد برای خود کاربر
    user_id = user.id
    set_pigeon_salavat_count(user_id, new_count)

    # محاسبه سطح جدید
    new_level = pigeon_feature_level_for_count(new_count)
    progress = get_pigeon_feature_progress(user_id)

    msg = (
        f"✅ تعداد صلوات کامل شما به {_code(to_persian_digits(new_count))} تنظیم شد.\n"
        f"سطح فعلی «پیشرفت قابلیت‌ها»: {_code(to_persian_digits(new_level))}\n"
        f"تعداد صلوات تا سطح بعدی: {_code(to_persian_digits(progress['remaining'])) if progress['remaining'] > 0 else 'به سقف رسیده‌اید'}\n\n"
        f"برای مشاهده‌ی کارت کبوتر، «کبوترم» را بفرستید."
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ============================================================
# ادامه کدهای قبلی (بدون تغییر)
# ============================================================

async def is_group_admin(update: Update) -> bool:
    if update.effective_chat.type == ChatType.PRIVATE:
        return True
    member = await update.effective_chat.get_member(update.effective_user.id)
    return member.status in ("administrator", "creator")


async def _require_admin(update: Update, query) -> bool:
    if not await is_group_admin(update):
        await query.answer("فقط ادمین‌های گروه می‌توانند تنظیمات را تغییر دهند.", show_alert=True)
        return False
    return True


# =====================================================================
# ساخت متن و کیبورد منوی اصلی تنظیمات
# =====================================================================

def _on_off(value) -> str:
    return "✅ فعال" if value else "❌ غیرفعال"


def _content_types_summary(settings) -> str:
    active = [CONTENT_TYPE_LABELS[t] for t in CONTENT_TYPES if settings[f"content_{t}"]]
    return "، ".join(active) if active else "هیچ‌کدام (پست خودکار عملاً چیزی نمی‌فرستد)"


def _quiet_summary(settings) -> str:
    if settings["quiet_start_hour"] is None or settings["quiet_start_hour"] < 0:
        return "❌ غیرفعال"
    return f"✅ از ساعت {settings['quiet_start_hour']} تا {settings['quiet_end_hour']}"


def build_main_menu(settings):
    text = (
        "⚙️ *تنظیمات پیشرفته‌ی گروه*\n\n"
        f"🔔 پست خودکار: {_on_off(settings['daily_post_enabled'])}\n"
        f"⏱ فاصله‌ی ارسال: هر {settings['post_interval_hours']} ساعت (لنگر: ساعت {settings['daily_post_hour']})\n"
        f"📚 نوع محتوا: {_content_types_summary(settings)}\n"
        f"🌙 بازه‌ی سکوت شبانه: {_quiet_summary(settings)}\n"
        f"👋 خوش‌آمدگویی اعضای جدید: {_on_off(settings['welcome_enabled'])}\n"
        f"🧹 پاک‌سازی پیام ورود/خروج: {_on_off(settings['delete_service_messages'])}\n"
        f"🔗 حذف لینک از غیرادمین‌ها: {_on_off(settings['block_links'])}\n"
    )
    buttons = [
        [InlineKeyboardButton(f"🔔 پست خودکار: {_on_off(settings['daily_post_enabled'])}", callback_data="gset_toggle_daily")],
        [
            InlineKeyboardButton("⏱ فاصله‌ی ارسال", callback_data="gset_interval_menu"),
            InlineKeyboardButton("🕐 ساعت شروع", callback_data="gset_hour_menu"),
        ],
        [InlineKeyboardButton("📚 نوع محتوای پست خودکار", callback_data="gset_content_menu")],
        [InlineKeyboardButton("🌙 بازه‌ی سکوت شبانه", callback_data="gset_quiet_menu")],
        [InlineKeyboardButton("🎲 ارسال یک مورد الان", callback_data="gset_send_now")],
        [InlineKeyboardButton(f"👋 خوش‌آمدگویی: {_on_off(settings['welcome_enabled'])}", callback_data="gset_welcome_toggle")],
        [InlineKeyboardButton(f"🧹 پاک‌سازی ورود/خروج: {_on_off(settings['delete_service_messages'])}", callback_data="gset_service_toggle")],
        [InlineKeyboardButton(f"🔗 حذف لینک غیرادمین: {_on_off(settings['block_links'])}", callback_data="gset_links_toggle")],
        [InlineKeyboardButton("🏆 رتبه‌بندی و آمار مسابقه‌ی گروه", callback_data="gset_leaderboard")],
        [InlineKeyboardButton("✖️ بستن", callback_data="gset_close")],
    ]
    return text, InlineKeyboardMarkup(buttons)


def _back_button(target="gset_main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=target)]])


async def _show_main_menu(query, chat_id):
    settings = get_group_settings(chat_id)
    text, markup = build_main_menu(settings)
    await query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")


# =====================================================================
# دستور ورودی /groupsettings
# =====================================================================

async def group_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == ChatType.PRIVATE:
        await update.message.reply_text("این دستور فقط داخل گروه‌ها کاربرد دارد.")
        return

    if not await is_group_admin(update):
        await update.message.reply_text("فقط ادمین‌های گروه می‌توانند تنظیمات را تغییر دهند.")
        return

    settings = get_group_settings(update.effective_chat.id)
    text, markup = build_main_menu(settings)
    await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")


# =====================================================================
# روتر مرکزی تمام دکمه‌های تنظیمات (همه با پیشوند gset_ شروع می‌شوند)
# =====================================================================

async def group_settings_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat_id = update.effective_chat.id

    if data == "gset_close":
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    if data == "gset_main":
        await query.answer()
        await _show_main_menu(query, chat_id)
        return

    if data == "gset_leaderboard":
        await query.answer()
        await _show_leaderboard(query, chat_id)
        return

    # از اینجا به بعد همه چیز نیازمند ادمین بودن است
    if not await _require_admin(update, query):
        return

    if data == "gset_toggle_daily":
        settings = get_group_settings(chat_id)
        update_group_settings(chat_id, daily_post_enabled=0 if settings["daily_post_enabled"] else 1)
        await query.answer("بروزرسانی شد ✅")
        await _show_main_menu(query, chat_id)

    elif data == "gset_interval_menu":
        await query.answer()
        buttons = [
            [InlineKeyboardButton(f"هر {i} ساعت", callback_data=f"gset_interval_{i}") for i in row]
            for row in [range(1, 5), range(5, 9), range(9, 13), range(13, 17), range(17, 21), range(21, 25)]
        ]
        buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="gset_main")])
        await query.edit_message_text("⏱ هر چند ساعت یک‌بار پست خودکار ارسال شود؟", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("gset_interval_"):
        hours = int(data.replace("gset_interval_", ""))
        update_group_settings(chat_id, post_interval_hours=hours)
        await query.answer("ذخیره شد ✅")
        await _show_main_menu(query, chat_id)

    elif data == "gset_hour_menu":
        await query.answer()
        await query.edit_message_text(
            "🕐 پست خودکار از چه ساعتی شروع به کار کند؟ (لنگرِ زمان‌بندی)",
            reply_markup=_hour_grid("gset_hour_"),
        )

    elif data.startswith("gset_hour_"):
        hour = int(data.replace("gset_hour_", ""))
        update_group_settings(chat_id, daily_post_hour=hour)
        await query.answer("ذخیره شد ✅")
        await _show_main_menu(query, chat_id)

    elif data == "gset_content_menu":
        await query.answer()
        await _show_content_menu(query, chat_id)

    elif data.startswith("gset_content_toggle_"):
        ctype = data.replace("gset_content_toggle_", "")
        settings = get_group_settings(chat_id)
        col = f"content_{ctype}"
        new_val = 0 if settings[col] else 1
        others_on = any(settings[f"content_{t}"] for t in CONTENT_TYPES if t != ctype)
        if new_val == 0 and not others_on:
            await query.answer("باید حداقل یک نوع محتوا فعال بماند.", show_alert=True)
        else:
            update_group_settings(chat_id, **{col: new_val})
            await query.answer("بروزرسانی شد ✅")
        await _show_content_menu(query, chat_id)

    elif data == "gset_send_now":
        await query.answer("در حال ارسال...")
        await _send_random_content(context, chat_id)

    elif data == "gset_quiet_menu":
        await query.answer()
        await _show_quiet_menu(query, chat_id)

    elif data == "gset_quiet_toggle":
        settings = get_group_settings(chat_id)
        if settings["quiet_start_hour"] is not None and settings["quiet_start_hour"] >= 0:
            update_group_settings(chat_id, quiet_start_hour=-1, quiet_end_hour=-1)
        else:
            update_group_settings(chat_id, quiet_start_hour=DEFAULT_QUIET_START, quiet_end_hour=DEFAULT_QUIET_END)
        await query.answer("بروزرسانی شد ✅")
        await _show_quiet_menu(query, chat_id)

    elif data == "gset_quiet_start_menu":
        await query.answer()
        await query.edit_message_text("🌙 ساعت شروع سکوت را انتخاب کنید:", reply_markup=_hour_grid("gset_qs_", back="gset_quiet_menu"))

    elif data == "gset_quiet_end_menu":
        await query.answer()
        await query.edit_message_text("🌙 ساعت پایان سکوت را انتخاب کنید:", reply_markup=_hour_grid("gset_qe_", back="gset_quiet_menu"))

    elif data.startswith("gset_qs_"):
        hour = int(data.replace("gset_qs_", ""))
        update_group_settings(chat_id, quiet_start_hour=hour)
        await query.answer("ذخیره شد ✅")
        await _show_quiet_menu(query, chat_id)

    elif data.startswith("gset_qe_"):
        hour = int(data.replace("gset_qe_", ""))
        update_group_settings(chat_id, quiet_end_hour=hour)
        await query.answer("ذخیره شد ✅")
        await _show_quiet_menu(query, chat_id)

    elif data == "gset_welcome_toggle":
        settings = get_group_settings(chat_id)
        update_group_settings(chat_id, welcome_enabled=0 if settings["welcome_enabled"] else 1)
        await query.answer("بروزرسانی شد ✅")
        await _show_main_menu(query, chat_id)

    elif data == "gset_service_toggle":
        settings = get_group_settings(chat_id)
        update_group_settings(chat_id, delete_service_messages=0 if settings["delete_service_messages"] else 1)
        await query.answer("بروزرسانی شد ✅")
        await _show_main_menu(query, chat_id)

    elif data == "gset_links_toggle":
        settings = get_group_settings(chat_id)
        update_group_settings(chat_id, block_links=0 if settings["block_links"] else 1)
        await query.answer("بروزرسانی شد ✅")
        await _show_main_menu(query, chat_id)

    else:
        await query.answer()


def _hour_grid(prefix: str, back: str = "gset_main", per_row: int = 6):
    buttons = []
    row = []
    for h in range(24):
        row.append(InlineKeyboardButton(str(h), callback_data=f"{prefix}{h}"))
        if len(row) == per_row:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data=back)])
    return InlineKeyboardMarkup(buttons)


async def _show_content_menu(query, chat_id):
    settings = get_group_settings(chat_id)
    buttons = []
    for t in CONTENT_TYPES:
        mark = "✅" if settings[f"content_{t}"] else "⬜️"
        buttons.append([InlineKeyboardButton(f"{mark} {CONTENT_TYPE_LABELS[t]}", callback_data=f"gset_content_toggle_{t}")])
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="gset_main")])
    await query.edit_message_text(
        "📚 پست خودکار از بین کدام نوع محتواها به‌صورت تصادفی انتخاب کند؟\n"
        "(روی هرکدام بزنید تا روشن/خاموش شود)",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def _show_quiet_menu(query, chat_id):
    settings = get_group_settings(chat_id)
    active = settings["quiet_start_hour"] is not None and settings["quiet_start_hour"] >= 0
    buttons = [
        [InlineKeyboardButton(f"حالت سکوت: {_on_off(active)}", callback_data="gset_quiet_toggle")],
    ]
    if active:
        buttons.append([
            InlineKeyboardButton(f"🕐 شروع: {settings['quiet_start_hour']}", callback_data="gset_quiet_start_menu"),
            InlineKeyboardButton(f"🕐 پایان: {settings['quiet_end_hour']}", callback_data="gset_quiet_end_menu"),
        ])
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="gset_main")])
    await query.edit_message_text(
        "🌙 در بازه‌ی سکوت، پست خودکار ارسال نمی‌شود (مثلاً برای جلوگیری از نوتیفیکیشن نیمه‌شب).",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def _show_leaderboard(query, chat_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT username, score FROM quiz_scores WHERE chat_id = ? ORDER BY score DESC LIMIT 10",
        (chat_id,),
    ).fetchall()
    conn.close()

    if not rows:
        text = "🏆 هنوز هیچ امتیازی در مسابقه‌ی این گروه ثبت نشده است.\nبا دستور /quiz مسابقه را شروع کنید!"
    else:
        medals = ["🥇", "🥈", "🥉"]
        lines = ["🏆 *رتبه‌بندی مسابقه‌ی این گروه*\n"]
        for i, r in enumerate(rows):
            prefix = medals[i] if i < 3 else f"{i + 1}."
            lines.append(f"{prefix} {r['username'] or 'کاربر ناشناس'} — {r['score']} امتیاز")
        text = "\n".join(lines)

    await query.edit_message_text(text, reply_markup=_back_button(), parse_mode="Markdown")


# =====================================================================
# دستور تنظیم متن خوش‌آمدگویی
# =====================================================================

async def set_welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == ChatType.PRIVATE:
        await update.message.reply_text("این دستور فقط داخل گروه‌ها کاربرد دارد.")
        return
    if not await is_group_admin(update):
        await update.message.reply_text("فقط ادمین‌های گروه می‌توانند این تنظیم را تغییر دهند.")
        return

    parts = update.message.text.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text(
            "فرمت درست:\n"
            "/setwelcome متن خوش‌آمدگویی\n\n"
            "می‌توانید از {name} برای نام کاربر جدید استفاده کنید. مثال:\n"
            "/setwelcome سلام {name}! خوش اومدی 🌹\n\n"
            f"متن پیش‌فرض فعلی:\n{DEFAULT_WELCOME_TEXT}"
        )
        return

    welcome_text = parts[1].strip()
    update_group_settings(update.effective_chat.id, welcome_text=welcome_text, welcome_enabled=1)
    await update.message.reply_text(
        "✅ متن خوش‌آمدگویی ذخیره شد و فعال گردید. پیش‌نمایش:\n\n"
        + welcome_text.replace("{name}", update.effective_user.first_name)
    )


# =====================================================================
# ارسال محتوای تصادفی (هم برای دکمه‌ی «ارسال الان» و هم برای جاب زمان‌بندی‌شده)
# =====================================================================

async def _format_ayah_post():
    surahs = await get_surah_list()
    surah = random.choice(surahs)
    ayah_num = random.randint(1, surah["numberOfAyahs"])
    data = await get_ayah(surah["number"], ayah_num)
    if not data or not data.get("arabic"):
        return None, None
    text = f"📖 {surah['name']} - آیه {ayah_num}\n\n{data['arabic']}\n\n🔹 {data['translation']}"
    return text, None


def _format_nahj_post(row):
    category, number = row["category"], row["number"]
    item_label = NAHJ_ITEM_LABELS.get(category, "")
    cat_label = NAHJ_MENU_LABELS.get(category, "🕌 نهج‌البلاغه")
    title_suffix = f" — {row['title']}" if row["title"] else ""
    body = row["translation_text"] or ""
    preview = body if len(body) <= 500 else body[:500].rstrip() + "…"
    text = f"{cat_label} — {item_label} {number}{title_suffix}\n\n{preview}"

    truncated = len(body) > 500
    has_arabic = bool(row["arabic_text"])
    has_tafsir = bool(row["tafsir_text"])
    needs_full_view = truncated or has_arabic or has_tafsir

    markup = None
    if needs_full_view:
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📖 مشاهده کامل", callback_data=f"nahjitem_{category}_{number}")]]
        )
    return text, markup


def _format_mafatih_post(row):
    cat_label = MAFATIH_CATEGORY_FA.get(row["category"], "🤲 مفاتیح‌الجنان")
    translation = row["translation_text"] or ""
    arabic = row["arabic_text"] or ""
    tafsir = row["tafsir_text"] or ""
    body = translation or arabic
    preview = body if len(body) <= 500 else body[:500].rstrip() + "…"
    text = f"{cat_label} — {row['title']}\n\n{preview}"

    truncated = len(body) > 500
    hidden_arabic = bool(translation) and bool(arabic)
    has_tafsir = bool(tafsir)
    needs_full_view = truncated or hidden_arabic or has_tafsir

    markup = None
    if needs_full_view:
        identifier = row["slug"] if row["slug"] else row["id"]
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📖 مشاهده کامل", callback_data=f"mafitem_{identifier}")]]
        )
    return text, markup


async def _build_random_content(enabled_types):
    random.shuffle(enabled_types)
    for content_type in enabled_types:
        text, markup = None, None
        if content_type == "hadith":
            row = get_random_hadith()
            if row:
                text = format_hadith(row)
        elif content_type == "ayah":
            text, markup = await _format_ayah_post()
        elif content_type == "nahj":
            row = get_random_nahj_item()
            if row:
                text, markup = _format_nahj_post(row)
        elif content_type == "mafatih":
            row = get_random_mafatih_item()
            if row:
                text, markup = _format_mafatih_post(row)
        if text:
            return text, markup
    return None, None


async def _send_random_content(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    settings = get_group_settings(chat_id)
    enabled_types = [t for t in CONTENT_TYPES if settings[f"content_{t}"]]
    if not enabled_types:
        enabled_types = ["hadith"]
    text, markup = await _build_random_content(enabled_types)
    if not text:
        text = "هنوز محتوایی برای ارسال ثبت نشده است."
        markup = None
    await context.bot.send_message(chat_id, text, reply_markup=markup)


async def group_send_now_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _send_random_content(context, update.effective_chat.id)


# =====================================================================
# جاب زمان‌بندی‌شده‌ی پست خودکار
# =====================================================================

def _in_quiet_hours(hour: int, start, end) -> bool:
    if start is None or end is None or start < 0 or end < 0 or start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def _ensure_daily_post_log_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_post_log (
            chat_id INTEGER PRIMARY KEY,
            last_sent_key TEXT
        )
        """
    )


def _get_last_sent_key(conn, chat_id):
    row = conn.execute(
        "SELECT last_sent_key FROM daily_post_log WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()
    return row["last_sent_key"] if row else None


def _set_last_sent_key(conn, chat_id, key):
    conn.execute(
        """
        INSERT INTO daily_post_log (chat_id, last_sent_key) VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET last_sent_key = excluded.last_sent_key
        """,
        (chat_id, key),
    )
    conn.commit()


async def daily_post_job(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now()

    conn = get_connection()
    _ensure_daily_post_log_table(conn)

    groups = get_all_active_daily_groups()
    for g in groups:
        interval = g["post_interval_hours"] or 1
        anchor = g["daily_post_hour"] if g["daily_post_hour"] is not None else 0
        if (now.hour - anchor) % interval != 0:
            continue

        if _in_quiet_hours(now.hour, g["quiet_start_hour"], g["quiet_end_hour"]):
            continue

        send_key = now.strftime("%Y-%m-%d-%H")
        if _get_last_sent_key(conn, g["chat_id"]) == send_key:
            continue

        enabled_types = [t for t in CONTENT_TYPES if g[f"content_{t}"]]
        if not enabled_types:
            continue

        text, markup = await _build_random_content(enabled_types)
        if not text:
            continue

        try:
            await context.bot.send_message(g["chat_id"], text, reply_markup=markup)
            _set_last_sent_key(conn, g["chat_id"], send_key)
        except Exception:
            pass

    conn.close()


# =====================================================================
# مدیریت اعضای جدید/خارج‌شده
# =====================================================================

async def member_update_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    chat_id = update.effective_chat.id
    settings = get_group_settings(chat_id)

    if msg.new_chat_members:
        for member in msg.new_chat_members:
            if member.id == context.bot.id:
                await msg.reply_text(
                    "سلام 🌙\n"
                    "از اضافه کردن من به این گروه خوشحالم!\n\n"
                    "برای دیدن قابلیت‌های گروهی از دستور /groupsettings استفاده کنید "
                    "(فقط ادمین‌ها).\n"
                    "برای جستجوی سریع، کافیست بنویسید:\n"
                    "`@نام_ربات صبر` یا `@نام_ربات 2:255`\n\n"
                    "همچنین می‌توانید در چت خصوصی من /start را بزنید تا از منوی کامل استفاده کنید.",
                    parse_mode="Markdown",
                )
                continue
            if settings["welcome_enabled"]:
                welcome_text = settings["welcome_text"] or DEFAULT_WELCOME_TEXT
                try:
                    await context.bot.send_message(
                        chat_id, welcome_text.replace("{name}", member.first_name or member.full_name)
                    )
                except Exception:
                    pass

    if settings["delete_service_messages"] and (msg.new_chat_members or msg.left_chat_member):
        try:
            await msg.delete()
        except Exception:
            pass


# =====================================================================
# ردیابی گروه‌ها و آمار
# =====================================================================

_ACTIVE_STATUSES = ("member", "administrator", "creator", "restricted")


async def bot_chat_member_update_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if not result:
        return

    chat = result.chat
    new_status = result.new_chat_member.status
    is_active = new_status in _ACTIVE_STATUSES

    member_count = None
    if is_active and chat.type in ("group", "supergroup"):
        try:
            member_count = await context.bot.get_chat_member_count(chat.id)
        except Exception:
            member_count = None

    upsert_chat(
        chat.id, chat.type, title=chat.title, username=chat.username,
        member_count=member_count, is_active=is_active,
    )


async def track_user_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or user.is_bot:
        return
    register_user(user.id, user.username)
    await dispatch_event(EVENT_DAILY_LOGIN, user.id)


async def bot_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    total_users = count_users()
    groups = get_active_groups()

    lines = [
        "📊 *آمار ربات* (فقط ادمین‌ها این را می‌بینند)\n",
        f"👤 کاربران چت خصوصی: {total_users}",
        f"👥 گروه‌هایی که ربات الان توشونه: {len(groups)}",
    ]

    MAX_LISTED = 40
    if groups:
        lines.append("\n*لیست گروه‌ها:*")
        for g in groups[:MAX_LISTED]:
            title = g["title"] or "(بدون نام)"
            username_part = f" (@{g['username']})" if g["username"] else ""
            count_part = f" — {g['member_count']} عضو" if g["member_count"] else ""
            lines.append(f"• {title}{username_part}{count_part}")
        if len(groups) > MAX_LISTED:
            lines.append(f"\n… و {len(groups) - MAX_LISTED} گروه دیگر")

    text = "\n".join(lines)
    try:
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(text)


# =====================================================================
# ضداسپم لینک
# =====================================================================

_LINK_PATTERN = re.compile(r"(https?://|t\.me/|telegram\.me/|www\.)\S+", re.IGNORECASE)


async def _delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    try:
        await context.bot.delete_message(job.chat_id, job.data)
    except Exception:
        pass


async def link_guard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    if update.effective_chat.type == ChatType.PRIVATE:
        return

    settings = get_group_settings(update.effective_chat.id)
    if not settings["block_links"]:
        return

    if not _LINK_PATTERN.search(msg.text):
        return

    try:
        member = await update.effective_chat.get_member(update.effective_user.id)
        if member.status in ("administrator", "creator"):
            return
    except Exception:
        return

    try:
        await msg.delete()
        warn = await context.bot.send_message(
            update.effective_chat.id,
            f"🔗 {update.effective_user.first_name} عزیز، ارسال لینک در این گروه مجاز نیست.",
        )
        if context.job_queue:
            context.job_queue.run_once(
                _delete_message_job, when=15,
                chat_id=update.effective_chat.id, data=warn.message_id,
            )
    except Exception:
        pass


# ==========================================
# اصلاح دستیِ audio_file_id یک دعا
# ==========================================

_PENDING_MAFATIH_AUDIO: dict[tuple[int, int], str] = {}


async def set_mafatih_audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه‌ی این دستور را ندارید.")
        return

    parts = update.message.text.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text(
            "فرمت درست: /setmafaudio شناسه\n"
            "مثال: /setmafaudio kumayl\n"
            "(شناسه همان چیزی است که در دکمه‌ی منو بعد از mafitem_ می‌آید، یا اگر "
            "slug ندارد، همان id عددی‌اش در دیتابیس است)"
        )
        return

    identifier = parts[1].strip()
    item = get_mafatih_item_flexible(identifier)
    if not item:
        await update.message.reply_text(f"چیزی با شناسه‌ی «{identifier}» پیدا نشد.")
        return

    _PENDING_MAFATIH_AUDIO[(update.effective_user.id, update.effective_chat.id)] = identifier
    await update.message.reply_text(
        f"✅ الان فایل صوتیِ «{item['title']}» رو همین‌جا به‌عنوان یک فایل صوتی (audio) بفرستید "
        f"(نه ویس/voice، ترجیحاً audio که عنوان و خواننده هم نگه می‌دارد)."
    )


async def mafatih_audio_upload_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = (update.effective_user.id, update.effective_chat.id)
    identifier = _PENDING_MAFATIH_AUDIO.get(key)
    if not identifier:
        return

    message = update.message
    file_id = None
    if message.audio:
        file_id = message.audio.file_id
    elif message.voice:
        file_id = message.voice.file_id

    if not file_id:
        return

    item = get_mafatih_item_flexible(identifier)
    if not item:
        _PENDING_MAFATIH_AUDIO.pop(key, None)
        await message.reply_text("❌ این دعا دیگر پیدا نشد (شاید حذف شده). عملیات لغو شد.")
        return

    update_mafatih_audio(item["id"], file_id)
    _PENDING_MAFATIH_AUDIO.pop(key, None)
    await message.reply_text(f"✅ فایل صوتی «{item['title']}» با موفقیت به‌روزرسانی شد.")