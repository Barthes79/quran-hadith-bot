# -*- coding: utf-8 -*-
"""
هندلرهای متنی/callback مربوط به شخصیت همراه (کبوتر).

«نذری» و «کبوترم» هم پیوی هم گروه کار می‌کنن. «صلوات» فقط تو پیوی از
همینجا award می‌شه؛ تو گروه، صلوات‌شمار گروهی (handlers/salavat.py) خودش
هم award می‌کنه هم کارت رو می‌فرسته -- تا XP دوبار داده نشه.
"""

import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import register_user
from text_utils import normalize_for_search
from gamification.pigeon import (
    handle_salavat_points,
    handle_nazri,
    build_pigeon_status_text,
    harvest_points,
    level_up_pigeon,
    set_pigeon_name,
)

# «اسم کبوترم رستم» -> گروه ۱ = "رستم"
_RENAME_PATTERN = re.compile(r"^اسم\s+کبوترم\s+(.+)$")

_STATUS_TRIGGERS = ("کبوترم", "پروفایل کبوترم", "وضعیت کبوترم")

HARVEST_CALLBACK_DATA = "pigeon_harvest"
LEVELUP_CALLBACK_DATA = "pigeon_levelup"

# باید عین کامل عبارت صلوات نوشته بشه، نه فقط کلمه‌ی «صلوات». از
# normalize_for_search استفاده می‌کنیم تا «آل»/«ال»، فاصله‌های اضافه، و
# تفاوت‌های ظاهری عربی/فارسی (که تو کیبورد موبایل رایجه) مشکلی ایجاد
# نکنن؛ ولی همچنان باید عبارت *کامل* باشه، نه بخشی از یه پیام بزرگ‌تر.
_SALAVAT_PHRASE_NORMALIZED = normalize_for_search("اللهم صل علی محمد و آل محمد")


def _is_full_salavat_phrase(text: str) -> bool:
    return normalize_for_search(text) == _SALAVAT_PHRASE_NORMALIZED


def _display_name(user) -> str:
    return user.first_name or user.full_name or (f"@{user.username}" if user.username else "کاربر")


def _status_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 برداشت صلوات پوینت", callback_data=HARVEST_CALLBACK_DATA)],
        [InlineKeyboardButton("⬆️ ارتقا", callback_data=LEVELUP_CALLBACK_DATA)],
    ])


async def pigeon_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """
    اگه متنِ پیام یکی از کلیدواژه‌های کبوتر («صلوات»، «نذری»، «کبوترم»، یا
    «اسم کبوترم ...») باشه، پاسخ مناسب رو می‌فرسته و True برمی‌گردونه تا
    general_text_handler دیگه مسیرهای بعدی (آیه/سرچ) رو امتحان نکنه.
    اگه هیچ‌کدوم نبود، هیچ کاری نمی‌کنه و False برمی‌گردونه.
    """
    if not update.message:
        return False

    user = update.effective_user
    chat = update.effective_chat
    normalized = text.strip()
    is_private = chat.type == "private"

    if _is_full_salavat_phrase(normalized):
        if not is_private:
            return False
        register_user(user.id, user.username)
        await update.message.reply_text(handle_salavat_points(user.id))
        return True

    if normalized == "نذری":
        register_user(user.id, user.username)
        await update.message.reply_text(handle_nazri(user.id))
        return True

    if normalized in _STATUS_TRIGGERS:
        register_user(user.id, user.username)
        status_text = build_pigeon_status_text(user.id, _display_name(user))
        await update.message.reply_text(status_text, reply_markup=_status_keyboard())
        return True

    rename_match = _RENAME_PATTERN.match(normalized)
    if rename_match:
        register_user(user.id, user.username)
        await update.message.reply_text(set_pigeon_name(user.id, rename_match.group(1)))
        return True

    return False


async def pigeon_harvest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌ی «📥 برداشت صلوات پوینت»."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user = update.effective_user
    harvest_message = harvest_points(user.id)
    status_text = build_pigeon_status_text(user.id, _display_name(user))
    combined = f"{harvest_message}\n\n{status_text}"

    try:
        await query.edit_message_text(combined, reply_markup=_status_keyboard())
    except Exception:
        await query.message.reply_text(harvest_message)


async def pigeon_levelup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌ی «⬆️ ارتقا» (ارتقا سطح یا ارتقا مقام، بسته به وضعیت فعلی)."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user = update.effective_user
    levelup_message = level_up_pigeon(user.id)
    status_text = build_pigeon_status_text(user.id, _display_name(user))
    combined = f"{levelup_message}\n\n{status_text}"

    try:
        await query.edit_message_text(combined, reply_markup=_status_keyboard())
    except Exception:
        await query.message.reply_text(levelup_message)
