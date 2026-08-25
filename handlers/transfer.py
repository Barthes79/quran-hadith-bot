# -*- coding: utf-8 -*-
"""
هندلرهای انتقال صلوات پوینت بین کاربران.

قابلیت‌ها:
  - فقط کاربران سطح ۲ به بالا می‌توانند انتقال انجام دهند.
  - حداقل انتقال ۱۰۰ صلوات پوینت، حداکثر نامحدود (تا موجودی اجازه دهد).
  - دو مرحله تایید: پس از درخواست، ربات از کاربر می‌پرسد که آیا مطمئن است.
  - کسر واقعی از موجودی مبدا و اضافه به موجودی مقصد.
  - تشخیص کاربر مقصد از طریق ریپلای روی پیام آن کاربر.
  - فقط خود کاربر درخواست‌دهنده می‌تواند روی دکمه‌ها کلیک کند.
"""

import re
import logging
import secrets

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

# کلیدهای context.chat_data برای نگهداری وضعیت تایید
_TRANSFER_PENDING_KEY = "transfer_pending"


def _code(value) -> str:
    return f"`{value}`"


# ============================================================
# پیام‌های قفل برای ارسال و دریافت
# ============================================================

async def _reply_transfer_sender_locked(update: Update, progress: dict) -> None:
    """پیام قفل برای ارسال (نیاز به سطح ۲)."""
    remaining = progress["remaining"]
    current_level = progress["level"]
    next_level = current_level + 1
    salavat_phrase = "`اللهم صل علی محمد و آل محمد`"
    
    if remaining > 0:
        msg = (
            f"🔒 قابلیت «ارسال صلوات» فقط برای کاربرانی که به سطح ۲ "
            f"«پیشرفت قابلیت‌ها» رسیده‌اند فعال است.\n\n"
            f"شما هم‌اکنون در سطح {_code(to_persian_digits(current_level))} هستید.\n"
            f"برای رسیدن به سطح بعدی (سطح {_code(to_persian_digits(next_level))})، باید "
            f"{_code(to_persian_digits(remaining))} صلوات کامل دیگه بفرستید.\n"
            f"{salavat_phrase}\n\n"
            f"هر بار که این عبارت رو کامل بنویسید، یک بار به شمارش اضافه می‌شود."
        )
    else:
        msg = (
            f"🔒 قابلیت «ارسال صلوات» فقط برای کاربرانی که به سطح ۲ "
            f"«پیشرفت قابلیت‌ها» رسیده‌اند فعال است.\n\n"
            f"شما هم‌اکنون در سطح {_code(to_persian_digits(current_level))} هستید.\n"
            f"برای فعال شدن این قابلیت، باید به سطح ۲ برسید."
        )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def _reply_transfer_receiver_locked(update: Update, progress: dict, sender_name: str) -> None:
    """پیام قفل برای دریافت (نیاز به سطح ۱) - این پیام به فرستنده نمایش داده میشه."""
    remaining = progress["remaining"]
    current_level = progress["level"]
    next_level = current_level + 1
    salavat_phrase = "`اللهم صل علی محمد و آل محمد`"
    
    if remaining > 0:
        msg = (
            f"⚠️ کاربر مقصد ({sender_name}) نمی‌تواند صلوات دریافت کند.\n\n"
            f"قابلیت «دریافت صلوات» فقط برای کاربرانی که به سطح ۱ "
            f"«پیشرفت قابلیت‌ها» رسیده‌اند فعال است.\n"
            f"این کاربر هم‌اکنون در سطح {_code(to_persian_digits(current_level))} هست.\n"
            f"برای رسیدن به سطح ۱، باید {_code(to_persian_digits(remaining))} صلوات کامل "
            f"دیگه بفرستد.\n"
            f"{salavat_phrase}\n\n"
            f"هر بار که این عبارت رو کامل بنویسد، یک بار به شمارش اضافه می‌شود."
        )
    else:
        msg = (
            f"⚠️ کاربر مقصد ({sender_name}) نمی‌تواند صلوات دریافت کند.\n\n"
            f"قابلیت «دریافت صلوات» فقط برای کاربرانی که به سطح ۱ "
            f"«پیشرفت قابلیت‌ها» رسیده‌اند فعال است.\n"
            f"این کاربر هم‌اکنون در سطح {_code(to_persian_digits(current_level))} هست.\n"
            f"برای فعال شدن این قابلیت، باید به سطح ۱ برسد."
        )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ============================================================
# هندلر اصلی تشخیص دستور انتقال
# ============================================================

