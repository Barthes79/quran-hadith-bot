# handlers/salavat.py
"""
صلوات‌شمار گروهی - با پشتیبانی از چند ختمِ همزمان

منطق کلی:
- هر پیامی که کلمه‌ی «صلوات» توش باشه (یا فقط یه عدد ساده باشه، وقتی حداقل
  یه ختم فعال توی گروه هست) به‌عنوان صلوات شمرده می‌شه و روی شمارنده‌ی کل
  گروه اضافه می‌شه.
- اگه اون لحظه توی گروه یک یا چند ختم فعال وجود داشته باشه، یه پنل شیشه‌ای
  (inline keyboard) زیر پیام باز می‌شه که وضعیت هر ختم رو نشون می‌ده و از
  فرستنده می‌پرسه این صلوات‌ها رو به نیت کدوم ختم می‌فرسته.
- به محض اینکه خودِ همون کاربر روی یکی از دکمه‌ها بزنه، اون مقدار به ختم
  انتخاب‌شده اضافه می‌شه و پنل حذف می‌شه تا گروه شلوغ نمونه.
"""

import logging
import re
import html

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ReactionEmoji
from telegram.ext import ContextTypes

from database import (
    increment_salavat,
    get_salavat_chat_total,
    get_salavat_global_total,
    get_salavat_global_group_count,
    get_salavat_top,
    create_salavat_goal,
    get_active_goals,
    get_goal_by_id,
    contribute_to_goal,
    delete_goal,
    save_interactive_message,
    delete_interactive_message,
)

logger = logging.getLogger(__name__)

GROUP_CHAT_TYPES = ("group", "supergroup")
MILESTONE_STEP = 50
MAX_SALAVAT_PER_MESSAGE = 1000
MAX_GOALS_IN_PANEL = 8  # اگه ختم‌های فعال خیلی زیاد شدن، پنل رو خیلی بزرگ نکنیم

_SALAVAT_PATTERN = re.compile(r"صلوات")

_SALAVAT_NUMBER_PATTERN = re.compile(
    r"(?:(\d+)\s*(?:تا)?\s*صلوات)|(?:صلوات\s*(?:تا)?\s*(\d+))"
)
_PURE_NUMBER_PATTERN = re.compile(r"^\d{1,4}$")
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


def _extract_pure_number(text: str):
    """اگه کل پیام فقط یه عدد ساده باشه (مثل «50»)، مقدارش رو برمی‌گردونه؛
    وگرنه None. این برای وقتیه که کاربر بدون نوشتن کلمه‌ی «صلوات»، فقط عدد
    صلواتش رو می‌فرسته."""
    normalized = text.strip().translate(_DIGIT_TRANSLATION)
    if not _PURE_NUMBER_PATTERN.match(normalized):
        return None
    amount = int(normalized)
    if amount <= 0:
        return None
    return min(amount, MAX_SALAVAT_PER_MESSAGE)


def _display_name(user) -> str:
    return user.first_name or user.full_name or (f"@{user.username}" if user.username else "کاربر")


