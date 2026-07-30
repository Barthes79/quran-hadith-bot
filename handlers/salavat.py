# handlers/salavat.py
"""
صلوات‌شمار گروهی - با پشتیبانی از ختم
"""

import logging
import re
import html

from telegram import Update
from telegram.constants import ReactionEmoji
from telegram.ext import ContextTypes

from database import (
    increment_salavat,
    get_salavat_chat_total,
    get_salavat_top,
    get_salavat_goal,
    set_salavat_goal,
    mark_salavat_goal_announced,
)

logger = logging.getLogger(__name__)

GROUP_CHAT_TYPES = ("group", "supergroup")
MILESTONE_STEP = 50
MAX_SALAVAT_PER_MESSAGE = 1000

_SALAVAT_PATTERN = re.compile(r"صلوات")

_SALAVAT_NUMBER_PATTERN = re.compile(
    r"(?:(\d+)\s*(?:تا)?\s*صلوات)|(?:صلوات\s*(?:تا)?\s*(\d+))"
)
_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _extract_salavat_amount(text: str) -> int:
    """اگه کنار کلمه‌ی صلوات یه عدد نوشته شده باشه (مثل «صلوات 50» یا
    «۱۰۰ صلوات») همون عدد رو برمی‌گردونه، وگرنه ۱ (یک صلوات ساده)."""
    normalized = text.translate(_DIGIT_TRANSLATION)
    match = _SALAVAT_NUMBER_PATTERN.search(normalized)
    if not match:
        return 1

    num_str = match.group(1) or match.group(2)
    try:
        amount = int(num_str)
    except (TypeError, ValueError):
        return 1

    if amount <= 0:
        return 1
    return min(amount, MAX_SALAVAT_PER_MESSAGE)


def _display_name(user) -> str:
    return user.first_name or user.full_name or (f"@{user.username}" if user.username else "کاربر")