async def transfer_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """
    تشخیص دستور انتقال صلوات با ریپلای.
    فرمت: «انتقال صلواتی ۱۰۰» (عدد دلخواه)
    شرط: کاربر باید روی پیام کاربر دیگری ریپلای زده باشد.
    """
    if not update.message:
        return False
    
    user = update.effective_user
    chat_id = update.effective_chat.id
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
    
    # بررسی سطح کاربر فرستنده برای ارسال (سطح ۲ به بالا)
    sender_progress = get_pigeon_feature_progress(user.id)
    if sender_progress["level"] < 2:
        await _reply_transfer_sender_locked(update, sender_progress)
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
    
    # 🔑 تولید شناسه یکتا برای این درخواست
    request_id = secrets.token_hex(8)
    
    # ذخیره اطلاعات درخواست در chat_data با شناسه یکتا
    if "transfer_requests" not in context.chat_data:
        context.chat_data["transfer_requests"] = {}
    
    context.chat_data["transfer_requests"][request_id] = {
        "from_user_id": user.id,
        "to_user_id": target_user.id,
        "amount": amount,
        "to_username": target_user.username or target_user.first_name or "کاربر",
        "to_first_name": target_user.first_name or "کاربر"
    }
    
    # ذخیره request_id در context.user_data برای دسترسی سریع
    context.user_data[_TRANSFER_PENDING_KEY] = request_id
    
    # نمایش پیام تایید با شناسه در دکمه‌ها
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ بله، مطمئنم", callback_data=f"transfer_confirm_{request_id}"),
            InlineKeyboardButton("❌ نه، منصرف شدم", callback_data=f"transfer_cancel_{request_id}")
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


# ============================================================
# کالبک تایید/لغو انتقال (با محدودیت دسترسی فقط برای درخواست‌دهنده)
# ============================================================

async def transfer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ به دکمه‌های تایید/لغو انتقال.
    
    فقط کاربری که درخواست انتقال را ایجاد کرده (from_user_id) می‌تواند
    روی دکمه‌ها کلیک کند. سایر کاربران پیام خطا دریافت می‌کنند.
    """
    query = update.callback_query
    if not query:
        return
    
    # ابتدا به کاربر اطلاع می‌دهیم که درخواستش دریافت شده
    await query.answer()
    
    # استخراج request_id از callback_data
    data_parts = query.data.split("_")
    if len(data_parts) < 3:
        await query.answer("⚠️ درخواست نامعتبر.")
        return
    
    action = data_parts[1]  # confirm یا cancel
    request_id = data_parts[2]
    
    # دریافت اطلاعات درخواست از chat_data
    if "transfer_requests" not in context.chat_data:
        await query.edit_message_text("⚠️ درخواست انتقال منقضی شده است. دوباره امتحان کنید.")
        return
    
    pending = context.chat_data["transfer_requests"].get(request_id)
    if not pending:
        await query.edit_message_text("⚠️ درخواست انتقال منقضی شده است. دوباره امتحان کنید.")
        return
    
    # 🔒 بررسی اینکه کاربر کلیک‌کننده، همان درخواست‌دهنده است
    if query.from_user.id != pending["from_user_id"]:
        # فقط یک اخطار به کاربر نشان بده و هیچ تغییری در پیام ایجاد نکن
        await query.answer("🚫 این دکمه مال شما نیست. فقط شخص درخواست‌کننده می‌تواند روی آن کلیک کند.", show_alert=True)
        return
    
    # از اینجا به بعد فقط خود درخواست‌دهنده می‌تواند ادامه دهد
    # حذف درخواست از chat_data
    del context.chat_data["transfer_requests"][request_id]
    context.user_data.pop(_TRANSFER_PENDING_KEY, None)
    
    if action == "cancel":
        await query.edit_message_text("❌ انتقال لغو شد.")
        return
    
    if action == "confirm":
        # انجام انتقال
        from_user_id = pending["from_user_id"]
        to_user_id = pending["to_user_id"]
        amount = pending["amount"]
        to_username = pending["to_username"]
        to_first_name = pending.get("to_first_name", "کاربر")
        
        # 🔒 بررسی سطح گیرنده برای دریافت (نیاز به سطح ۱)
        receiver_progress = get_pigeon_feature_progress(to_user_id)
        if receiver_progress["level"] < 1:
            await query.edit_message_text(
                f"⚠️ کاربر مقصد ({to_first_name}) نمی‌تواند صلوات دریافت کند.\n\n"
                f"او هم‌اکنون در سطح {_code(to_persian_digits(receiver_progress['level']))} است.\n"
                f"برای دریافت صلوات، باید حداقل سطح ۱ باشد.\n"
                f"فعلاً {_code(to_persian_digits(receiver_progress['remaining']))} صلوات کامل دیگر لازم دارد."
            )
            return
        
        # بررسی دوباره موجودی فرستنده (برای جلوگیری از تغییر همزمان)
        profile = get_profile(from_user_id)
        wallet = profile["xp"] if profile else 0
        if wallet < amount:
            await query.edit_message_text(
                f"⚠️ موجودی شما دیگر کافی نیست. انتقال لغو شد."
            )
            return
        
        # کسر از مبدا و اضافه به مقصد در یک تراکنش
        try:
            # کسر از مبدا
            if not spend_points(from_user_id, amount):
                await query.edit_message_text(
                    f"⚠️ خطا در انجام انتقال. موجودی شما تغییر کرده است."
                )
                return
            
            # اضافه به مقصد
            add_points(to_user_id, amount)
            
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
            logger.error(f"خطا در انتقال: {e}")
            await query.edit_message_text(
                f"⚠️ خطا در انجام انتقال. لطفاً دوباره امتحان کنید."
            )