def _progress_bar(current: int, goal_count: int, width: int = 10):
    percent = min(100, int(current * 100 / goal_count)) if goal_count else 0
    filled = min(width, percent // (100 // width))
    bar = "🟩" * filled + "⬜️" * (width - filled)
    return bar, percent


def _goal_status_lines(goal) -> str:
    progress = goal["total_contributions"]
    remaining = max(0, goal["goal_count"] - progress)
    bar, percent = _progress_bar(progress, goal["goal_count"])
    safe_title = html.escape(goal["title"])
    return (
        f"<b>🎯 {safe_title}</b>\n"
        f"{bar} {percent}٪\n"
        f"{progress} از {goal['goal_count']} ({remaining} مونده) — "
        f"{goal['participants_count']} نفر شرکت کردن\n"
    )


async def salavat_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    مدیریت پیام‌های حاوی کلمه‌ی صلوات (یا یه عدد ساده، وقتی ختم فعال هست).
    شمارش کلی گروه + باز کردن پنل انتخاب ختم اگه ختم فعالی وجود داشته باشه.
    """
    message = update.message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not message.text or not chat or chat.type not in GROUP_CHAT_TYPES:
        return False

    text = message.text.strip()
    has_keyword = bool(_SALAVAT_PATTERN.search(text))

    if has_keyword:
        amount = _extract_salavat_amount(text)
    else:
        # پیام فقط یه عدد ساده هست؛ فقط وقتی به‌حساب صلوات می‌ذاریمش که
        # الان توی این گروه حداقل یه ختم فعال وجود داشته باشه (وگرنه هر
        # عدد تصادفی توی گروه رو صلوات حساب می‌کردیم).
        pure_amount = _extract_pure_number(text)
        if pure_amount is None or not get_active_goals(chat.id):
            return False
        amount = pure_amount

    user_name = _display_name(user)

    # ری‌اکشن بی‌صدا روی خود پیام (فقط وقتی صریحاً نوشته «صلوات»)
    if has_keyword:
        try:
            await context.bot.set_message_reaction(
                chat_id=chat.id,
                message_id=message.message_id,
                reaction=[ReactionEmoji.PERSON_WITH_FOLDED_HANDS],
            )
        except Exception as e:
            logger.debug(f"عدم امکان ست کردن ری‌اکشن صلوات: {e}")

    # ثبت صلوات در شمارنده‌ی کلی گروه (مستقل از ختم‌ها)
    user_count, chat_total = increment_salavat(chat.id, user.id, user_name, amount)
    prev_total = chat_total - amount

    # پیام تبریک سر رکوردهای رند کلی گروه
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

    # ختم‌های فعال این گروه
    active_goals = get_active_goals(chat.id)
    if not active_goals:
        return True

    active_goals = active_goals[:MAX_GOALS_IN_PANEL]

    keyboard_rows = []
    for goal in active_goals:
        label = f"🎯 {goal['title']} ({goal['total_contributions']}/{goal['goal_count']})"
        callback_data = f"salgoal_{goal['id']}_{amount}_{user.id}"
        keyboard_rows.append([InlineKeyboardButton(label, callback_data=callback_data)])
    keyboard_rows.append(
        [InlineKeyboardButton("↩️ فقط شمارش کلی (بدون ختم)", callback_data=f"salskip_{user.id}")]
    )

    safe_name = html.escape(user_name)
    panel_text = f"🌹 {safe_name} عزیز، این {amount} صلوات رو به نیت کدوم ختم می‌فرستی؟\n\n"
    for goal in active_goals:
        panel_text += _goal_status_lines(goal) + "\n"

    try:
        sent = await message.reply_text(
            panel_text,
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
            parse_mode="HTML",
        )
        save_interactive_message(chat.id, sent.message_id, user.id, None, "salavat_panel")
    except Exception as e:
        logger.error(f"خطا در نمایش پنل انتخاب ختم صلوات (چت {chat.id}): {e}")

    return True


async def salavat_goal_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ به تیک زدنِ کاربر روی یکی از دکمه‌های پنل انتخاب ختم."""
    query = update.callback_query
    if not query or not query.data:
        return

    chat = update.effective_chat
    clicking_user = update.effective_user
    data = query.data

    # --- گزینه‌ی «فقط شمارش کلی» ---
    if data.startswith("salskip_"):
        owner_id_str = data.split("_", 1)[1]
        if str(clicking_user.id) != owner_id_str:
            await query.answer("این پنل برای شما نیست 🙏", show_alert=True)
            return

        await query.answer("باشه، فقط توی شمارش کلی گروه ثبت موند 🌹")
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"عدم امکان حذف پنل صلوات: {e}")
        delete_interactive_message(chat.id, query.message.message_id)
        return

    # --- انتخاب یکی از ختم‌ها ---
    if not data.startswith("salgoal_"):
        await query.answer()
        return

    try:
        _, goal_id_str, amount_str, owner_id_str = data.split("_")
        goal_id = int(goal_id_str)
        amount = int(amount_str)
    except (ValueError, IndexError):
        await query.answer("خطای داخلی، لطفاً دوباره یه صلوات بفرست.", show_alert=True)
        return

    if str(clicking_user.id) != owner_id_str:
        await query.answer(
            "این پنل برای شما نیست 🙏 خودت هم یه صلوات بفرست تا ختمت رو انتخاب کنی!",
            show_alert=True,
        )
        return

    user_name = _display_name(clicking_user)
    result = contribute_to_goal(goal_id, clicking_user.id, user_name, amount)
    goal = result["goal"]

    if not goal:
        await query.answer("این ختم دیگه وجود نداره یا حذف شده.", show_alert=True)
        try:
            await query.message.delete()
        except Exception:
            pass
        delete_interactive_message(chat.id, query.message.message_id)
        return

    safe_title = html.escape(goal["title"])
    await query.answer(f"✅ {amount} صلوات به ختم «{goal['title']}» اضافه شد 🌹")

    try:
        await query.message.delete()
    except Exception as e:
        logger.debug(f"عدم امکان حذف پنل صلوات: {e}")
    delete_interactive_message(chat.id, query.message.message_id)

    if result["completed"]:
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


