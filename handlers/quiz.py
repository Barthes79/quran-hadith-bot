import re
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from text_utils import normalize_input_text
from database import (
    get_random_quiz_question, get_quiz_question_by_id, count_quiz_questions,
    add_score, get_leaderboard, get_global_leaderboard,
    add_quiz_question, record_quiz_result, get_user_quiz_stats, award_badge,
)

# ---------------- تنظیمات کلی ----------------

QUIZ_ANSWERS = {}  # key=(chat_id, message_id) -> اطلاعات دور جاری کوییز

CATEGORIES = {
    "quran": "📖 قرآن",
    "nahj": "🕋 نهج‌البلاغه",
    "hadith": "🗣 احادیث",
    "general": "🌍 عمومی",
}

CATEGORY_FA_TO_KEY = {
    "قرآن": "quran",
    "نهج البلاغه": "nahj",
    "نهج‌البلاغه": "nahj",
    "احادیث": "hadith",
    "حدیث": "hadith",
    "عمومی": "general",
}

DIFFICULTY_INFO = {
    "easy":   {"label": "🟢 آسان",  "points": 1, "time": 25},
    "medium": {"label": "🟡 متوسط", "points": 2, "time": 20},
    "hard":   {"label": "🔴 سخت",   "points": 3, "time": 15},
}

DIFFICULTY_FA_TO_KEY = {
    "آسان": "easy",
    "متوسط": "medium",
    "سخت": "hard",
}

OPTION_MARK = {"a": "🔵", "b": "🟢", "c": "🟠", "d": "🟣"}
OPTION_LETTER_FA = {"a": "الف", "b": "ب", "c": "ج", "d": "د"}

SPEED_BONUS_POINTS = 1
WARNING_SECONDS_BEFORE_END = 5

# ---------------- تعریف نشان‌ها ----------------

BADGES = {
    "streak_5":     {"emoji": "🔥", "title": "شعله‌ی پیروزی",   "desc": "۵ پاسخ درست پشت‌سرهم"},
    "streak_10":    {"emoji": "⚡", "title": "برق‌آسا",         "desc": "۱۰ پاسخ درست پشت‌سرهم"},
    "correct_10":   {"emoji": "🥉", "title": "مبتدی",           "desc": "۱۰ پاسخ درست"},
    "correct_50":   {"emoji": "🥈", "title": "آشنا",            "desc": "۵۰ پاسخ درست"},
    "correct_150":  {"emoji": "🥇", "title": "استاد کوییز",     "desc": "۱۵۰ پاسخ درست"},
    "cat_quran_20":  {"emoji": "📖", "title": "حافظ قرآن",        "desc": "۲۰ پاسخ درست در دسته‌ی قرآن"},
    "cat_nahj_20":   {"emoji": "🕋", "title": "راوی نهج‌البلاغه", "desc": "۲۰ پاسخ درست در دسته‌ی نهج‌البلاغه"},
    "cat_hadith_20": {"emoji": "🗣", "title": "محدث",             "desc": "۲۰ پاسخ درست در دسته‌ی احادیث"},
}


def _check_new_badges(user_id: int, stats: dict, category: str):
    """با توجه به آمار به‌روزشده‌ی کاربر، نشان‌های تازه را ثبت و برمی‌گرداند."""
    newly_awarded = []

    for threshold, key in [(10, "correct_10"), (50, "correct_50"), (150, "correct_150")]:
        if stats.get("total_correct", 0) >= threshold and award_badge(user_id, key):
            newly_awarded.append(key)

    for threshold, key in [(5, "streak_5"), (10, "streak_10")]:
        if stats.get("current_streak", 0) >= threshold and award_badge(user_id, key):
            newly_awarded.append(key)

    cat_key = f"cat_{category}_20"
    if category in ("quran", "nahj", "hadith") and stats.get("category_correct", 0) >= 20:
        if cat_key in BADGES and award_badge(user_id, cat_key):
            newly_awarded.append(cat_key)

    return newly_awarded


# ---------------- منوی انتخاب دسته ----------------

def quiz_menu_keyboard():
    buttons = []
    row = []
    for key, label in CATEGORIES.items():
        row.append(InlineKeyboardButton(label, callback_data=f"quizcat_{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🎲 تصادفی از همه‌ی دسته‌ها", callback_data="quizcat_random")])
    return InlineKeyboardMarkup(buttons)


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎮 کوییز مسابقه‌ای\n\n"
        "یک دسته انتخاب کن یا تصادفی بازی کن.\n"
        "هرچی سریع‌تر و دقیق‌تر جواب بدی، امتیاز بیشتری می‌گیری! 🏆"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=quiz_menu_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=quiz_menu_keyboard())


