# handlers/salavat.py
"""
صلوات‌شمار گروهی.

- هر پیامی که توی یه گروه، کلمه‌ی «صلوات» توش باشه، شمرده می‌شه (هم برای
  خود شخص، هم برای مجموع گروه). اگه کنارش یه عدد هم نوشته باشه (مثل
  «صلوات 50» یا «۱۰۰ صلوات»)، همون تعداد به‌جای یکی حساب می‌شه.
- برای اینکه گروه شلوغ نشه، به‌جای فرستادن پیام برای هر صلوات، فقط روی
  همون پیام یه ری‌اکشن 🙏 می‌زنیم. فقط سر رکوردهای هر ۵۰ تا، یا وقتی یه
  «ختم» فعال به هدفش برسه، پیام تبریک می‌فرستیم.
- /salavat            -> نمایش مجموع گروه + وضعیت ختم فعال (اگه باشه)
- /salavat_top         -> جدول نفرات برتر
- /salavat_goal N عنوان -> (فقط ادمین) شروع یه ختم جدید با هدف N صلوات
"""
import logging
import re

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
MILESTONE_STEP = 50  # هر چند تا صلوات، پیام تبریک بفرستیم
MAX_SALAVAT_PER_MESSAGE = 1000  # سقف امنیتی، جلوی سوءاستفاده رو می‌گیره

# تشخیص کلمه‌ی «صلوات» به‌عنوان یک کلمه‌ی مستقل
_SALAVAT_PATTERN = re.compile(r"صلوات")