async def salavat_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /salavat -- نمایش مجموع گروه، همه‌ی ختم‌های فعال، و نفرات برتر"""
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

    # همه‌ی ختم‌های فعال
    active_goals = get_active_goals(chat.id)
    if active_goals:
        text += f"\n🎯 <b>ختم‌های فعال ({len(active_goals)}):</b>\n\n"
        for goal in active_goals:
            text += _goal_status_lines(goal) + "\n"
    else:
        text += "\nختم فعالی این لحظه نیست. یه ادمین می‌تونه با /salavat_goal یکی شروع کنه.\n"

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
    """دستور /salavat_goal N عنوان -- (فقط ادمین) شروع یه ختم جدید.

    چند ختم می‌تونن هم‌زمان فعال باشن؛ این دستور فقط ختمِ قبلی رو
    متوقف نمی‌کنه، یه ختمِ جدید بهش اضافه می‌کنه."""
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
            "می‌تونید هم‌زمان چند ختم فعال داشته باشید؛ هر بار کسی صلوات بفرسته، "
            "ازش می‌پرسیم به نیت کدوم ختم بوده.",
            parse_mode="HTML",
        )
        return

    goal_count = int(args[0])
    if goal_count <= 0:
        await update.message.reply_text("⚠️ عدد هدف باید بزرگ‌تر از صفر باشه.")
        return

    title = " ".join(args[1:]).strip() or "بدون عنوان"

    # جلوگیری از دو ختمِ فعال با عنوان یکسان توی یه گروه
    if any(g["title"] == title for g in get_active_goals(chat.id)):
        await update.message.reply_text(
            "⚠️ یه ختم فعال با همین عنوان از قبل توی این گروه هست. لطفاً یه عنوان دیگه انتخاب کن."
        )
        return

    create_salavat_goal(chat.id, goal_count, title, created_by=user.id)

    active_count = len(get_active_goals(chat.id))
    safe_title = html.escape(title)
    await update.message.reply_text(
        f"🎯 ختم صلوات جدید شروع شد!\n\n"
        f"<b>عنوان:</b> {safe_title}\n"
        f"<b>هدف:</b> {goal_count} صلوات\n\n"
        f"الان این گروه <b>{active_count}</b> ختم فعال داره. هرکس توی گروه بنویسه «صلوات» "
        f"(یا حتی فقط یه عدد بفرسته)، ازش می‌پرسیم این صلوات‌ها به نیت کدوم ختم بوده. "
        f"وضعیت همه‌ی ختم‌ها رو با /salavat می‌تونید ببینید.",
        parse_mode="HTML",
    )


async def salavat_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /salavat_delete -- (فقط ادمین) نمایش لیست ختم‌های فعال با
    دکمه‌ی حذف برای هرکدوم."""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in GROUP_CHAT_TYPES:
        await update.message.reply_text("🌹 این دستور فقط داخل گروه‌ها کار می‌کنه.")
        return

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        is_admin = member.status in ("administrator", "creator")
    except Exception as e:
        logger.error(f"خطا در بررسی ادمین بودن برای حذف ختم صلوات: {e}")
        is_admin = False

    if not is_admin:
        await update.message.reply_text("⛔ فقط ادمین‌های گروه می‌تونن ختم حذف کنن.")
        return

    active_goals = get_active_goals(chat.id)
    if not active_goals:
        await update.message.reply_text("در حال حاضر هیچ ختم فعالی توی این گروه نیست.")
        return

    keyboard_rows = []
    for goal in active_goals:
        label = f"🗑 {goal['title']} ({goal['total_contributions']}/{goal['goal_count']})"
        callback_data = f"salrm_{goal['id']}_{user.id}"
        keyboard_rows.append([InlineKeyboardButton(label, callback_data=callback_data)])
    keyboard_rows.append(
        [InlineKeyboardButton("↩️ انصراف", callback_data=f"salrmcancel_{user.id}")]
    )

    await update.message.reply_text(
        "کدوم ختم رو می‌خوای حذف کنی؟\n⚠️ این کار قابل بازگشت نیست و همه‌ی مشارکت‌های ثبت‌شده توی این ختم هم پاک می‌شن.",
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
    )