async def quiz_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await quiz_command(update, context)


async def quiz_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.replace("quizcat_", "")
    await start_quiz(update, context, category)


# ---------------- شروع یک دور کوییز ----------------

def quiz_keyboard(qid: int, row):
    buttons = [
        [InlineKeyboardButton(f"{OPTION_MARK['a']} {row['option_a']}", callback_data=f"quizans_{qid}_a")],
        [InlineKeyboardButton(f"{OPTION_MARK['b']} {row['option_b']}", callback_data=f"quizans_{qid}_b")],
        [InlineKeyboardButton(f"{OPTION_MARK['c']} {row['option_c']}", callback_data=f"quizans_{qid}_c")],
        [InlineKeyboardButton(f"{OPTION_MARK['d']} {row['option_d']}", callback_data=f"quizans_{qid}_d")],
    ]
    return InlineKeyboardMarkup(buttons)


async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    query = update.callback_query
    chat = update.effective_chat

    lookup_category = None if category == "random" else category
    row = get_random_quiz_question(lookup_category)

    if not row:
        msg = "😕 هنوز سوالی در این دسته ثبت نشده. یه دسته‌ی دیگه رو امتحان کن."
        if query:
            await query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(msg)
        return

    difficulty = row["difficulty"] if row["difficulty"] in DIFFICULTY_INFO else "medium"
    info = DIFFICULTY_INFO[difficulty]
    time_limit = info["time"]
    cat_label = CATEGORIES.get(row["category"], CATEGORIES["general"])

    text = (
        f"{cat_label}  |  {info['label']}  |  ⏱ {time_limit} ثانیه  |  🎯 {info['points']} امتیاز\n"
        "──────────────\n\n"
        f"❓ {row['question_text']}\n\n"
        "زودتر از بقیه جواب درست بده تا امتیاز سرعت هم بگیری! ⚡"
    )
    markup = quiz_keyboard(row["id"], row)

    if query:
        sent_msg = await query.edit_message_text(text, reply_markup=markup)
        chat_id = query.message.chat.id
        message_id = query.message.message_id
    else:
        sent_msg = await update.message.reply_text(text, reply_markup=markup)
        chat_id = chat.id
        message_id = sent_msg.message_id

    key = (chat_id, message_id)
    QUIZ_ANSWERS[key] = {
        "qid": row["id"],
        "row": row,
        "category": row["category"] or "general",
        "difficulty": difficulty,
        "time_limit": time_limit,
        "start": time.time(),
        "text": text,
        "answers": {},
    }

    context.job_queue.run_once(
        finish_quiz,
        time_limit,
        data={"chat_id": chat_id, "message_id": message_id},
    )

    if time_limit > WARNING_SECONDS_BEFORE_END:
        context.job_queue.run_once(
            warn_time_running_out,
            time_limit - WARNING_SECONDS_BEFORE_END,
            data={"chat_id": chat_id, "message_id": message_id},
        )


