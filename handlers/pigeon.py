# -*- coding: utf-8 -*-
"""
هندلرهای متنی/callback مربوط به شخصیت همراه (کبوتر) — فقط در پیوی.

عمداً از گروه‌ها کنار گذاشته شده چون صلوات‌شمار گروهی (handlers/salavat.py)
از قبل روی کلمه‌ی «صلوات» توی گروه‌ها کار می‌کنه (ختم‌ها، پنل شیشه‌ای،
رکوردهای گروهی...)؛ اضافه‌کردن یه پاسخ دومِ کارت‌مانند روی همون پیام، تو
گروه‌های شلوغ صرفاً باعث شلوغی می‌شه. XP هر دو مسیر (گروه و پیوی) از
همون EVENT_SALAVAT_SENT با کول‌داون/سقف مشترک استفاده می‌کنن، پس امکان
گرفتن XP دوبرابر با رفتن بین گروه و پیوی وجود نداره.
"""

import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import register_user
from gamification.pigeon import (
    handle_salavat_points,
    handle_nazri,
    build_pigeon_status_text,
    feed_pigeon_from_fridge,
    set_pigeon_name,
)

# «اسم کبوترم رستم» -> گروه ۱ = "رستم"
_RENAME_PATTERN = re.compile(r"^اسم\s+کبوترم\s+(.+)$")

_STATUS_TRIGGERS = ("کبوترم", "پروفایل کبوترم", "وضعیت کبوترم")

FEED_CALLBACK_DATA = "pigeon_feed"


def _display_name(user) -> str:
    return user.first_name or user.full_name or (f"@{user.username}" if user.username else "کاربر")


def _status_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🍽 به کبوترم غذا بده", callback_data=FEED_CALLBACK_DATA)
    ]])


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
    normalized = text.strip()

    if normalized == "صلوات":
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


async def pigeon_feed_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌ی «🍽 به کبوترم غذا بده» زیر کارت وضعیت."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user = update.effective_user
    feed_message = feed_pigeon_from_fridge(user.id)
    status_text = build_pigeon_status_text(user.id, _display_name(user))
    combined = f"{feed_message}\n\n{status_text}"

    try:
        await query.edit_message_text(combined, reply_markup=_status_keyboard())
    except Exception:
        # اگه متن با پیام قبلی فرقی نداشت (مثلاً یخچال خالی بود و دوباره
        # زده)، تلگرام روی edit خطای "message not modified" می‌ده؛ در این
        # حالت فقط با یه پیام جدید (کوتاه) اطلاع می‌دیم.
        await query.message.reply_text(feed_message)
