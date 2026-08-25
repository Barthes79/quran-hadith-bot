# -*- coding: utf-8 -*-
"""
هندلرهای متنی/callback مربوط به یخچال صلواتی و آیتم‌های نذری.

جریان:
  «نذری» -> پنلِ پیشنهاد (فروش فوری / بده کبوترت بخوره / بندازش تو یخچال)
  «یخچالم» -> پنلِ کامل یخچال (لیست آیتم‌ها + دکمه‌ی فروش/تغذیه/گرم‌کردن
              روی هرکدوم + دکمه‌ی ارتقا سطح یخچال)

owner_id همیشه تو خودِ callback_data قایمه (دقیقاً همون الگوی
handlers/pigeon.py) تا فقط صاحبِ پنل بتونه روی دکمه‌هاش بزنه.

🔒 تغییر جدید: دسترسی به «نذری» فقط برای کاربرانی که به سطح ۱ (۱۰ صلوات کامل)
رسیده‌اند فعال است. کاربران زیر سطح ۱ پیام توضیحی دریافت می‌کنند.
"""

import re
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from database import register_user
from handlers.pigeon import reject_if_not_owner, _display_name
from gamification.fridge import (
    roll_nazri,
    build_offer_text,
    sell_offered_item,
    feed_offered_item,
    store_offered_item,
    build_fridge_text,
    sell_fridge_item,
    feed_fridge_item,
    warm_fridge_item,
    upgrade_fridge,
)
from gamification.pigeon import get_pigeon_feature_progress
from text_utils import to_persian_digits

logger = logging.getLogger(__name__)

_FRIDGE_TRIGGERS = ("یخچالم", "یخچال من", "یخچال صلواتی")

# فرمت callback_data:
#   nzoffer:<action>:<owner_id>:<food_key>:<weight>   -- پنلِ پیشنهاد (هنوز ذخیره نشده)
#   nzitem:<action>:<owner_id>:<item_id>              -- آیتمِ واقعاً تو یخچال
#   nzupgrade:<owner_id>                              -- ارتقای سطح یخچال
_OFFER_PATTERN = re.compile(r"^nzoffer:(sell|feed|store):(\d+):([a-z]+):([\d.]+)$")
_ITEM_PATTERN = re.compile(r"^nzitem:(sell|feed|warm):(\d+):(\d+)$")
_UPGRADE_PATTERN = re.compile(r"^nzupgrade:(\d+)$")


def _offer_keyboard(owner_id: int, food_key: str, weight: float) -> InlineKeyboardMarkup:
    weight_str = f"{weight:.2f}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 فروش نذری", callback_data=f"nzoffer:sell:{owner_id}:{food_key}:{weight_str}")],
        [InlineKeyboardButton("🕊️ بده کبوترت بخوره", callback_data=f"nzoffer:feed:{owner_id}:{food_key}:{weight_str}")],
        [InlineKeyboardButton("❄️ بندازش تو یخچال", callback_data=f"nzoffer:store:{owner_id}:{food_key}:{weight_str}")],
    ])


def _fridge_keyboard(owner_id: int, items: list) -> InlineKeyboardMarkup:
    rows = []
    for it in items:
        item_id = it["id"]
        emoji = "🔥" if it["is_warmed"] else "🧊"
        rows.append([
            InlineKeyboardButton(f"💰 فروش {emoji}", callback_data=f"nzitem:sell:{owner_id}:{item_id}"),
            InlineKeyboardButton("🕊️ تغذیه", callback_data=f"nzitem:feed:{owner_id}:{item_id}"),
        ])
        if not it["is_warmed"]:
            rows.append([InlineKeyboardButton("🔥 گرم کردن", callback_data=f"nzitem:warm:{owner_id}:{item_id}")])
    rows.append([InlineKeyboardButton("⬆️ ارتقا سطح یخچال", callback_data=f"nzupgrade:{owner_id}")])
    return InlineKeyboardMarkup(rows)


def _code(value) -> str:
    return f"`{value}`"


async def _reply_feature_locked(update: Update, progress: dict) -> None:
    """پیام قفل بودن نذری برای کاربران زیر سطح ۱."""
    remaining = progress["remaining"]
    current_level = progress["level"]
    next_level = current_level + 1
    
    if remaining > 0:
        msg = (
            f"🔒 قابلیت «نذری» فقط برای کاربرانی که به سطح ۱ "
            f"«پیشرفت قابلیت‌ها» رسیده‌اند فعال است.\n\n"
            f"شما هم‌اکنون در سطح {_code(to_persian_digits(current_level))} هستید.\n"
            f"برای رسیدن به سطح ۱، باید {_code(to_persian_digits(remaining))} صلوات کامل "
            f"دیگه بفرستید.\n"
            f"(اللهم صل علی محمد و آل محمد)\n\n"
            f"هر بار که این عبارت رو کامل بنویسید، یک بار به شمارش اضافه می‌شود."
        )
    else:
        msg = (
            f"🔒 قابلیت «نذری» فقط برای کاربرانی که به سطح ۱ "
            f"«پیشرفت قابلیت‌ها» رسیده‌اند فعال است.\n\n"
            f"شما هم‌اکنون در سطح {_code(to_persian_digits(current_level))} هستید.\n"
            f"برای فعال شدن این قابلیت، باید به سطح ۱ برسید."
        )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    logger.info("[DEBUG] Fridge locked message sent.")


