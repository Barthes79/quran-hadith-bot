# -*- coding: utf-8 -*-
"""
هندلرهای متنی/callback مربوط به شخصیت همراه (کبوتر): صلوات، کارتِ وضعیت،
برداشت، ارتقا، تغییرِ اسم.

«کبوترم» هم پیوی هم گروه کار می‌کنه. «صلوات» فقط تو پیوی از همینجا
award می‌شه؛ تو گروه، صلوات‌شمار گروهی (handlers/salavat.py) خودش هم
award می‌کنه هم کارت رو می‌فرسته -- تا XP دوبار داده نشه.

توجه: «نذری» و «یخچالم» دیگه اینجا نیستن؛ رفتن تو handlers/fridge.py.
"""

import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from database import register_user
from gamification.pigeon import (
    handle_salavat_points,
    build_pigeon_status_text,
    harvest_points,
    level_up_pigeon,
    set_pigeon_name,
    is_full_salavat_phrase,
    get_pigeon_name,
    PIGEON_RENAME_COST,
)
from text_utils import to_persian_digits

# «اسم کبوترم رستم» -> گروه ۱ = "رستم"
_RENAME_PATTERN = re.compile(r"^اسم\s+کبوترم\s+(.+)$")

_STATUS_TRIGGERS = ("کبوترم", "پروفایل کبوترم", "وضعیت کبوترم")
_RENAME_CANCEL_WORDS = {"بیخیال", "انصراف", "لغو"}

HARVEST_CALLBACK_PREFIX = "pigeon_harvest"
LEVELUP_CALLBACK_PREFIX = "pigeon_levelup"
RENAME_CALLBACK_PREFIX = "pigeon_rename"

# owner_id همیشه تو خودِ callback_data قایم می‌شه (نه فقط تو حافظه‌ی
# چت)، چون تو گروه ممکنه چندین نفر همزمان پنل‌های جدا داشته باشن و پیام
# ربات هم بین ری‌استارت‌ها می‌مونه؛ این تنها راهِ قابل‌اعتماد برای اینه که
# بفهمیم این پنل مال کدوم کاربره.
_CALLBACK_PATTERN = re.compile(r"^(pigeon_harvest|pigeon_levelup|pigeon_rename):(\d+)$")

# کلیدِ context.user_data برای اینکه بدونیم کاربر تازه دکمه‌ی «✏️ تغییر
# نام» رو زده و پیامِ بعدیش باید به‌عنوانِ اسمِ جدید تفسیر بشه (نه صلوات/
# «کبوترم»/چیزِ دیگه). این حافظه فقط تو RAMه (بین ری‌استارت‌های ربات
# پاک می‌شه)، که برای یه پرامپتِ کوتاه‌مدت مشکلی نداره.
_AWAITING_RENAME_KEY = "pigeon_awaiting_rename"


def _display_name(user) -> str:
    return user.first_name or user.full_name or (f"@{user.username}" if user.username else "کاربر")


def _status_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 برداشت صلوات پوینت", callback_data=f"{HARVEST_CALLBACK_PREFIX}:{owner_id}")],
        [InlineKeyboardButton("⬆️ ارتقا", callback_data=f"{LEVELUP_CALLBACK_PREFIX}:{owner_id}")],
        [InlineKeyboardButton("✏️ تغییر نام", callback_data=f"{RENAME_CALLBACK_PREFIX}:{owner_id}")],
    ])


async def reject_if_not_owner(query, owner_id: int) -> bool:
    """اگه کلیک‌کننده صاحبِ این پنل نباشه، یه alert نشونش می‌ده و True
    برمی‌گردونه (یعنی باید متوقف بشیم). صاحبِ پنل با False ادامه می‌ده."""
    if query.from_user.id != owner_id:
        await query.answer("🚫 این پنل مال شما نیست؛ خودت با «کبوترم» پنل خودتو باز کن.", show_alert=True)
        return True
    return False


