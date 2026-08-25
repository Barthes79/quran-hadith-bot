# -*- coding: utf-8 -*-
"""
هندلرهای متنی/callback مربوط به شخصیت همراه (کبوتر): صلوات، کارتِ وضعیت،
برداشت، ارتقا، تغییرِ اسم.

نسخه‌ی نهایی با پیام پویا برای سطح بعدی.
"""

import re
import logging

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
    get_pigeon_feature_progress,
    PIGEON_RENAME_COST,
)
from text_utils import to_persian_digits

logger = logging.getLogger(__name__)

# «اسم کبوترم رستم» -> گروه ۱ = "رستم"
_RENAME_PATTERN = re.compile(r"^اسم\s+کبوترم\s+(.+)$")

_STATUS_TRIGGERS = ("کبوترم", "پروفایل کبوترم", "وضعیت کبوترم")
_RENAME_CANCEL_WORDS = {"بیخیال", "انصراف", "لغو"}

HARVEST_CALLBACK_PREFIX = "pigeon_harvest"
LEVELUP_CALLBACK_PREFIX = "pigeon_levelup"
RENAME_CALLBACK_PREFIX = "pigeon_rename"

_CALLBACK_PATTERN = re.compile(r"^(pigeon_harvest|pigeon_levelup|pigeon_rename):(\d+)$")

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
    if query.from_user.id != owner_id:
        await query.answer("🚫 این پنل مال شما نیست؛ خودت با «کبوترم» پنل خودتو باز کن.", show_alert=True)
        return True
    return False


def _check_feature_level(user_id: int) -> tuple[bool, dict]:
    progress = get_pigeon_feature_progress(user_id)
    is_allowed = progress["level"] >= 3
    logger.info(f"[DEBUG] user_id={user_id}, level={progress['level']}, is_allowed={is_allowed}, remaining={progress['remaining']}")
    return is_allowed, progress


async def _reply_feature_locked(update: Update, progress: dict) -> None:
    """پیام قفل بودن قابلیت‌های کبوتر رو با توضیح کامل و پویا می‌فرسته."""
    remaining = progress["remaining"]
    current_level = progress["level"]
    next_level = current_level + 1
    # اگر سطح فعلی ۰ باشه، سطح بعدی ۱ هست؛ اگر ۱ باشه، سطح بعدی ۲ و ...
    
    if remaining > 0:
        msg = (
            f"🔒 قابلیت‌های کبوتر (شامل «کبوترم») فقط برای کاربرانی که به سطح ۳ "
            f"«پیشرفت قابلیت‌ها» رسیده‌اند فعال است.\n\n"
            f"شما هم‌اکنون در سطح {_code(to_persian_digits(current_level))} هستید.\n"
            f"برای رسیدن به سطح بعدی (سطح {_code(to_persian_digits(next_level))})، باید "
            f"{_code(to_persian_digits(remaining))} صلوات کامل دیگه بفرستید.\n"
            f"(اللهم صل علی محمد و آل محمد)\n\n"
            f"هر بار که این عبارت رو کامل بنویسید، یک بار به شمارش اضافه می‌شود."
        )
    else:
        msg = (
            f"🔒 قابلیت‌های کبوتر (شامل «کبوترم») فقط برای کاربرانی که به سطح ۳ "
            f"«پیشرفت قابلیت‌ها» رسیده‌اند فعال است.\n\n"
            f"شما هم‌اکنون در سطح {_code(to_persian_digits(current_level))} هستید.\n"
            f"برای فعال شدن این قابلیت، باید به سطح ۳ برسید."
        )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    logger.info("[DEBUG] Locked message sent.")