async def salavat_delete_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ به تیک زدنِ ادمین روی یکی از دکمه‌های پنل حذف ختم."""
    query = update.callback_query
    if not query or not query.data:
        return

    chat = update.effective_chat
    clicking_user = update.effective_user
    data = query.data

    # --- انصراف ---
    if data.startswith("salrmcancel_"):
        owner_id_str = data.split("_", 1)[1]
        if str(clicking_user.id) != owner_id_str:
            await query.answer("این پنل برای شما نیست 🙏", show_alert=True)
            return
        await query.answer("باشه، لغو شد.")
        try:
            await query.message.delete()
        except Exception as e:
            logger.debug(f"عدم امکان حذف پنل حذف ختم: {e}")
        return

    # --- انتخاب یکی از ختم‌ها برای حذف ---
    if not data.startswith("salrm_"):
        await query.answer()
        return

    try:
        _, goal_id_str, owner_id_str = data.split("_")
        goal_id = int(goal_id_str)
    except (ValueError, IndexError):
        await query.answer("خطای داخلی، لطفاً دوباره /salavat_delete رو بزن.", show_alert=True)
        return

    if str(clicking_user.id) != owner_id_str:
        await query.answer("این پنل برای شما نیست 🙏 فقط کسی که دستور رو زده می‌تونه انتخاب کنه.", show_alert=True)
        return

    # چون حذف برگشت‌ناپذیره، ادمین بودن رو دوباره در لحظه‌ی کلیک هم چک می‌کنیم
    try:
        member = await context.bot.get_chat_member(chat.id, clicking_user.id)
        is_admin = member.status in ("administrator", "creator")
    except Exception as e:
        logger.error(f"خطا در بررسی مجدد ادمین بودن برای حذف ختم صلوات: {e}")
        is_admin = False

    if not is_admin:
        await query.answer("⛔ فقط ادمین‌های گروه می‌تونن ختم حذف کنن.", show_alert=True)
        return

    goal = get_goal_by_id(goal_id)
    if not goal:
        await query.answer("این ختم قبلاً حذف شده.", show_alert=True)
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    delete_goal(goal_id)
    safe_title = html.escape(goal["title"])

    await query.answer(f"🗑 ختم «{goal['title']}» حذف شد.")
    try:
        await query.message.edit_text(f"🗑 ختم «{safe_title}» حذف شد.", parse_mode="HTML")
    except Exception as e:
        logger.debug(f"عدم امکان ویرایش پیام بعد از حذف ختم: {e}")


async def salavat_global_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /salavat_global -- نمایش مجموع کل صلوات‌های فرستاده‌شده توی
    همه‌ی گروه‌هایی که ربات عضوشونه (هم توی پیوی و هم توی گروه کار می‌کنه)."""
    total = get_salavat_global_total()
    group_count = get_salavat_global_group_count()

    text = (
        f"🌹 <b>مجموع کل صلوات‌ها</b>\n\n"
        f"تا الان توی مجموع <b>{group_count}</b> گروه، "
        f"<b>{total}</b> صلوات فرستاده شده 🤲"
    )
    await update.message.reply_text(text, parse_mode="HTML")


