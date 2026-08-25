# -*- coding: utf-8 -*-
"""
هندلرهای متنی/callback مربوط به یخچال صلواتی و آیتم‌های نذری.
"""

import re
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from database import register_user
from handlers.pigeon import reject_if_not_owner, _display_name
from gamification import db
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
    buy_fridge,  # ✅ تابع خرید یخچال
)
from gamification.pigeon import get_pigeon_feature_progress
from text_utils import to_persian_digits

logger = logging.getLogger(__name__)

_FRIDGE_TRIGGERS = ("یخچالم", "یخچال من", "یخچال صلواتی")

_OFFER_PATTERN = re.compile(r"^nzoffer:(sell|feed|store):(\d+):([a-z]+):([\d.]+)$")
_ITEM_PATTERN = re.compile(r"^nzitem:(sell|feed|warm):(\d+):(\d+)$")
_UPGRADE_PATTERN = re.compile(r"^nzupgrade:(\d+)$")

# ✅ دکمه‌ی خرید یخچال
_BUY_FRIDGE_CALLBACK = "buy_fridge"


def _offer_keyboard(owner_id: int, food_key: str, weight: float, user_level: int, has_fridge: bool) -> InlineKeyboardMarkup:
    """
    ساخت کیبورد برای نذری پیشنهادی.
    دکمه‌ی «بندازش تو یخچال» فقط اگر کاربر سطح >= 5 و یخچال داشته باشد نمایش داده می‌شود.
    """
    weight_str = f"{weight:.2f}"
    buttons = [
        [InlineKeyboardButton("💰 فروش نذری", callback_data=f"nzoffer:sell:{owner_id}:{food_key}:{weight_str}")],
        [InlineKeyboardButton("🕊️ بده کبوترت بخوره", callback_data=f"nzoffer:feed:{owner_id}:{food_key}:{weight_str}")],
    ]
    # فقط اگر کاربر سطح >= 5 و یخچال داشته باشد، دکمه‌ی یخچال را نشان بده
    if user_level >= 5 and has_fridge:
        buttons.append([InlineKeyboardButton("❄️ بندازش تو یخچال", callback_data=f"nzoffer:store:{owner_id}:{food_key}:{weight_str}")])
    return InlineKeyboardMarkup(buttons)


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