async def warn_time_running_out(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    key = (data["chat_id"], data["message_id"])
    quiz = QUIZ_ANSWERS.get(key)
    if not quiz:
        return
    answered_count = len(quiz["answers"])
    try:
        await context.bot.edit_message_text(
            chat_id=data["chat_id"],
            message_id=data["message_id"],
            text=(
                f"{quiz['text']}\n\n"
                f"⏳ فقط {WARNING_SECONDS_BEFORE_END} ثانیه مونده! "
                f"({answered_count} نفر تا الان جواب دادن)"
            ),
            reply_markup=quiz_keyboard(quiz["qid"], quiz["row"]),
        )
    except Exception:
        pass


async def quiz_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    key = (query.message.chat.id, query.message.message_id)

    quiz = QUIZ_ANSWERS.get(key)
    if not quiz:
        await query.answer("⏰ زمان پاسخ‌گویی تمام شده است.", show_alert=True)
        return

    _, qid, chosen = query.data.split("_")
    user = query.from_user

    if user.id in quiz["answers"]:
        await query.answer("قبلاً جواب دادی! ⏳ منتظر پایان زمان بمون.")
        return

    username = user.username or user.first_name or "ناشناس"
    quiz["answers"][user.id] = {
        "username": username,
        "chosen": chosen,
        "elapsed": time.time() - quiz["start"],
    }

    await query.answer("✅ جواب شما ثبت شد! نتیجه در پایان زمان اعلام می‌شود.")


# ---------------- پایان دور و اعلام نتیجه ----------------

async def finish_quiz(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    key = (data["chat_id"], data["message_id"])

    quiz = QUIZ_ANSWERS.pop(key, None)
    if not quiz:
        return

    row = get_quiz_question_by_id(quiz["qid"])
    if not row:
        return

    category = quiz["category"]
    difficulty = quiz["difficulty"]
    time_limit = quiz["time_limit"]
    base_points = DIFFICULTY_INFO[difficulty]["points"]

    correct_lines = []
    wrong_lines = []
    badge_lines = []

    for uid, ans in quiz["answers"].items():
        is_correct = ans["chosen"] == row["correct_option"]
        points = 0

        if is_correct:
            points = base_points
            speed_bonus = ans["elapsed"] <= time_limit / 2
            if speed_bonus:
                points += SPEED_BONUS_POINTS
            add_score(data["chat_id"], uid, ans["username"], points=points)
            bonus_tag = " ⚡" if speed_bonus else ""
            correct_lines.append(f"✅ {ans['username']} (+{points}{bonus_tag})")
        else:
            wrong_lines.append(f"❌ {ans['username']}")

        stats_after = record_quiz_result(
            data["chat_id"], uid, ans["username"], category, is_correct, points
        )
        new_badges = _check_new_badges(uid, stats_after, category)
        for bkey in new_badges:
            b = BADGES[bkey]
            badge_lines.append(f"{b['emoji']} {ans['username']} نشان «{b['title']}» رو گرفت!")

    option_map = OPTION_LETTER_FA
    correct_text_map = {
        "a": row["option_a"], "b": row["option_b"],
        "c": row["option_c"], "d": row["option_d"],
    }

    result_text = (
        "⏰ زمان تمام شد!\n\n"
        f"❓ {row['question_text']}\n\n"
        f"📌 پاسخ صحیح: {option_map[row['correct_option']]}) {correct_text_map[row['correct_option']]}\n\n"
        f"{chr(10).join(correct_lines) if correct_lines else '— هیچ‌کس جواب درست نداد —'}\n"
        f"{chr(10).join(wrong_lines) if wrong_lines else ''}"
    ).strip()

    if badge_lines:
        result_text += "\n\n🏅 نشان‌های جدید:\n" + "\n".join(badge_lines)

    buttons = [[InlineKeyboardButton("🔁 سوال بعدی", callback_data=f"quizcat_{category}")]]

    await context.bot.edit_message_text(
        chat_id=data["chat_id"],
        message_id=data["message_id"],
        text=result_text,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ---------------- لیدربوردها ----------------

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_leaderboard(update.effective_chat.id)
    if not rows:
        await update.message.reply_text(
            "هنوز کسی در این گروه امتیازی کسب نکرده است.\n"
            "با /quiz یک دور کوییز شروع کن! 🎮"
        )
        return

    lines = ["🏆 جدول امتیازات این گروه:\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows):
        prefix = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{prefix} {row['username']} — {row['score']} امتیاز")
    lines.append("\n🌍 برای رتبه‌بندی سراسری از /quizrank استفاده کن.")

    await update.message.reply_text("\n".join(lines))


async def global_leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_global_leaderboard()
    if not rows:
        await update.message.reply_text("هنوز کسی در رتبه‌بندی سراسری امتیازی کسب نکرده است.")
        return

    lines = ["🌍 رتبه‌بندی سراسری کوییز (همه‌ی گروه‌ها):\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows):
        prefix = medals[i] if i < 3 else f"{i+1}."
        accuracy = (
            round(100 * row["total_correct"] / row["total_answered"])
            if row["total_answered"] else 0
        )
        lines.append(
            f"{prefix} {row['username'] or 'ناشناس'} — {row['total_points']} امتیاز "
            f"({row['total_correct']} درست، دقت {accuracy}٪)"
        )

    await update.message.reply_text("\n".join(lines))


async def my_quiz_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = get_user_quiz_stats(user.id)
    stats = data["stats"]

    if not stats or stats["total_answered"] == 0:
        await update.message.reply_text(
            "هنوز در هیچ کوییزی شرکت نکرده‌ای!\nبا /quiz شروع کن 🎮"
        )
        return

    accuracy = round(100 * stats["total_correct"] / stats["total_answered"]) if stats["total_answered"] else 0

    lines = [
        f"📊 آمار کوییز {user.first_name}:\n",
        f"🎯 امتیاز کل: {stats['total_points']}",
        f"✅ پاسخ درست: {stats['total_correct']} از {stats['total_answered']} (دقت {accuracy}٪)",
        f"🔥 بهترین رکورد پشت‌سرهم: {stats['best_streak']}",
    ]

    if data["categories"]:
        lines.append("\n📚 عملکرد به تفکیک دسته:")
        for cat, cnt in data["categories"].items():
            label = CATEGORIES.get(cat, cat)
            lines.append(f"  {label}: {cnt} پاسخ درست")

    if data["badges"]:
        lines.append("\n🏅 نشان‌ها:")
        for bkey in data["badges"]:
            b = BADGES.get(bkey)
            if b:
                lines.append(f"  {b['emoji']} {b['title']} — {b['desc']}")
    else:
        lines.append("\n🏅 هنوز نشانی نگرفته‌ای. ادامه بده تا نشان بگیری!")

    await update.message.reply_text("\n".join(lines))


# ---------------- دستور ادمین برای افزودن سوال مسابقه ----------------
# فرمت:
# /addquiz
# سوال: نام کتاب مقدس مسلمانان چیست؟
# الف: تورات
# ب: قرآن
# ج: انجیل
# د: زبور
# پاسخ: ب
# دسته: قرآن        (اختیاری — قرآن / نهج‌البلاغه / احادیث / عمومی — پیش‌فرض: عمومی)
# سطح: متوسط        (اختیاری — آسان / متوسط / سخت — پیش‌فرض: متوسط)

async def add_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه‌ی این دستور را ندارید.")
        return

    full_text = update.message.text.split(" ", 1)
    if len(full_text) < 2:
        await update.message.reply_text(
            "فرمت صحیح استفاده:\n\n"
            "/addquiz\n"
            "سوال: ...\n"
            "الف: ...\n"
            "ب: ...\n"
            "ج: ...\n"
            "د: ...\n"
            "پاسخ: الف (یا ب، ج، د)\n"
            "دسته: قرآن (اختیاری - قرآن/نهج‌البلاغه/احادیث/عمومی)\n"
            "سطح: متوسط (اختیاری - آسان/متوسط/سخت)"
        )
        return

    body = normalize_input_text(full_text[1])
    field_labels = ["سوال", "الف", "ب", "ج", "د", "پاسخ", "دسته", "سطح"]
    pattern = r"(?=(?:" + "|".join(field_labels) + r")\s*:)"
    chunks = re.split(pattern, body.strip())

    fields = {}
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        key, value = chunk.split(":", 1)
        key = key.strip()
        if key in field_labels:
            fields[key] = value.strip()

    question = fields.get("سوال", "")
    option_a = fields.get("الف", "")
    option_b = fields.get("ب", "")
    option_c = fields.get("ج", "")
    option_d = fields.get("د", "")
    answer_raw = fields.get("پاسخ", "").strip()

    letter_map = {"الف": "a", "ب": "b", "ج": "c", "د": "d",
                  "a": "a", "b": "b", "c": "c", "d": "d"}
    correct_option = letter_map.get(answer_raw)

    if not all([question, option_a, option_b, option_c, option_d, correct_option]):
        await update.message.reply_text(
            "همه‌ی فیلدها (سوال، الف، ب، ج، د، پاسخ) الزامی هستند و پاسخ باید "
            "یکی از حروف الف/ب/ج/د باشد."
        )
        return

    category = CATEGORY_FA_TO_KEY.get(fields.get("دسته", "").strip(), "general")
    difficulty = DIFFICULTY_FA_TO_KEY.get(fields.get("سطح", "").strip(), "medium")

    qid = add_quiz_question(
        question, option_a, option_b, option_c, option_d, correct_option,
        category=category, difficulty=difficulty,
    )
    await update.message.reply_text(
        f"✅ سوال با شناسه {qid} ثبت شد.\n"
        f"دسته: {CATEGORIES.get(category)} | سطح: {DIFFICULTY_INFO[difficulty]['label']}"
    )