# عددی که کنار کلمه‌ی «صلوات» نوشته شده (قبل یا بعدش)، مثلاً «صلوات 50»،
# «50 صلوات»، «صلوات ۱۰۰ تا» یا «۱۰۰ تا صلوات»
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
    اگه پیام توی یه گروه باشه و کلمه‌ی «صلوات» توش باشه، شمارش می‌کنه.
    خروجی True یعنی این پیام رو مصرف کرد (برای هماهنگی با general_text_handler،
    هرچند فعلاً جلوی هندلرهای دیگه رو نمی‌گیره چون صلوات با آیه/سرچ تداخلی نداره).
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
    user_count, chat_total = increment_salavat(chat.id, user.id, user_name, amount)
    prev_total = chat_total - amount

    # ری‌اکشن بی‌سروصدا روی خود پیام (به‌جای پیام جدید، تا اسپم نشه)
    try:
        await context.bot.set_message_reaction(
            chat_id=chat.id,
            message_id=message.message_id,
            reaction=[ReactionEmoji.PERSON_WITH_FOLDED_HANDS],
        )
    except Exception as e:
        logger.debug(f"عدم امکان ست کردن ری‌اکشن صلوات: {e}")

    # اگه یه ختم/هدف فعاله، ببینیم توی همین پیام بهش رسیدیم یا رد شدیم یا نه
    # (چون ممکنه کاربر یهو عدد بزرگی مثل «صلوات 200» بفرسته و از وسط هدف
    # بپره جلو، نمی‌شه فقط progress == goal_count رو چک کرد)
    goal = get_salavat_goal(chat.id)
    if goal and goal["goal_count"] and not goal["announced"]:
        progress = chat_total - goal["start_total"]
        prev_progress = prev_total - goal["start_total"]
        if progress >= goal["goal_count"] > prev_progress:
            mark_salavat_goal_announced(chat.id)
            await context.bot.send_message(
                chat_id=chat.id,
                text=(
                    f"🎉🌹 *ختم صلوات «{goal['title']}» تکمیل شد!*\n\n"
                    f"مجموع {goal['goal_count']} صلواتی که هدف بود، فرستاده شد. "
                    f"خدا از همه‌ی عزیزانی که شرکت کردن قبول کنه 🤲\n\n"
                    f"برای شروع یه ختم جدید، از دستور /salavat_goal استفاده کنید."
                ),
                parse_mode="Markdown",
            )
            return True

    # پیام تبریک سر رکوردهای رند (وقتی هدف فعالی در کار نیست).
    # چون ممکنه با یه عدد بزرگ از وسط یه مرز رد بشیم (مثلاً 48 -> 53)،
    # به‌جای total % STEP == 0، عبور از مرز رو چک می‌کنیم.
    elif chat_total // MILESTONE_STEP > prev_total // MILESTONE_STEP:
        milestone = (prev_total // MILESTONE_STEP + 1) * MILESTONE_STEP
        await context.bot.send_message(
            chat_id=chat.id,
            text=f"🌹 صلوات‌های این گروه از مرز *{milestone}* رد شد! مجموع الان: *{chat_total}*",
            parse_mode="Markdown",
        )

    return True


async def salavat_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /salavat -- نمایش مجموع گروه و وضعیت ختم فعال"""
    chat = update.effective_chat

    if chat.type not in GROUP_CHAT_TYPES:
        await update.message.reply_text(
            "🌹 صلوات‌شمار فقط داخل گروه‌ها کار می‌کنه. "
            "منو به یه گروه اضافه کن و همونجا هر وقت کسی «صلوات» بنویسه، شمرده میشه."
        )
        return

    total = get_salavat_chat_total(chat.id)
    text = f"🌹 *صلوات‌شمار گروه {chat.title}*\n\nمجموع تا الان: *{total}* صلوات\n"

    goal = get_salavat_goal(chat.id)
    if goal and goal["goal_count"] and not goal["announced"]:
        progress = max(0, total - goal["start_total"])
        remaining = max(0, goal["goal_count"] - progress)
        percent = min(100, int(progress * 100 / goal["goal_count"])) if goal["goal_count"] else 0
        filled = percent // 10
        bar = "🟩" * filled + "⬜️" * (10 - filled)
        text += (
            f"\n🎯 *ختم فعال:* {goal['title']}\n"
            f"{bar} {percent}٪\n"
            f"{progress} از {goal['goal_count']} ({remaining} مونده)\n"
        )

    top = get_salavat_top(chat.id, limit=5)
    if top:
        text += "\n🏆 *نفرات برتر:*\n"
        medals = ["🥇", "🥈", "🥉", "4.", "5."]
        for i, row in enumerate(top):
            text += f"{medals[i]} {row['user_name']} — {row['count']}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def salavat_top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /salavat_top -- جدول کامل‌تر نفرات برتر"""
    chat = update.effective_chat

    if chat.type not in GROUP_CHAT_TYPES:
        await update.message.reply_text("🌹 این دستور فقط داخل گروه‌ها کار می‌کنه.")
        return

    top = get_salavat_top(chat.id, limit=10)
    if not top:
        await update.message.reply_text("هنوز کسی توی این گروه صلواتی ثبت نکرده 🌹")
        return

    text = f"🏆 *نفرات برتر صلوات‌شمار {chat.title}*\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(top):
        prefix = medals[i] if i < 3 else f"{i + 1}."
        text += f"{prefix} {row['user_name']} — {row['count']} صلوات\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def salavat_goal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /salavat_goal N عنوان -- (فقط ادمین گروه) شروع یه ختم جدید"""
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
            "`/salavat_goal 1000 شفای فلانی`\n\n"
            "(عدد اول تعداد هدف، بقیه‌ی متن عنوان اختیاریه)",
            parse_mode="Markdown",
        )
        return

    goal_count = int(args[0])
    if goal_count <= 0:
        await update.message.reply_text("⚠️ عدد هدف باید بزرگ‌تر از صفر باشه.")
        return

    title = " ".join(args[1:]).strip() or "بدون عنوان"
    set_salavat_goal(chat.id, goal_count, title)

    await update.message.reply_text(
        f"🎯 ختم صلوات جدید شروع شد!\n\n"
        f"*عنوان:* {title}\n"
        f"*هدف:* {goal_count} صلوات\n\n"
        f"هرکس توی گروه بنویسه «صلوات»، به این ختم اضافه میشه. "
        f"وضعیت رو با /salavat می‌تونید ببینید.",
        parse_mode="Markdown",
    )