def _buy_fridge_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    """کیبورد خرید یخچال با دکمه‌های خرید و انصراف."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ خرید یخچال", callback_data=f"{_BUY_FRIDGE_CALLBACK}:{owner_id}")],
        [InlineKeyboardButton("❌ انصراف", callback_data="fridge_cancel")]
    ])


def _code(value) -> str:
    return f"`{value}`"


# ============================================================
# پیام‌های قفل و راهنما
# ============================================================

async def _reply_fridge_locked(update: Update, progress: dict) -> None:
    """پیام قفل برای «یخچالم» (سطح ۵)."""
    remaining = progress["remaining"]
    current_level = progress["level"]
    next_level = current_level + 1
    salavat_phrase = "`اللهم صل علی محمد و آل محمد`"
    if remaining > 0:
        msg = (
            f"🔒 قابلیت «یخچالم» فقط برای کاربرانی که به سطح ۵ "
            f"«پیشرفت قابلیت‌ها» رسیده‌اند فعال است.\n\n"
            f"شما هم‌اکنون در سطح {_code(to_persian_digits(current_level))} هستید.\n"
            f"برای رسیدن به سطح بعدی (سطح {_code(to_persian_digits(next_level))})، باید "
            f"{_code(to_persian_digits(remaining))} صلوات کامل دیگه بفرستید.\n"
            f"{salavat_phrase}\n\n"
            f"هر بار که این عبارت رو کامل بنویسید، یک بار به شمارش اضافه می‌شود."
        )
    else:
        msg = (
            f"🔒 قابلیت «یخچالم» فقط برای کاربرانی که به سطح ۵ "
            f"«پیشرفت قابلیت‌ها» رسیده‌اند فعال است.\n\n"
            f"شما هم‌اکنون در سطح {_code(to_persian_digits(current_level))} هستید.\n"
            f"برای فعال شدن این قابلیت، باید به سطح ۵ برسید."
        )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def _reply_nazri_locked(update: Update, progress: dict) -> None:
    """پیام قفل برای «نذری» (سطح ۱)."""
    remaining = progress["remaining"]
    current_level = progress["level"]
    next_level = current_level + 1
    salavat_phrase = "`اللهم صل علی محمد و آل محمد`"
    if remaining > 0:
        msg = (
            f"🔒 قابلیت «نذری» فقط برای کاربرانی که به سطح ۱ "
            f"«پیشرفت قابلیت‌ها» رسیده‌اند فعال است.\n\n"
            f"شما هم‌اکنون در سطح {_code(to_persian_digits(current_level))} هستید.\n"
            f"برای رسیدن به سطح ۱، باید {_code(to_persian_digits(remaining))} صلوات کامل "
            f"دیگه بفرستید.\n"
            f"{salavat_phrase}\n\n"
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


def _build_buy_fridge_text(cost: int) -> str:
    """متن نمایشی برای پنل خرید یخچال."""
    from gamification.config import FRIDGE_BUY_COST
    return (
        f"❄️ *خرید یخچال صلواتی*\n\n"
        f"هزینه‌ی خرید یخچال: {_code(to_persian_digits(FRIDGE_BUY_COST))} صلوات پوینت\n\n"
        f"با خرید یخچال می‌توانید نذری‌های خود را ذخیره کنید، گرم کنید و از امکانات کامل یخچال استفاده کنید.\n\n"
        f"آیا مایل به خرید هستید؟"
    )


# ============================================================
# هندلر اصلی متن
# ============================================================

async def fridge_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """
    اگه پیام «نذری» یا «یخچالم» باشه، پنل مربوطه رو می‌فرسته و True
    برمی‌گردونه؛ وگرنه False (هم پیوی هم گروه فعاله).
    
    🔒 قفل‌ها:
      - «نذری» -> سطح ۱ به بالا
      - «یخچالم» -> سطح ۵ به بالا (و سپس خرید)
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
        progress = get_pigeon_feature_progress(user.id)
        if progress["level"] < 1:
            await _reply_nazri_locked(update, progress)
            return True
        rolled = roll_nazri(user.id)
        if not rolled["ok"]:
            await update.message.reply_text(rolled["message"], parse_mode=ParseMode.MARKDOWN)
            return True
        item = rolled["item"]
        offer_text = build_offer_text(item)
        has_fridge = db.get_has_fridge(user.id)
        keyboard = _offer_keyboard(user.id, item["food_key"], item["weight"], progress["level"], has_fridge)
        await update.message.reply_text(offer_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return True

    # ============================================================
    # «یخچالم» → نیاز به سطح ۵
    # ============================================================
    if normalized in _FRIDGE_TRIGGERS:
        register_user(user.id, user.username)
        progress = get_pigeon_feature_progress(user.id)
        
        # ❌ اگر سطح کمتر از ۵ باشد، قفل
        if progress["level"] < 5:
            await _reply_fridge_locked(update, progress)
            return True
        
        # ❌ اگر سطح >= ۵ باشد ولی یخچال نداشته باشد، پنل خرید
        if not db.get_has_fridge(user.id):
            from gamification.config import FRIDGE_BUY_COST
            text = _build_buy_fridge_text(FRIDGE_BUY_COST)
            keyboard = _buy_fridge_keyboard(user.id)
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            return True
        
        # ✅ اگر سطح >= ۵ و یخچال داشته باشد، پنل یخچال
        fridge_text = build_fridge_text(user.id, _display_name(user))
        items = db.get_fridge_items(user.id)
        await update.message.reply_text(
            fridge_text, reply_markup=_fridge_keyboard(user.id, items), parse_mode=ParseMode.MARKDOWN
        )
        return True

    return False


# ============================================================
# کالبک‌های مربوط به آیتم‌های نذری و خرید یخچال
# ============================================================

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
    
    # اگر عمل «store» (یخچال) باشد، سطح کاربر و داشتن یخچال را چک کن
    if action == "store":
        progress = get_pigeon_feature_progress(owner_id)
        if progress["level"] < 5:
            await query.answer("🔒 این قابلیت فقط برای کاربران سطح ۵ به بالا فعال است.", show_alert=True)
            return
        if not db.get_has_fridge(owner_id):
            await query.answer("❌ شما یخچال ندارید! ابتدا با نوشتن «یخچالم» یخچال را خریداری کنید.", show_alert=True)
            return
    
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
    else:
        action_message = warm_fridge_item(owner_id, item_id)
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
    fridge_text = build_fridge_text(owner_id, _display_name(query.from_user))
    items = db.get_fridge_items(owner_id)
    combined = f"{upgrade_message}\n\n{fridge_text}"
    try:
        await query.edit_message_text(
            combined, reply_markup=_fridge_keyboard(owner_id, items), parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        await query.message.reply_text(upgrade_message, parse_mode=ParseMode.MARKDOWN)


# ============================================================
# کالبک خرید یخچال
# ============================================================

async def buy_fridge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ به دکمه‌ی خرید یخچال."""
    query = update.callback_query
    if not query:
        return
    # بررسی اینکه آیا کالبک مربوط به خرید است
    if not query.data.startswith(_BUY_FRIDGE_CALLBACK):
        return
    try:
        owner_id = int(query.data.split(":")[1])
    except (IndexError, ValueError):
        await query.answer("⚠️ خطا در پردازش درخواست.")
        return
    
    if await reject_if_not_owner(query, owner_id):
        return
    await query.answer()
    
    # انجام خرید
    result_message = buy_fridge(owner_id)
    # بعد از خرید، اگر موفق بود، پنل یخچال را نشان بده
    if "موفقیت" in result_message or "خریداری شد" in result_message:
        # نمایش پنل یخچال بعد از خرید موفق
        fridge_text = build_fridge_text(owner_id, _display_name(query.from_user))
        items = db.get_fridge_items(owner_id)
        combined = f"{result_message}\n\n{fridge_text}"
        try:
            await query.edit_message_text(
                combined, reply_markup=_fridge_keyboard(owner_id, items), parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            await query.message.reply_text(combined, parse_mode=ParseMode.MARKDOWN)
    else:
        # اگر خطا بود، فقط پیام خطا را نشان بده
        try:
            await query.edit_message_text(result_message, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await query.message.reply_text(result_message, parse_mode=ParseMode.MARKDOWN)


async def fridge_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ به دکمه‌ی انصراف از خرید یخچال."""
    query = update.callback_query
    if not query:
        return
    await query.answer()
    try:
        await query.edit_message_text("❌ خرید یخچال لغو شد.", parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await query.message.reply_text("❌ خرید یخچال لغو شد.", parse_mode=ParseMode.MARKDOWN)