async def salavat_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    مدیریت پیام‌های حاوی کلمه صلوات.
    شمارش ساده و نمایش ری‌اکشن.
    """
    message = update.message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not message.text or not chat or chat.type not in GROUP_CHAT_TYPES:
        return False

    if not _SALAVAT_PATTERN.search(message.text):
        return False

    amount = _extract_salavat_amount(message.text)
    user_name = _display_name(user)

    # ری‌اکشن بی‌صدا روی خود پیام
    try:
        await context.bot.set_message_reaction(
            chat_id=chat.id,
            message_id=message.message_id,
            reaction=[ReactionEmoji.PERSON_WITH_FOLDED_HANDS],
        )
    except Exception as e:
        logger.debug(f"عدم امکان ست کردن ری‌اکشن صلوات: {e}")

    # ثبت صلوات
    user_count, chat_total = increment_salavat(chat.id, user.id, user_name, amount)
    prev_total = chat_total - amount

    # چک کردن تکمیل ختم
    goal = get_salavat_goal(chat.id)
    if goal and goal.get("goal_count") and not goal.get("announced", 0):
        progress = chat_total - goal.get("start_total", 0)
        prev_progress = prev_total - goal.get("start_total", 0)
        if progress >= goal["goal_count"] > prev_progress:
            mark_salavat_goal_announced(chat.id)
            safe_title = html.escape(goal.get("title", ""))
            try:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=(
                        f"🎉🌹 <b>ختم صلوات «{safe_title}» تکمیل شد!</b>\n\n"
                        f"مجموع {goal['goal_count']} صلواتی که هدف بود، فرستاده شد. "
                        f"خدا از همه‌ی عزیزانی که شرکت کردن قبول کنه 🤲\n\n"
                        f"برای شروع یه ختم جدید، از دستور /salavat_goal استفاده کنید."
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"خطا در ارسال پیام تکمیل ختم صلوات (چت {chat.id}): {e}")
            return True

    # پیام تبریک سر رکوردهای رند
    if chat_total // MILESTONE_STEP > prev_total // MILESTONE_STEP:
        milestone = (prev_total // MILESTONE_STEP + 1) * MILESTONE_STEP
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"🌹 صلوات‌های این گروه از مرز <b>{milestone}</b> رد شد! مجموع الان: <b>{chat_total}</b>",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"خطا در ارسال پیام رکورد صلوات (چت {chat.id}): {e}")

    return True


async def salavat_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /salavat -- نمایش مجموع گروه و وضعیت ختم فعال و نفرات برتر"""
    chat = update.effective_chat

    if chat.type not in GROUP_CHAT_TYPES:
        await update.message.reply_text(
            "🌹 صلوات‌شمار فقط داخل گروه‌ها کار می‌کنه. "
            "منو به یه گروه اضافه کن و همونجا هر وقت کسی «صلوات» بنویسه، شمرده میشه."
        )
        return

    total = get_salavat_chat_total(chat.id)
    safe_chat_title = html.escape(chat.title or "این گروه")
    text = f"🌹 <b>صلوات‌شمار گروه {safe_chat_title}</b>\n\nمجموع تا الان: <b>{total}</b> صلوات\n"

    # ختم فعال
    goal = get_salavat_goal(chat.id)
    if goal and goal.get("goal_count") and not goal.get("announced", 0):
        progress = max(0, total - goal.get("start_total", 0))
        remaining = max(0, goal["goal_count"] - progress)
        percent = min(100, int(progress * 100 / goal["goal_count"])) if goal["goal_count"] else 0
        filled = percent // 10
        bar = "🟩" * filled + "⬜️" * (10 - filled)
        safe_goal_title = html.escape(goal.get("title", ""))
        text += (
            f"\n🎯 <b>ختم فعال:</b> {safe_goal_title}\n"
            f"{bar} {percent}٪\n"
            f"{progress} از {goal['goal_count']} ({remaining} مونده)\n"
        )

    # نفرات برتر
    top = get_salavat_top(chat.id, limit=5)
    if top:
        text += "\n🏆 <b>نفرات برتر:</b>\n"
        medals = ["🥇", "🥈", "🥉", "4.", "5."]
        for i, row in enumerate(top):
            safe_name = html.escape(row["user_name"] or "کاربر")
            text += f"{medals[i]} {safe_name} — {row['count']}\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def salavat_top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /salavat_top -- جدول کامل‌تر نفرات برتر"""
    chat = update.effective_chat

    if chat.type not in GROUP_CHAT_TYPES:
        await update.message.reply_text("🌹 این دستور فقط داخل گروه‌ها کار می‌کنه.")
        return

    top = get_salavat_top(chat.id, limit=15)
    if not top:
        await update.message.reply_text("هنوز کسی توی این گروه صلواتی ثبت نکرده 🌹")
        return

    safe_chat_title = html.escape(chat.title or "این گروه")
    text = f"🏆 <b>نفرات برتر صلوات‌شمار {safe_chat_title}</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(top):
        prefix = medals[i] if i < 3 else f"{i + 1}."
        safe_name = html.escape(row["user_name"] or "کاربر")
        text += f"{prefix} {safe_name} — {row['count']} صلوات\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def salavat_goal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /salavat_goal N عنوان -- (فقط ادمین) شروع یه ختم جدید"""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in GROUP_CHAT_TYPES:
        await update.message.reply_text("🌹 این دستور فقط داخل گروه‌ها کار می‌کنه.")
        return

    # فقط ادمین‌های گروه بتونن ختم تعریف کنن
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        is_admin = member.status in ("administrator", "creator")
    except Exception as e:
        logger.error(f"خطا در بررسی ادمین بودن برای صلوات‌شمار: {e}")
        is_admin = False

    if not is_admin:
        await update.message.reply_text("⛔ فقط ادمین‌های گروه می‌تونن ختم صلوات تعریف کنن.")
        return

    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "برای شروع یه ختم صلوات جدید بنویسید:\n"
            "<code>/salavat_goal 1000 شفای فلانی</code>\n\n"
            "(عدد اول تعداد هدف، بقیه‌ی متن عنوان اختیاریه)",
            parse_mode="HTML",
        )
        return

    goal_count = int(args[0])
    if goal_count <= 0:
        await update.message.reply_text("⚠️ عدد هدف باید بزرگ‌تر از صفر باشه.")
        return

    title = " ".join(args[1:]).strip() or "بدون عنوان"
    
    # تنظیم ختم جدید
    set_salavat_goal(chat.id, goal_count, title)

    safe_title = html.escape(title)
    await update.message.reply_text(
        f"🎯 ختم صلوات جدید شروع شد!\n\n"
        f"<b>عنوان:</b> {safe_title}\n"
        f"<b>هدف:</b> {goal_count} صلوات\n\n"
        f"هرکس توی گروه بنویسه «صلوات»، به این ختم اضافه میشه. "
        f"وضعیت رو با /salavat می‌تونید ببینید.",
        parse_mode="HTML",
    )