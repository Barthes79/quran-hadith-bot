# handlers/salavat.py
"""
صلوات‌شمار گروهی با پشتیبانی از ختم‌های متعدد.

- هر پیامی که توی یه گروه، کلمه‌ی «صلوات» توش باشه، شمرده می‌شه.
- اگر چند ختم فعال وجود داشته باشد، پنل انتخاب برای کاربر نمایش داده می‌شود.
- کاربر می‌تواند انتخاب کند صلوات خود را به نیت کدام ختم بفرستد.
- پنل و پیام اصلی بعد از انتخاب حذف می‌شوند تا گروه شلوغ نشود.
- /salavat            -> نمایش مجموع گروه + لیست ختم‌های فعال
- /salavat_top        -> جدول نفرات برتر
- /salavat_goal N عنوان -> (فقط ادمین) شروع یه ختم جدید
- /salavat_goals      -> نمایش لیست ختم‌های فعال و تکمیل‌شده
- /salavat_delete [شناسه] -> (فقط ادمین) حذف یک ختم
- /salavat_participants [شناسه] -> نمایش مشارکت‌کنندگان یک ختم
- /salavat_multi      -> (فقط ادمین) فعال/غیرفعال کردن حالت چندختمی
"""
import logging
import re
import html
from typing import List, Dict, Any, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ReactionEmoji
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from database import (
    increment_salavat,
    get_salavat_chat_total,
    get_salavat_top,
    get_salavat_goal,
    set_salavat_goal,
    mark_salavat_goal_announced,
    create_salavat_goal,
    get_active_goals,
    get_goal_by_id,
    contribute_to_goal,
    delete_goal,
    get_goal_participants,
    save_interactive_message,
    delete_interactive_messages,
    get_interactive_messages,
    get_completed_goals,
    get_group_settings,
    update_group_settings,
    get_connection,
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


def _format_goal_card(goal: dict, total_contributions: int = 0, user_contrib: int = 0) -> str:
    """قالب‌بندی کارت نمایش یک ختم."""
    goal_count = goal["goal_count"]
    remaining = max(0, goal_count - total_contributions)
    percent = min(100, int(total_contributions * 100 / goal_count)) if goal_count else 0
    filled = percent // 10
    bar = "🟩" * filled + "⬜️" * (10 - filled)
    
    safe_title = html.escape(goal["title"])
    text = (
        f"🎯 <b>{safe_title}</b>\n"
        f"{bar} {percent}٪\n"
        f"📊 {total_contributions} از {goal_count} صلوات ({remaining} مونده)\n"
    )
    if user_contrib > 0:
        text += f"👤 سهم شما: {user_contrib} صلوات\n"
    return text


def _build_goal_selection_keyboard(goals: List[dict], user_id: int, user_name: str, amount: int) -> InlineKeyboardMarkup:
    """ساخت کیبورد انتخاب ختم."""
    keyboard = []
    
    for goal in goals:
        total = goal.get("total_contributions", 0)
        remaining = max(0, goal["goal_count"] - total)
        label = f"{goal['title']} (باقی: {remaining})"
        if remaining <= 0:
            label = f"✅ {label} - تکمیل شده!"
        callback_data = f"salavat_goal_{goal['id']}_{amount}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("❌ انصراف", callback_data="salavat_cancel")])
    
    return InlineKeyboardMarkup(keyboard)


async def salavat_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    مدیریت پیام‌های حاوی کلمه صلوات.
    اگر چند ختم فعال وجود داشته باشد، پنل انتخاب نشان داده می‌شود.
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

    # دریافت تنظیمات گروه
    settings = get_group_settings(chat.id)
    multi_goal_enabled = settings.get("multi_goal_enabled", 1)

    # دریافت ختم‌های فعال
    active_goals = get_active_goals(chat.id)
    
    # اگر ختم فعالی وجود ندارد یا حالت چندختمی غیرفعال است
    if not active_goals or not multi_goal_enabled:
        # رفتار قدیمی: فقط مجموع گروه را افزایش بده
        user_count, chat_total = increment_salavat(chat.id, user.id, user_name, amount)
        prev_total = chat_total - amount

        # چک کردن تکمیل ختم (فقط برای ختم اول)
        goal = get_salavat_goal(chat.id)
        if goal and goal["goal_count"] and not goal["announced"]:
            progress = chat_total - goal["start_total"]
            prev_progress = prev_total - goal["start_total"]
            if progress >= goal["goal_count"] > prev_progress:
                mark_salavat_goal_announced(chat.id)
                safe_title = html.escape(goal["title"] or "")
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
        elif chat_total // MILESTONE_STEP > prev_total // MILESTONE_STEP:
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

    # حالت چندختمی: نمایش پنل انتخاب
    goals_data = []
    for goal in active_goals:
        # محاسبه مشارکت کاربر در این ختم
        conn = get_connection()
        user_contrib = conn.execute(
            "SELECT amount FROM salavat_contributions WHERE goal_id = ? AND user_id = ?",
            (goal["id"], user.id)
        ).fetchone()
        conn.close()
        
        goals_data.append({
            **goal,
            "user_contrib": user_contrib["amount"] if user_contrib else 0,
        })

    # ارسال پیام با کیبورد انتخاب
    keyboard = _build_goal_selection_keyboard(goals_data, user.id, user_name, amount)
    
    # پیام راهنما
    message_text = (
        f"🌹 <b>{user_name} عزیز</b>\n\n"
        f"شما در حال فرستادن <b>{amount}</b> صلوات هستید.\n"
        f"لطفاً انتخاب کنید که این صلوات را به نیت کدام ختم بفرستید:\n\n"
    )
    
    # نمایش وضعیت خلاصه ختم‌ها
    for goal in goals_data:
        total = goal.get("total_contributions", 0)
        remaining = max(0, goal["goal_count"] - total)
        status = "✅ تکمیل شده" if remaining <= 0 else f"باقی: {remaining}"
        message_text += f"• {goal['title']} — {status}\n"

    sent_msg = await context.bot.send_message(
        chat_id=chat.id,
        text=message_text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )

    # ذخیره پیام برای حذف بعدی
    save_interactive_message(
        chat_id=chat.id,
        message_id=sent_msg.message_id,
        user_id=user.id,
        goal_id=0,
        message_type="salavat_selection",
    )

    # همچنین پیام اصلی کاربر را برای حذف ذخیره می‌کنیم
    save_interactive_message(
        chat_id=chat.id,
        message_id=message.message_id,
        user_id=user.id,
        goal_id=0,
        message_type="salavat_trigger",
    )

    return True


async def salavat_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کل‌بک‌های انتخاب ختم."""
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    data = query.data
    
    if data == "salavat_cancel":
        await query.edit_message_text("❌ عملیات لغو شد.")
        # حذف پیام‌های تعاملی این کاربر
        delete_interactive_messages(chat_id, user_id)
        return
    
    # استخراج goal_id و amount از callback_data
    match = re.match(r"salavat_goal_(\d+)_(\d+)", data)
    if not match:
        await query.edit_message_text("⚠️ خطا در پردازش درخواست.")
        return
    
    goal_id = int(match.group(1))
    amount = int(match.group(2))
    
    # دریافت اطلاعات ختم
    goal = get_goal_by_id(goal_id)
    if not goal:
        await query.edit_message_text("⚠️ این ختم دیگر وجود ندارد.")
        delete_interactive_messages(chat_id, user_id)
        return
    
    if goal["completed"]:
        await query.edit_message_text(
            f"⚠️ ختم «{goal['title']}» قبلاً تکمیل شده است.\n"
            f"لطفاً ختم دیگری را انتخاب کنید."
        )
        # نمایش مجدد ختم‌های فعال
        active_goals = get_active_goals(chat_id)
        if active_goals:
            keyboard = _build_goal_selection_keyboard(active_goals, user_id, query.from_user.first_name, amount)
            await query.edit_message_text(
                text=query.message.text,
                reply_markup=keyboard,
            )
        else:
            await query.edit_message_text("❌ هیچ ختم فعال دیگری وجود ندارد.")
            delete_interactive_messages(chat_id, user_id)
        return
    
    # ثبت مشارکت
    user_name = _display_name(query.from_user)
    result = contribute_to_goal(goal_id, user_id, user_name, amount)
    
    if result["completed"]:
        # ختم تکمیل شده
        safe_title = html.escape(goal["title"])
        await query.edit_message_text(
            f"🎉🌹 <b>ختم صلوات «{safe_title}» تکمیل شد!</b>\n\n"
            f"مجموع {goal['goal_count']} صلوات توسط کاربران فرستاده شد.\n"
            f"خدا از همه‌ی عزیزانی که شرکت کردن قبول کنه 🤲\n\n"
            f"برای شروع یه ختم جدید، از دستور /salavat_goal استفاده کنید.",
            parse_mode="HTML",
        )
    else:
        # نمایش پیام تایید
        safe_title = html.escape(goal["title"])
        remaining = result["remaining"]
        user_contrib = result.get("user_contribution", amount)
        
        await query.edit_message_text(
            f"✅ <b>{amount} صلوات</b> به ختم «{safe_title}» اضافه شد.\n\n"
            f"📊 وضعیت فعلی:\n"
            f"• مجموع: {result['total_contributions']} از {goal['goal_count']}\n"
            f"• باقی‌مانده: {remaining}\n"
            f"• سهم شما: {user_contrib}\n\n"
            f"🙏 اجرکم الله",
            parse_mode="HTML",
        )
    
    # حذف پیام‌های تعاملی این کاربر
    interactive_msgs = get_interactive_messages(chat_id, user_id)
    for msg in interactive_msgs:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg["message_id"])
        except Exception as e:
            logger.debug(f"خطا در حذف پیام تعاملی: {e}")
    
    delete_interactive_messages(chat_id, user_id)


async def salavat_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /salavat -- نمایش مجموع گروه و وضعیت ختم‌های فعال"""
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

    # ختم‌های فعال
    active_goals = get_active_goals(chat.id)
    if active_goals:
        text += "\n🎯 <b>ختم‌های فعال:</b>\n"
        for goal in active_goals:
            total_contrib = goal.get("total_contributions", 0)
            remaining = max(0, goal["goal_count"] - total_contrib)
            percent = min(100, int(total_contrib * 100 / goal["goal_count"])) if goal["goal_count"] else 0
            filled = percent // 10
            bar = "🟩" * filled + "⬜️" * (10 - filled)
            safe_title = html.escape(goal["title"])
            text += (
                f"\n<b>{safe_title}</b>\n"
                f"{bar} {percent}٪\n"
                f"{total_contrib} از {goal['goal_count']} ({remaining} مونده)\n"
                f"👥 شرکت‌کنندگان: {goal.get('participants_count', 0)} نفر\n"
            )
    else:
        text += "\n❌ هیچ ختم فعالی وجود ندارد.\nبرای شروع: /salavat_goal"

    # ختم‌های تکمیل‌شده اخیر
    completed = get_completed_goals(chat.id, limit=3)
    if completed:
        text += "\n✅ <b>ختم‌های تکمیل‌شده اخیر:</b>\n"
        for goal in completed:
            safe_title = html.escape(goal["title"])
            text += f"• {safe_title} ({goal.get('total_contributions', 0)} صلوات)\n"

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
            "(عدد اول تعداد هدف، بقیه‌ی متن عنوان اختیاریه)\n\n"
            "⚠️ توجه: با این روش ختم‌های جدید به ختم‌های فعال قبلی اضافه می‌شوند و کاربران می‌توانند انتخاب کنند صلواتشان را به نیت کدام ختم بفرستند.",
            parse_mode="HTML",
        )
        return

    goal_count = int(args[0])
    if goal_count <= 0:
        await update.message.reply_text("⚠️ عدد هدف باید بزرگ‌تر از صفر باشه.")
        return

    title = " ".join(args[1:]).strip() or "بدون عنوان"
    
    # ایجاد ختم جدید
    goal_id = create_salavat_goal(chat.id, goal_count, title, user.id)

    safe_title = html.escape(title)
    await update.message.reply_text(
        f"🎯 ختم صلوات جدید با موفقیت ایجاد شد!\n\n"
        f"<b>عنوان:</b> {safe_title}\n"
        f"<b>هدف:</b> {goal_count} صلوات\n"
        f"<b>شناسه:</b> {goal_id}\n\n"
        f"📌 کاربران با نوشتن «صلوات» می‌توانند صلوات خود را به این ختم اختصاص دهند.\n"
        f"وضعیت ختم‌ها را با /salavat مشاهده کنید.",
        parse_mode="HTML",
    )