async def fridge_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """
    اگه پیام «نذری» یا «یخچالم» باشه، پنل مربوطه رو می‌فرسته و True
    برمی‌گردونه؛ وگرنه False (هم پیوی هم گروه فعاله).
    
    🔒 تغییر: «نذری» فقط برای کاربران سطح ۱ به بالا فعال است.
    «یخچالم» بدون قفل و همیشه در دسترس است (برای مشاهده‌ی آیتم‌های موجود).
    """
    if not update.message:
        return False

    user = update.effective_user
    normalized = text.strip()

    # ============================================================
    # «نذری» → نیاز به سطح ۱
    # ============================================================
    if normalized == "نذری":
        register_user(user.id, user.username)
        
        # بررسی سطح کاربر
        progress = get_pigeon_feature_progress(user.id)
        if progress["level"] < 1:
            await _reply_feature_locked(update, progress)
            return True
        
        rolled = roll_nazri(user.id)
        if not rolled["ok"]:
            await update.message.reply_text(rolled["message"], parse_mode=ParseMode.MARKDOWN)
            return True

        item = rolled["item"]
        offer_text = build_offer_text(item)
        keyboard = _offer_keyboard(user.id, item["food_key"], item["weight"])
        await update.message.reply_text(offer_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return True

    # ============================================================
    # «یخچالم» → بدون قفل (همیشه قابل مشاهده)
    # ============================================================
    if normalized in _FRIDGE_TRIGGERS:
        register_user(user.id, user.username)
        from gamification import db
        fridge_text = build_fridge_text(user.id, _display_name(user))
        items = db.get_fridge_items(user.id)
        await update.message.reply_text(
            fridge_text, reply_markup=_fridge_keyboard(user.id, items), parse_mode=ParseMode.MARKDOWN
        )
        return True

    return False


async def nazri_offer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌های پنلِ پیشنهادِ نذری: فروش / تغذیه / یخچال."""
    query = update.callback_query
    if not query:
        return

    match = _OFFER_PATTERN.match(query.data or "")
    if not match:
        await query.answer()
        return

    action, owner_id_str, food_key, weight_str = match.groups()
    owner_id = int(owner_id_str)
    weight = float(weight_str)

    if await reject_if_not_owner(query, owner_id):
        return
    await query.answer()

    if action == "sell":
        message = sell_offered_item(owner_id, food_key, weight)
    elif action == "feed":
        message = feed_offered_item(owner_id, food_key)
    else:  # store
        message = store_offered_item(owner_id, food_key, weight)

    try:
        await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await query.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


async def nazri_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌های هر آیتمِ واقعاً تو یخچال: فروش / تغذیه / گرم‌کردن."""
    query = update.callback_query
    if not query:
        return

    match = _ITEM_PATTERN.match(query.data or "")
    if not match:
        await query.answer()
        return

    action, owner_id_str, item_id_str = match.groups()
    owner_id = int(owner_id_str)
    item_id = int(item_id_str)

    if await reject_if_not_owner(query, owner_id):
        return
    await query.answer()

    if action == "sell":
        action_message = sell_fridge_item(owner_id, item_id)
    elif action == "feed":
        action_message = feed_fridge_item(owner_id, item_id)
    else:  # warm
        action_message = warm_fridge_item(owner_id, item_id)

    from gamification import db
    fridge_text = build_fridge_text(owner_id, _display_name(query.from_user))
    items = db.get_fridge_items(owner_id)
    combined = f"{action_message}\n\n{fridge_text}"

    try:
        await query.edit_message_text(
            combined, reply_markup=_fridge_keyboard(owner_id, items), parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        await query.message.reply_text(action_message, parse_mode=ParseMode.MARKDOWN)


async def fridge_upgrade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌ی «⬆️ ارتقا سطح یخچال»."""
    query = update.callback_query
    if not query:
        return

    match = _UPGRADE_PATTERN.match(query.data or "")
    if not match:
        await query.answer()
        return
    owner_id = int(match.group(1))

    if await reject_if_not_owner(query, owner_id):
        return
    await query.answer()

    upgrade_message = upgrade_fridge(owner_id)

    from gamification import db
    fridge_text = build_fridge_text(owner_id, _display_name(query.from_user))
    items = db.get_fridge_items(owner_id)
    combined = f"{upgrade_message}\n\n{fridge_text}"

    try:
        await query.edit_message_text(
            combined, reply_markup=_fridge_keyboard(owner_id, items), parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        await query.message.reply_text(upgrade_message, parse_mode=ParseMode.MARKDOWN)