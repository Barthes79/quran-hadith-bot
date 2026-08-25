# -*- coding: utf-8 -*-
"""
هندلرهای انتقال صلوات پوینت بین کاربران.

قابلیت‌ها:
  - فقط کاربران سطح ۱ به بالا می‌توانند انتقال انجام دهند.
  - حداقل انتقال ۱۰۰ صلوات پوینت، حداکثر نامحدود (تا موجودی اجازه دهد).
  - دو مرحله تایید: پس از درخواست، ربات از کاربر می‌پرسد که آیا مطمئن است.
  - کسر واقعی از موجودی مبدا و اضافه به موجودی مقصد.
  - تشخیص کاربر مقصد از طریق ریپلای روی پیام آن کاربر.
"""

import re
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from database import register_user
from gamification.pigeon import get_pigeon_feature_progress
from gamification.db import get_profile, spend_points, add_points
from text_utils import to_persian_digits

logger = logging.getLogger(__name__)

# الگوی تشخیص دستور انتقال: «انتقال صلواتی ۱۰۰» یا «انتقال صلواتی 1000»
_TRANSFER_PATTERN = re.compile(r"^انتقال\s+صلواتی\s+(\d+)$", re.IGNORECASE)

# کلیدهای context.user_data برای نگهداری وضعیت تایید
_TRANSFER_PENDING_KEY = "transfer_pending"


def _code(value) -> str:
    return f"`{value}`"