async def salavat_goals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /salavat_goals -- نمایش لیست ختم‌های فعال و امکان مدیریت آنها"""
    chat = update.effective_chat

    if chat.type not in GROUP_CHAT_TYPES:
        await update.message.reply_text("🌹 این دستور فقط داخل گروه‌ها کار می‌کنه.")
        return

    active_goals = get_active_goals(chat.id)
    completed_goals = get_completed_goals(chat.id, limit=5)

    if not active_goals and not completed_goals:
        await update.message.reply_text(
            "❌ هیچ ختمی در این گروه وجود ندارد.\n"
            "برای شروع: /salavat_goal"
        )
        return

    text = "📋 <b>لیست ختم‌های صلوات</b>\n\n"
    
    if active_goals:
        text += "🎯 <b>ختم‌های فعال:</b>\n"
        for goal in active_goals:
            total = goal.get("total_contributions", 0)
            remaining = max(0, goal["goal_count"] - total)
            safe_title = html.escape(goal["title"])
            text += f"• {safe_title} — {total}/{goal['goal_count']} (باقی: {remaining})\n"
    
    if completed_goals:
        text += "\n✅ <b>ختم‌های تکمیل‌شده اخیر:</b>\n"
        for goal in completed_goals:
            safe_title = html.escape(goal["title"])
            text += f"• {safe_title} — {goal.get('total_contributions', 0)} صلوات\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def salavat_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /salavat_delete [شناسه] -- (فقط ادمین) حذف یک ختم"""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in GROUP_CHAT_TYPES:
        await update.message.reply_text("🌹 این دستور فقط داخل گروه‌ها کار می‌کنه.")
        return

    # بررسی ادمین بودن
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        is_admin = member.status in ("administrator", "creator")
    except Exception as e:
        logger.error(f"خطا در بررسی ادمین بودن: {e}")
        is_admin = False

    if not is_admin:
        await update.message.reply_text("⛔ فقط ادمین‌های گروه می‌تونن ختم رو حذف کنن.")
        return

    args = context.args
    if not args:
        # نمایش لیست ختم‌های فعال برای انتخاب
        active_goals = get_active_goals(chat.id)
        if not active_goals:
            await update.message.reply_text("❌ هیچ ختم فعالی برای حذف وجود ندارد.")
            return

        keyboard = []
        for goal in active_goals:
            safe_title = html.escape(goal["title"])
            keyboard.append([
                InlineKeyboardButton(
                    f"🗑 {safe_title}",
                    callback_data=f"salavat_delete_goal_{goal['id']}"
                )
            ])
        keyboard.append([InlineKeyboardButton("❌ انصراف", callback_data="salavat_cancel")])

        await update.message.reply_text(
            "🗑 لطفاً ختم مورد نظر برای حذف را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # حذف مستقیم با شناسه
    try:
        goal_id = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ لطفاً شناسه معتبر وارد کنید.")
        return

    goal = get_goal_by_id(goal_id)
    if not goal or goal["chat_id"] != chat.id:
        await update.message.reply_text("❌ ختم مورد نظر یافت نشد.")
        return

    safe_title = html.escape(goal["title"])
    delete_goal(goal_id)
    await update.message.reply_text(
        f"✅ ختم «{safe_title}» با موفقیت حذف شد.",
        parse_mode="HTML",
    )


async def salavat_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کل‌بک حذف ختم."""
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    user_id = query.from_user.id

    # بررسی ادمین بودن
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        is_admin = member.status in ("administrator", "creator")
    except Exception as e:
        logger.error(f"خطا در بررسی ادمین بودن: {e}")
        is_admin = False

    if not is_admin:
        await query.edit_message_text("⛔ فقط ادمین‌های گروه می‌تونن ختم رو حذف کنن.")
        return

    goal_id = int(query.data.replace("salavat_delete_goal_", ""))
    goal = get_goal_by_id(goal_id)

    if not goal or goal["chat_id"] != chat_id:
        await query.edit_message_text("❌ ختم مورد نظر یافت نشد.")
        return

    safe_title = html.escape(goal["title"])
    delete_goal(goal_id)
    await query.edit_message_text(
        f"✅ ختم «{safe_title}» با موفقیت حذف شد.",
        parse_mode="HTML",
    )


async def salavat_participants_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /salavat_participants [شناسه] -- نمایش مشارکت‌کنندگان یک ختم"""
    chat = update.effective_chat

    if chat.type not in GROUP_CHAT_TYPES:
        await update.message.reply_text("🌹 این دستور فقط داخل گروه‌ها کار می‌کنه.")
        return

    args = context.args
    if not args:
        # نمایش لیست ختم‌های فعال
        active_goals = get_active_goals(chat.id)
        if not active_goals:
            await update.message.reply_text("❌ هیچ ختم فعالی وجود ندارد.")
            return

        keyboard = []
        for goal in active_goals:
            safe_title = html.escape(goal["title"])
            keyboard.append([
                InlineKeyboardButton(
                    f"👥 {safe_title}",
                    callback_data=f"salavat_participants_{goal['id']}"
                )
            ])
        keyboard.append([InlineKeyboardButton("❌ انصراف", callback_data="salavat_cancel")])

        await update.message.reply_text(
            "👥 لطفاً ختم مورد نظر برای مشاهده مشارکت‌کنندگان را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # نمایش مستقیم با شناسه
    try:
        goal_id = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ لطفاً شناسه معتبر وارد کنید.")
        return

    goal = get_goal_by_id(goal_id)
    if not goal or goal["chat_id"] != chat.id:
        await update.message.reply_text("❌ ختم مورد نظر یافت نشد.")
        return

    participants = get_goal_participants(goal_id, limit=20)
    if not participants:
        await update.message.reply_text(
            f"👤 هنوز کسی در ختم «{goal['title']}» شرکت نکرده است."
        )
        return

    safe_title = html.escape(goal["title"])
    text = f"👥 <b>مشارکت‌کنندگان در ختم «{safe_title}»</b>\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    for i, p in enumerate(participants):
        prefix = medals[i] if i < 3 else f"{i+1}."
        safe_name = html.escape(p["user_name"] or "کاربر")
        text += f"{prefix} {safe_name} — {p['amount']} صلوات\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def salavat_participants_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کل‌بک نمایش مشارکت‌کنندگان."""
    query = update.callback_query
    await query.answer()

    goal_id = int(query.data.replace("salavat_participants_", ""))
    goal = get_goal_by_id(goal_id)

    if not goal:
        await query.edit_message_text("❌ ختم مورد نظر یافت نشد.")
        return

    participants = get_goal_participants(goal_id, limit=20)
    if not participants:
        await query.edit_message_text(
            f"👤 هنوز کسی در ختم «{goal['title']}» شرکت نکرده است."
        )
        return

    safe_title = html.escape(goal["title"])
    text = f"👥 <b>مشارکت‌کنندگان در ختم «{safe_title}»</b>\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    for i, p in enumerate(participants):
        prefix = medals[i] if i < 3 else f"{i+1}."
        safe_name = html.escape(p["user_name"] or "کاربر")
        text += f"{prefix} {safe_name} — {p['amount']} صلوات\n"

    await query.edit_message_text(text, parse_mode="HTML")


async def salavat_multi_toggle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /salavat_multi -- (فقط ادمین) فعال/غیرفعال کردن حالت چندختمی"""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in GROUP_CHAT_TYPES:
        await update.message.reply_text("🌹 این دستور فقط داخل گروه‌ها کار می‌کنه.")
        return

    # بررسی ادمین بودن
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        is_admin = member.status in ("administrator", "creator")
    except Exception as e:
        logger.error(f"خطا در بررسی ادمین بودن: {e}")
        is_admin = False

    if not is_admin:
        await update.message.reply_text("⛔ فقط ادمین‌های گروه می‌تونن این تنظیمات رو تغییر بدن.")
        return

    settings = get_group_settings(chat.id)
    current = settings.get("multi_goal_enabled", 1)
    new_value = 0 if current else 1
    
    update_group_settings(chat.id, multi_goal_enabled=new_value)
    
    status = "فعال" if new_value else "غیرفعال"
    await update.message.reply_text(
        f"⚙️ حالت چندختمی صلوات‌شمار <b>{status}</b> شد.\n\n"
        f"{'✅ کاربران می‌توانند بین ختم‌های مختلف انتخاب کنند.' if new_value else '❌ کاربران فقط به ختم اصلی می‌توانند صلوات بفرستند.'}",
        parse_mode="HTML",
    )


# ============================================================
# ثبت هندلرها (برای استفاده در main.py)
# ============================================================

def register_handlers(application):
    """ثبت تمام هندلرهای مربوط به صلوات‌شمار."""
    
    # هندلر پیام‌های متنی حاوی صلوات
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.ChatType.GROUPS,
            salavat_text_handler
        )
    )
    
    # کل‌بک‌های مربوط به انتخاب ختم
    application.add_handler(
        CallbackQueryHandler(
            salavat_callback_handler,
            pattern="^salavat_goal_"
        )
    )
    
    # کل‌بک‌های مربوط به حذف ختم
    application.add_handler(
        CallbackQueryHandler(
            salavat_delete_callback,
            pattern="^salavat_delete_goal_"
        )
    )
    
    # کل‌بک‌های مربوط به نمایش مشارکت‌کنندگان
    application.add_handler(
        CallbackQueryHandler(
            salavat_participants_callback,
            pattern="^salavat_participants_"
        )
    )
    
    # کل‌بک انصراف
    application.add_handler(
        CallbackQueryHandler(
            salavat_callback_handler,
            pattern="^salavat_cancel$"
        )
    )
    
    # دستورات
    application.add_handler(CommandHandler("salavat", salavat_stats_command))
    application.add_handler(CommandHandler("salavat_top", salavat_top_command))
    application.add_handler(CommandHandler("salavat_goal", salavat_goal_command))
    application.add_handler(CommandHandler("salavat_goals", salavat_goals_command))
    application.add_handler(CommandHandler("salavat_delete", salavat_delete_command))
    application.add_handler(CommandHandler("salavat_participants", salavat_participants_command))
    application.add_handler(CommandHandler("salavat_multi", salavat_multi_toggle_command))