async def pigeon_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """
    اگه متنِ پیام یکی از کلیدواژه‌های کبوتر («صلوات کامل»، «کبوترم»، یا
    «اسم کبوترم ...») باشه، پاسخ مناسب رو می‌فرسته و True برمی‌گردونه تا
    general_text_handler دیگه مسیرهای بعدی (آیه/سرچ) رو امتحان نکنه.
    اگه هیچ‌کدوم نبود، هیچ کاری نمی‌کنه و False برمی‌گردونه.

    توجه: پیام‌هایی که عدد توشونه با parse_mode=Markdown فرستاده می‌شن تا
    بک‌تیک‌های دورِ عدد (تو gamification/pigeon.py) به‌شکل کدِ آبیِ
    قابل‌کپی تلگرام نمایش داده بشن، نه به‌شکل خام با علامتِ ` .
    """
    if not update.message:
        return False

    user = update.effective_user
    chat = update.effective_chat
    normalized = text.strip()
    is_private = chat.type == "private"

    # اگه کاربر تازه دکمه‌ی «✏️ تغییر نام» رو زده، این پیام (هرچی باشه،
    # حتی اگه شبیهِ «کبوترم» یا صلوات باشه) به‌عنوانِ اسمِ جدید تفسیر
    # می‌شه -- نه هیچ مسیرِ دیگه‌ای.
    if context.user_data.get(_AWAITING_RENAME_KEY):
        if normalized in _RENAME_CANCEL_WORDS:
            context.user_data[_AWAITING_RENAME_KEY] = False
            await update.message.reply_text("باشه، تغییرِ اسم لغو شد.")
            return True
        register_user(user.id, user.username)
        result_text = set_pigeon_name(user.id, normalized)
        # فقط با موفقیت یا کمبودِ موجودی از حالتِ انتظار خارج می‌شیم؛
        # اگه فقط فرمتِ اسم غلط بود (طول/کاراکترهای غیرمجاز)، بذار بدونِ
        # نیاز به زدنِ دوبارهٔ دکمه، همینجا دوباره امتحان کنه.
        if result_text.startswith("🕊️") or result_text.startswith("💰"):
            context.user_data[_AWAITING_RENAME_KEY] = False
        await update.message.reply_text(result_text)
        return True

    if is_full_salavat_phrase(normalized):
        if not is_private:
            return False
        register_user(user.id, user.username)
        await update.message.reply_text(handle_salavat_points(user.id), parse_mode=ParseMode.MARKDOWN)
        return True

    if normalized in _STATUS_TRIGGERS:
        register_user(user.id, user.username)
        status_text = build_pigeon_status_text(user.id, _display_name(user))
        await update.message.reply_text(
            status_text, reply_markup=_status_keyboard(user.id), parse_mode=ParseMode.MARKDOWN
        )
        return True

    # چک کردن اسم سفارشی کبوتر (کاربر می‌تونه با نوشتن اسم کبوترش، پنل رو باز کنه)
    # این چک باید بعد از _STATUS_TRIGGERS باشه تا «کبوترم» اولویت داشته باشه،
    # و قبل از _RENAME_PATTERN باشه تا با «اسم کبوترم ...» تداخل نکنه.
    if not context.user_data.get(_AWAITING_RENAME_KEY):
        pigeon_name = get_pigeon_name(user.id)
        if normalized == pigeon_name:
            register_user(user.id, user.username)
            status_text = build_pigeon_status_text(user.id, _display_name(user))
            await update.message.reply_text(
                status_text, reply_markup=_status_keyboard(user.id), parse_mode=ParseMode.MARKDOWN
            )
            return True

    rename_match = _RENAME_PATTERN.match(normalized)
    if rename_match:
        register_user(user.id, user.username)
        await update.message.reply_text(set_pigeon_name(user.id, rename_match.group(1)))
        return True

    return False


async def pigeon_harvest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌ی «📥 برداشت صلوات پوینت» -- فقط صاحبِ پنل می‌تونه بزنه."""
    query = update.callback_query
    if not query:
        return

    match = _CALLBACK_PATTERN.match(query.data or "")
    if not match:
        await query.answer()
        return
    owner_id = int(match.group(2))

    if await reject_if_not_owner(query, owner_id):
        return
    await query.answer()

    harvest_message = harvest_points(owner_id)
    status_text = build_pigeon_status_text(owner_id, _display_name(query.from_user))
    combined = f"{harvest_message}\n\n{status_text}"

    try:
        await query.edit_message_text(combined, reply_markup=_status_keyboard(owner_id), parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await query.message.reply_text(harvest_message, parse_mode=ParseMode.MARKDOWN)


async def pigeon_levelup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌ی «⬆️ ارتقا» -- فقط صاحبِ پنل می‌تونه بزنه."""
    query = update.callback_query
    if not query:
        return

    match = _CALLBACK_PATTERN.match(query.data or "")
    if not match:
        await query.answer()
        return
    owner_id = int(match.group(2))

    if await reject_if_not_owner(query, owner_id):
        return
    await query.answer()

    levelup_message = level_up_pigeon(owner_id)
    status_text = build_pigeon_status_text(owner_id, _display_name(query.from_user))
    combined = f"{levelup_message}\n\n{status_text}"

    try:
        await query.edit_message_text(combined, reply_markup=_status_keyboard(owner_id), parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await query.message.reply_text(levelup_message, parse_mode=ParseMode.MARKDOWN)


async def pigeon_rename_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌ی «✏️ تغییر نام» -- فقط صاحبِ پنل می‌تونه بزنه. با زدنِ این
    دکمه فقط یه پرامپت می‌فرسته و منتظرِ پیامِ بعدیِ همون کاربر می‌مونه؛
    خرج و اعمالِ اسم تو pigeon_text_handler (بالای همین فایل) انجام
    می‌شه."""
    query = update.callback_query
    if not query:
        return

    match = _CALLBACK_PATTERN.match(query.data or "")
    if not match:
        await query.answer()
        return
    owner_id = int(match.group(2))

    if await reject_if_not_owner(query, owner_id):
        return
    await query.answer()

    context.user_data[_AWAITING_RENAME_KEY] = True
    cost_str = to_persian_digits(PIGEON_RENAME_COST)
    prompt = (
        "✏️ اسمِ جدیدِ کبوترت رو تو یه پیام بنویس.\n"
        "۳ تا ۲۲ حرف، فقط حروف و فاصله (بدون عدد، ایموجی، یا علامتِ نگارشی).\n"
        f"هزینه‌ش {cost_str} صلوات پوینته.\n"
        "برای انصراف، بنویس «بیخیال»."
    )
    await query.message.reply_text(prompt)