async def _reply_transfer_locked(update: Update, progress: dict) -> None:
    """پیام قفل انتقال برای کاربران زیر سطح ۱.
    عبارت صلوات داخل بک‌تیک قرار می‌گیرد تا کاربر بتواند کپی کند."""
    remaining = progress["remaining"]
    current_level = progress["level"]
    next_level = current_level + 1
    salavat_phrase = "`اللهم صل علی محمد و آل محمد`"  # 🔄 قابل کپی با بک‌تیک
    
    if remaining > 0:
        msg = (
            f"🔒 قابلیت «انتقال صلوات» فقط برای کاربرانی که به سطح ۱ "
            f"«پیشرفت قابلیت‌ها» رسیده‌اند فعال است.\n\n"
            f"شما هم‌اکنون در سطح {_code(to_persian_digits(current_level))} هستید.\n"
            f"برای رسیدن به سطح ۱، باید {_code(to_persian_digits(remaining))} صلوات کامل "
            f"دیگه بفرستید.\n"
            f"{salavat_phrase}\n\n"
            f"هر بار که این عبارت رو کامل بنویسید، یک بار به شمارش اضافه می‌شود."
        )
    else:
        msg = (
            f"🔒 قابلیت «انتقال صلوات» فقط برای کاربرانی که به سطح ۱ "
            f"«پیشرفت قابلیت‌ها» رسیده‌اند فعال است.\n\n"
            f"شما هم‌اکنون در سطح {_code(to_persian_digits(current_level))} هستید.\n"
            f"برای فعال شدن این قابلیت، باید به سطح ۱ برسید."
        )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def transfer_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """
    تشخیص دستور انتقال صلوات با ریپلای.
    فرمت: «انتقال صلواتی ۱۰۰» (عدد دلخواه)
    شرط: کاربر باید روی پیام کاربر دیگری ریپلای زده باشد.
    """
    if not update.message:
        return False
    
    user = update.effective_user
    normalized = text.strip()
    
    # بررسی اینکه آیا پیام با الگوی انتقال مطابقت دارد
    match = _TRANSFER_PATTERN.match(normalized)
    if not match:
        return False
    
    # بررسی ریپلای
    reply_to = update.message.reply_to_message
    if not reply_to:
        await update.message.reply_text(
            "⚠️ برای انتقال صلوات، باید روی پیام کاربر مقصد ریپلای بزنید."
        )
        return True
    
    # دریافت کاربر مقصد از ریپلای
    target_user = reply_to.from_user
    if not target_user:
        await update.message.reply_text("⚠️ کاربر مقصد شناسایی نشد.")
        return True
    
    # جلوگیری از انتقال به خود
    if target_user.id == user.id:
        await update.message.reply_text("⚠️ نمی‌توانید به خودتان صلوات انتقال دهید.")
        return True
    
    # بررسی سطح کاربر فرستنده
    progress = get_pigeon_feature_progress(user.id)
    if progress["level"] < 1:
        await _reply_transfer_locked(update, progress)
        return True
    
    # خواندن مقدار انتقال
    try:
        amount = int(match.group(1))
    except ValueError:
        await update.message.reply_text("⚠️ مقدار وارد شده معتبر نیست.")
        return True
    
    # حداقل ۱۰۰
    if amount < 100:
        await update.message.reply_text(
            f"⚠️ حداقل انتقال {_code(to_persian_digits(100))} صلوات پوینت است."
        )
        return True
    
    # بررسی موجودی مبدا
    profile = get_profile(user.id)
    wallet = profile["xp"] if profile else 0
    if wallet < amount:
        missing = amount - wallet
        await update.message.reply_text(
            f"💰 موجودی شما کافی نیست.\n"
            f"شما {_code(to_persian_digits(wallet))} پوینت دارید، "
            f"اما برای انتقال {_code(to_persian_digits(amount))} پوینت نیاز دارید.\n"
            f"{_code(to_persian_digits(missing))} پوینت کم دارید."
        )
        return True
    
    # ذخیره اطلاعات درخواست در context.user_data برای تایید دوم
    context.user_data[_TRANSFER_PENDING_KEY] = {
        "from_user_id": user.id,
        "to_user_id": target_user.id,
        "amount": amount,
        "to_username": target_user.username or target_user.first_name or "کاربر"
    }
    
    # نمایش پیام تایید
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ بله، مطمئنم", callback_data="transfer_confirm"),
            InlineKeyboardButton("❌ نه، منصرف شدم", callback_data="transfer_cancel")
        ]
    ])
    
    confirm_msg = (
        f"⚠️ **تایید انتقال صلوات**\n\n"
        f"شما در حال انتقال {_code(to_persian_digits(amount))} صلوات پوینت "
        f"به کاربر {target_user.first_name} هستید.\n\n"
        f"آیا مطمئن هستید؟"
    )
    await update.message.reply_text(confirm_msg, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return True


async def transfer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ به دکمه‌های تایید/لغو انتقال."""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    pending = context.user_data.get(_TRANSFER_PENDING_KEY)
    if not pending:
        await query.edit_message_text("⚠️ درخواست انتقال منقضی شده است. دوباره امتحان کنید.")
        return
    
    # بررسی اینکه کاربری که دکمه را زده، همان درخواست‌دهنده است
    if query.from_user.id != pending["from_user_id"]:
        await query.answer("🚫 این دکمه مال شما نیست.", show_alert=True)
        return
    
    if query.data == "transfer_cancel":
        context.user_data.pop(_TRANSFER_PENDING_KEY, None)
        await query.edit_message_text("❌ انتقال لغو شد.")
        return
    
    if query.data == "transfer_confirm":
        # انجام انتقال
        from_user_id = pending["from_user_id"]
        to_user_id = pending["to_user_id"]
        amount = pending["amount"]
        to_username = pending["to_username"]
        
        # بررسی دوباره موجودی (برای جلوگیری از تغییر همزمان)
        profile = get_profile(from_user_id)
        wallet = profile["xp"] if profile else 0
        if wallet < amount:
            context.user_data.pop(_TRANSFER_PENDING_KEY, None)
            await query.edit_message_text(
                f"⚠️ موجودی شما دیگر کافی نیست. انتقال لغو شد."
            )
            return
        
        # کسر از مبدا و اضافه به مقصد در یک تراکنش
        try:
            # کسر از مبدا
            if not spend_points(from_user_id, amount):
                context.user_data.pop(_TRANSFER_PENDING_KEY, None)
                await query.edit_message_text(
                    f"⚠️ خطا در انجام انتقال. موجودی شما تغییر کرده است."
                )
                return
            
            # اضافه به مقصد
            add_points(to_user_id, amount)
            
            # پاک کردن وضعیت
            context.user_data.pop(_TRANSFER_PENDING_KEY, None)
            
            # گزارش موفقیت
            await query.edit_message_text(
                f"✅ انتقال با موفقیت انجام شد!\n\n"
                f"{_code(to_persian_digits(amount))} صلوات پوینت به "
                f"کاربر {to_username} منتقل شد."
            )
            
            # اطلاع به کاربر مقصد (اختیاری)
            try:
                await context.bot.send_message(
                    chat_id=to_user_id,
                    text=f"🎉 شما {_code(to_persian_digits(amount))} صلوات پوینت از "
                         f"کاربر {query.from_user.first_name} دریافت کردید!"
                )
            except Exception:
                pass  # در صورت عدم دسترسی به پیوی، خطا نادیده گرفته شود
                
        except Exception as e:
            context.user_data.pop(_TRANSFER_PENDING_KEY, None)
            logger.error(f"خطا در انتقال: {e}")
            await query.edit_message_text(
                f"⚠️ خطا در انجام انتقال. لطفاً دوباره امتحان کنید."
            )