async def pigeon_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    if not update.message:
        logger.warning("[DEBUG] No message in update")
        return False

    user = update.effective_user
    chat = update.effective_chat
    normalized = text.strip()
    is_private = chat.type == "private"

    logger.info(f"[DEBUG] pigeon_text_handler called: user_id={user.id}, text='{text}', normalized='{normalized}', is_private={is_private}")

    # ============================================================
    # حالت تغییر نام (دکمه‌ی «✏️ تغییر نام»)
    # ============================================================
    if context.user_data.get(_AWAITING_RENAME_KEY):
        logger.info("[DEBUG] In rename mode")
        if normalized in _RENAME_CANCEL_WORDS:
            context.user_data[_AWAITING_RENAME_KEY] = False
            await update.message.reply_text("باشه، تغییرِ اسم لغو شد.")
            return True

        is_allowed, progress = _check_feature_level(user.id)
        if not is_allowed:
            context.user_data[_AWAITING_RENAME_KEY] = False
            await _reply_feature_locked(update, progress)
            return True

        register_user(user.id, user.username)
        result_text = set_pigeon_name(user.id, normalized)
        if result_text.startswith("🕊️") or result_text.startswith("💰"):
            context.user_data[_AWAITING_RENAME_KEY] = False
        await update.message.reply_text(result_text)
        return True

    # ============================================================
    # عبارت کامل صلوات → همیشه کار می‌کنه (برای رسیدن به سطح ۳)
    # ============================================================
    if is_full_salavat_phrase(normalized):
        if not is_private:
            logger.info("[DEBUG] Salavat phrase in group, skipping")
            return False
        logger.info("[DEBUG] Full salavat phrase detected, awarding points")
        register_user(user.id, user.username)
        await update.message.reply_text(handle_salavat_points(user.id), parse_mode=ParseMode.MARKDOWN)
        return True

    # ============================================================
    # از اینجا به بعد، همه‌ی قابلیت‌های کبوتر نیاز به سطح ۳ دارند
    # ============================================================
    is_allowed, progress = _check_feature_level(user.id)

    # اگر کاربر «کبوترم» نوشته
    if normalized in _STATUS_TRIGGERS:
        logger.info(f"[DEBUG] User wrote status trigger: '{normalized}', is_allowed={is_allowed}")
        if not is_allowed:
            await _reply_feature_locked(update, progress)
            return True
        register_user(user.id, user.username)
        status_text = build_pigeon_status_text(user.id, _display_name(user))
        await update.message.reply_text(
            status_text, reply_markup=_status_keyboard(user.id), parse_mode=ParseMode.MARKDOWN
        )
        return True

    # اگر کاربر «اسم کبوترم ...» نوشته
    rename_match = _RENAME_PATTERN.match(normalized)
    if rename_match:
        logger.info(f"[DEBUG] Rename pattern matched: '{rename_match.group(1)}', is_allowed={is_allowed}")
        if not is_allowed:
            await _reply_feature_locked(update, progress)
            return True
        register_user(user.id, user.username)
        await update.message.reply_text(set_pigeon_name(user.id, rename_match.group(1)))
        return True

    # اگر کاربر اسم سفارشی کبوتر رو نوشته
    pigeon_name = get_pigeon_name(user.id)
    if normalized == pigeon_name:
        logger.info(f"[DEBUG] Custom pigeon name matched: '{pigeon_name}', is_allowed={is_allowed}")
        if not is_allowed:
            await _reply_feature_locked(update, progress)
            return True
        register_user(user.id, user.username)
        status_text = build_pigeon_status_text(user.id, _display_name(user))
        await update.message.reply_text(
            status_text, reply_markup=_status_keyboard(user.id), parse_mode=ParseMode.MARKDOWN
        )
        return True

    logger.info("[DEBUG] No pigeon trigger matched, returning False")
    return False


async def pigeon_harvest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    is_allowed, _ = _check_feature_level(owner_id)
    if not is_allowed:
        await query.answer("🔒 این قابلیت فقط برای کاربران سطح ۳ به بالا فعال است.", show_alert=True)
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

    is_allowed, _ = _check_feature_level(owner_id)
    if not is_allowed:
        await query.answer("🔒 این قابلیت فقط برای کاربران سطح ۳ به بالا فعال است.", show_alert=True)
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

    is_allowed, _ = _check_feature_level(owner_id)
    if not is_allowed:
        await query.answer("🔒 این قابلیت فقط برای کاربران سطح ۳ به بالا فعال است.", show_alert=True)
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


def _code(value) -> str:
    return f"`{value}`"