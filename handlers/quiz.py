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
    get_group_settings, update_group_settings,
)

# ---------------- تنظیمات کلی ----------------

QUIZ_ANSWERS = {}  # key=(chat_id, message_id) -> اطلاعات دور جاری کوییز
NORMAL_SESSIONS = {}  # chat_id -> {"total": int, "asked_count": int, "asked_ids": set}

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

MIN_CUSTOM_TIME = 5
MAX_CUSTOM_TIME = 120
MIN_NEXT_DELAY = 2
MAX_NEXT_DELAY = 30
DEFAULT_NEXT_DELAY = 5
MIN_BUZZER_COUNT = 1
MAX_BUZZER_COUNT = 100

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


def _get_quiz_settings(chat_id: int):
    row = get_group_settings(chat_id)
    custom_time = row["quiz_custom_time"] if row["quiz_custom_time"] else None
    buzzer_mode = bool(row["quiz_buzzer_mode"])
    next_delay = row["quiz_buzzer_next_delay"] if row["quiz_buzzer_next_delay"] else DEFAULT_NEXT_DELAY
    return {"custom_time": custom_time, "buzzer_mode": buzzer_mode, "next_delay": next_delay}


# ---------------- سشن دوره‌ی زنگ‌اول (تعداد سوال + جلوگیری از تکرار) ----------------
# این حالت فقط در حافظه نگه‌داری می‌شود (با ری‌استارت ربات، سشن‌های فعال پاک می‌شوند)

BUZZER_SESSIONS = {}  # chat_id -> {"total": int|None, "asked_count": int, "asked_ids": set}


def _start_buzzer_session(chat_id: int, total: int = None):
    BUZZER_SESSIONS[chat_id] = {"total": total, "asked_count": 0, "asked_ids": set()}


def _end_buzzer_session(chat_id: int):
    BUZZER_SESSIONS.pop(chat_id, None)
    update_group_settings(chat_id, quiz_buzzer_mode=0)


def _pick_question_for_round(chat_id: int, category: str, session: dict):
    """سوال بعدی را انتخاب می‌کند؛ اگر سشن فعال باشد، از تکرار سوالات قبلی جلوگیری می‌کند."""
    lookup_category = None if category == "random" else category
    exclude_ids = list(session["asked_ids"]) if session else None
    row = get_random_quiz_question(lookup_category, exclude_ids=exclude_ids)
    reset_notice = None
    if not row and exclude_ids:
        # همه‌ی سوالات این دسته یک‌بار پرسیده شده‌اند؛ از اول شروع می‌کنیم
        session["asked_ids"].clear()
        row = get_random_quiz_question(lookup_category)
        if row:
            reset_notice = "🔁 همه‌ی سوالات این دسته یک‌بار پرسیده شد؛ تکرار از اول."
    return row, reset_notice


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


def _build_question_payload(row, settings: dict, progress=None):
    difficulty = row["difficulty"] if row["difficulty"] in DIFFICULTY_INFO else "medium"
    info = DIFFICULTY_INFO[difficulty]
    time_limit = settings["custom_time"] or info["time"]
    cat_label = CATEGORIES.get(row["category"], CATEGORIES["general"])

    header = f"{cat_label}  |  {info['label']}  |  ⏱ {time_limit} ثانیه  |  🎯 {info['points']} امتیاز"
    if progress and progress[1]:
        header += f"\n📍 سوال {progress[0]} از {progress[1]}"
    if settings["buzzer_mode"]:
        header += "\n🔔 حالت زنگ‌اول فعال است"
        footer = "اولین نفری که درست جواب بده، همه‌ی امتیاز این سوال رو می‌بره! 🔔"
    else:
        footer = "زودتر از بقیه جواب درست بده تا امتیاز سرعت هم بگیری! ⚡"

    text = f"{header}\n──────────────\n\n❓ {row['question_text']}\n\n{footer}"
    markup = quiz_keyboard(row["id"], row)
    return text, markup, time_limit, difficulty


def _prepare_next_question(chat_id: int, category: str, context=None):
    """سوال بعدی را با توجه به تنظیمات و سشن فعلی (تعداد باقی‌مانده و عدم تکرار) آماده می‌کند."""
    settings = _get_quiz_settings(chat_id)
    session = None
    
    # اگر حالت زنگ‌اول فعاله، از سشن زنگ‌اول استفاده کن
    if settings["buzzer_mode"]:
        if chat_id not in BUZZER_SESSIONS:
            _start_buzzer_session(chat_id, total=None)
        session = BUZZER_SESSIONS[chat_id]
    
    # اگر حالت معمولی و تعداد سوال مشخص شده، یه سشن موقت بساز
    if not settings["buzzer_mode"] and context and context.chat_data.get('normal_quiz_count'):
        total = context.chat_data.get('normal_quiz_count')
        if chat_id not in NORMAL_SESSIONS:
            NORMAL_SESSIONS[chat_id] = {"total": total, "asked_count": 0, "asked_ids": set()}
        session = NORMAL_SESSIONS[chat_id]

    row, reset_notice = _pick_question_for_round(chat_id, category, session)
    if not row:
        return None

    is_last = False
    progress = None
    if session is not None:
        session["asked_ids"].add(row["id"])
        session["asked_count"] += 1
        progress = (session["asked_count"], session["total"])
        if session["total"] is not None and session["asked_count"] >= session["total"]:
            is_last = True
            # بعد از آخرین سوال، سشن رو پاک کن
            if not settings["buzzer_mode"] and chat_id in NORMAL_SESSIONS:
                del NORMAL_SESSIONS[chat_id]

    text, markup, time_limit, difficulty = _build_question_payload(row, settings, progress=progress)
    if reset_notice:
        text = f"{reset_notice}\n\n{text}"

    return {
        "row": row, "text": text, "markup": markup, "time_limit": time_limit,
        "difficulty": difficulty, "settings": settings, "is_last": is_last,
    }


def _register_round(context, chat_id, message_id, row, category, difficulty, time_limit, text, settings, session_last=False):
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
        "buzzer_mode": settings["buzzer_mode"],
        "buzzer_next_delay": settings["next_delay"],
        "session_last": session_last,
        "finish_job": None,
        "warn_job": None,
    }

    finish_job = context.job_queue.run_once(
        finish_quiz,
        time_limit,
        data={"chat_id": chat_id, "message_id": message_id},
    )
    QUIZ_ANSWERS[key]["finish_job"] = finish_job

    if time_limit > WARNING_SECONDS_BEFORE_END:
        warn_job = context.job_queue.run_once(
            warn_time_running_out,
            time_limit - WARNING_SECONDS_BEFORE_END,
            data={"chat_id": chat_id, "message_id": message_id},
        )
        QUIZ_ANSWERS[key]["warn_job"] = warn_job


async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    query = update.callback_query
    chat = update.effective_chat

    prep = _prepare_next_question(chat.id, category, context)

    if not prep:
        msg = "😕 هنوز سوالی در این دسته ثبت نشده (یا همه‌ی سوالات این دوره تمام شده). یه دسته‌ی دیگه رو امتحان کن."
        if query:
            await query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(msg)
        return

    if query:
        await query.edit_message_text(prep["text"], reply_markup=prep["markup"])
        chat_id = query.message.chat.id
        message_id = query.message.message_id
    else:
        sent_msg = await update.message.reply_text(prep["text"], reply_markup=prep["markup"])
        chat_id = chat.id
        message_id = sent_msg.message_id

    _register_round(
        context, chat_id, message_id, prep["row"], category, prep["difficulty"],
        prep["time_limit"], prep["text"], prep["settings"], session_last=prep["is_last"],
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


async def _auto_next_question(context: ContextTypes.DEFAULT_TYPE):
    """در حالت زنگ‌اول، بعد از پایان هر دور، این تابع سوال بعدی را خودکار می‌فرستد."""
    data = context.job.data
    chat_id = data["chat_id"]
    message_id = data["message_id"]
    category = data["category"]

    settings = _get_quiz_settings(chat_id)
    if not settings["buzzer_mode"]:
        return  # ادمین در همین فاصله حالت زنگ‌اول را خاموش کرده

    prep = _prepare_next_question(chat_id, category, None)
    if not prep:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id,
                text="😕 سوال دیگری در این دسته باقی نمانده.",
            )
        except Exception:
            pass
        return

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=message_id, text=prep["text"], reply_markup=prep["markup"],
        )
    except Exception:
        return

    _register_round(
        context, chat_id, message_id, prep["row"], category, prep["difficulty"],
        prep["time_limit"], prep["text"], prep["settings"], session_last=prep["is_last"],
    )


async def _finish_round_message(context, chat_id, message_id, category, next_delay, session_last, base_text):
    """پیام پایان دور را ادیت می‌کند؛ اگر آخرین سوال دوره بود، دوره را جمع‌بندی و متوقف می‌کند
    وگرنه سوال بعدی را خودکار زمان‌بندی می‌کند."""
    text = base_text
    if session_last:
        _end_buzzer_session(chat_id)
        text += "\n\n🏁 این دوره‌ی زنگ‌اول به پایان رسید!"
        top = get_leaderboard(chat_id, limit=3)
        if top:
            medals = ["🥇", "🥈", "🥉"]
            text += "\n\n🏆 برترین‌های این گروه تا الان:\n"
            text += "\n".join(f"{medals[i]} {r['username']} — {r['score']} امتیاز" for i, r in enumerate(top))
        text += "\n\nبرای شروع دوره‌ی جدید: مسابقه سرعتی <تعداد سوال>"
    else:
        text += f"\n\n⏭ سوال بعدی تا {next_delay} ثانیه‌ی دیگر..."

    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)
    except Exception:
        pass

    if not session_last:
        context.job_queue.run_once(
            _auto_next_question,
            next_delay,
            data={"chat_id": chat_id, "message_id": message_id, "category": category},
        )


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
    elapsed = time.time() - quiz["start"]
    quiz["answers"][user.id] = {"username": username, "chosen": chosen, "elapsed": elapsed}

    is_correct = chosen == quiz["row"]["correct_option"]

    if quiz["buzzer_mode"] and is_correct:
        await query.answer("🔔 آفرین! تو زودتر از همه جواب درست دادی!", show_alert=True)
        await _settle_buzzer_win(context, key, user.id, username)
        return

    await query.answer("✅ جواب شما ثبت شد! نتیجه در پایان زمان اعلام می‌شود.")


async def _settle_buzzer_win(context: ContextTypes.DEFAULT_TYPE, key, uid: int, username: str):
    """اولین پاسخ درست در حالت زنگ‌اول: سوال را قفل، امتیاز را اعلام و سوال بعدی را زمان‌بندی می‌کند."""
    quiz = QUIZ_ANSWERS.pop(key, None)
    if not quiz:
        return  # یک کاربر دیگر لحظه‌ای زودتر برنده اعلام شده

    for job in (quiz.get("finish_job"), quiz.get("warn_job")):
        if job:
            try:
                job.schedule_removal()
            except Exception:
                pass

    row = quiz["row"]
    category = quiz["category"]
    difficulty = quiz["difficulty"]
    base_points = DIFFICULTY_INFO[difficulty]["points"]
    points = base_points + SPEED_BONUS_POINTS

    chat_id, message_id = key
    add_score(chat_id, uid, username, points=points)
    stats_after = record_quiz_result(chat_id, uid, username, category, True, points)
    new_badges = _check_new_badges(uid, stats_after, category)

    option_map = OPTION_LETTER_FA
    correct_text_map = {
        "a": row["option_a"], "b": row["option_b"],
        "c": row["option_c"], "d": row["option_d"],
    }
    others = [a["username"] for u, a in quiz["answers"].items() if u != uid]

    result_text = (
        "🔔 قفل شد! یک نفر زودتر از همه جواب درست داد!\n\n"
        f"❓ {row['question_text']}\n\n"
        f"🏆 برنده: {username} (+{points} امتیاز) ⚡\n"
        f"📌 پاسخ صحیح: {option_map[row['correct_option']]}) "
        f"{correct_text_map[row['correct_option']]}"
    )
    if others:
        result_text += f"\n\n🙋 بقیه‌ای که تلاش کردند: {'، '.join(others)}"

    for bkey in new_badges:
        b = BADGES[bkey]
        result_text += f"\n\n🏅 نشان جدید: {b['emoji']} {b['title']}"

    await _finish_round_message(
        context, chat_id, message_id, category,
        quiz["buzzer_next_delay"], quiz.get("session_last", False), result_text,
    )


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

    if quiz["buzzer_mode"]:
        # در حالت زنگ‌اول، حتی اگر کسی برنده نشد، دور بعدی خودکار ادامه پیدا می‌کند
        await _finish_round_message(
            context, data["chat_id"], data["message_id"], category,
            quiz["buzzer_next_delay"], quiz.get("session_last", False), result_text,
        )
        return

    buttons = [
        [InlineKeyboardButton("🔁 سوال بعدی", callback_data=f"quizcat_{category}")],
        [InlineKeyboardButton("📋 منوی دسته‌ها", callback_data="quizmenu")],
    ]

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


# ---------------- تنظیمات کوییز (مخصوص ادمین‌های گروه) ----------------

async def quiz_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    settings = _get_quiz_settings(chat_id)

    time_text = f"{settings['custom_time']} ثانیه (سفارشی)" if settings["custom_time"] else "پیش‌فرض بر اساس سطح سختی"
    buzzer_text = "روشن 🔔" if settings["buzzer_mode"] else "خاموش"

    lines = [
        "⚙️ تنظیمات کوییز این گروه:\n",
        f"⏱ زمان هر سوال: {time_text}",
        f"🔔 حالت زنگ‌اول: {buzzer_text}",
        f"⏭ تاخیر سوال بعدی (در حالت زنگ‌اول): {settings['next_delay']} ثانیه",
    ]

    session = BUZZER_SESSIONS.get(chat_id)
    if settings["buzzer_mode"] and session:
        if session["total"]:
            lines.append(f"📍 دوره‌ی فعلی: سوال {session['asked_count']} از {session['total']}")
        else:
            lines.append(f"📍 دوره‌ی فعلی: نامحدود ({session['asked_count']} سوال پرسیده شده)")

    lines += [
        "\nبرای تغییر (فقط ادمین):",
        "• /quiztime <ثانیه>  — یا  /quiztime 0  برای پیش‌فرض",
        "• /quizbuzzer on [تعداد سوال] | off",
        "• /quiznextdelay <ثانیه>",
    ]
    await update.message.reply_text("\n".join(lines))


async def quiz_time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه‌ی این دستور را ندارید.")
        return

    if not context.args:
        await update.message.reply_text(
            "استفاده: /quiztime <ثانیه>\n"
            "مثال: /quiztime 30\n"
            "برای بازگشت به زمان پیش‌فرض هر سطح سختی: /quiztime 0\n"
            f"بازه‌ی مجاز: {MIN_CUSTOM_TIME} تا {MAX_CUSTOM_TIME} ثانیه"
        )
        return

    try:
        seconds = int(context.args[0])
    except ValueError:
        await update.message.reply_text("لطفاً یک عدد صحیح وارد کن.")
        return

    chat_id = update.effective_chat.id

    if seconds == 0:
        update_group_settings(chat_id, quiz_custom_time=None)
        await update.message.reply_text("✅ زمان سوالات به حالت پیش‌فرض (بر اساس سطح سختی) برگشت.")
        return

    if not (MIN_CUSTOM_TIME <= seconds <= MAX_CUSTOM_TIME):
        await update.message.reply_text(f"عدد باید بین {MIN_CUSTOM_TIME} تا {MAX_CUSTOM_TIME} ثانیه باشد.")
        return

    update_group_settings(chat_id, quiz_custom_time=seconds)
    await update.message.reply_text(f"✅ زمان هر سوال روی {seconds} ثانیه تنظیم شد.")


async def quiz_buzzer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه‌ی این دستور را ندارید.")
        return

    valid = {"on": True, "off": False, "روشن": True, "خاموش": False}
    if not context.args or context.args[0].lower() not in valid:
        await update.message.reply_text(
            "استفاده:\n"
            "/quizbuzzer on            — حالت زنگ‌اول نامحدود\n"
            "/quizbuzzer on 10         — یک دوره‌ی ۱۰ سوالی زنگ‌اول\n"
            "/quizbuzzer off           — خاموش کردن\n\n"
            "وقتی روشنه: هرکس زودتر از بقیه جواب درست بده، سوال قفل می‌شه، "
            "امتیاز می‌گیره و بعد از چند ثانیه خودکار سوال بعدی میاد.\n"
            "در یک دوره، سوالات تکراری پرسیده نمی‌شوند."
        )
        return

    enable = valid[context.args[0].lower()]
    chat_id = update.effective_chat.id

    if not enable:
        _end_buzzer_session(chat_id)
        await update.message.reply_text("✅ حالت زنگ‌اول خاموش شد. کوییز به حالت عادی برگشت.")
        return

    count = None
    if len(context.args) > 1:
        try:
            count = int(context.args[1])
        except ValueError:
            await update.message.reply_text("عدد تعداد سوال باید یک عدد صحیح باشد.")
            return
        if not (MIN_BUZZER_COUNT <= count <= MAX_BUZZER_COUNT):
            await update.message.reply_text(
                f"تعداد سوال باید بین {MIN_BUZZER_COUNT} تا {MAX_BUZZER_COUNT} باشد."
            )
            return

    update_group_settings(chat_id, quiz_buzzer_mode=1)
    _start_buzzer_session(chat_id, total=count)

    if count:
        await update.message.reply_text(
            f"🔔 یک دوره‌ی زنگ‌اول با {count} سوال شروع شد!\n"
            "هرکس زودتر از بقیه جواب درست بده برنده‌ی همون سواله. سوالات تکراری پرسیده نمی‌شوند.\n"
            "برای شروع دور اول: /quiz"
        )
    else:
        await update.message.reply_text(
            "🔔 حالت زنگ‌اول نامحدود روشن شد!\n"
            "هرکس زودتر از بقیه جواب درست بده برنده‌ی همون سواله و بقیه دیگه نمی‌تونن جواب بدن.\n"
            "برای شروع دور اول: /quiz"
        )


async def quiz_next_delay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("شما اجازه‌ی این دستور را ندارید.")
        return

    if not context.args:
        await update.message.reply_text(
            f"استفاده: /quiznextdelay <ثانیه>\nبازه‌ی مجاز: {MIN_NEXT_DELAY} تا {MAX_NEXT_DELAY} ثانیه"
        )
        return

    try:
        seconds = int(context.args[0])
    except ValueError:
        await update.message.reply_text("لطفاً یک عدد صحیح وارد کن.")
        return

    if not (MIN_NEXT_DELAY <= seconds <= MAX_NEXT_DELAY):
        await update.message.reply_text(f"عدد باید بین {MIN_NEXT_DELAY} تا {MAX_NEXT_DELAY} ثانیه باشد.")
        return

    chat_id = update.effective_chat.id
    update_group_settings(chat_id, quiz_buzzer_next_delay=seconds)
    await update.message.reply_text(f"✅ فاصله تا سوال بعدی (حالت زنگ‌اول) روی {seconds} ثانیه تنظیم شد.")


# ==========================================
# مسابقه سرعتی با متن ساده (تایپ در گروه)
# ==========================================

async def start_rapid_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع مسابقه سرعتی با تعداد سوال مشخص (با تایپ 'مسابقه سرعتی 10' در گروه)"""
    chat_id = update.effective_chat.id
    text = update.message.text
    
    # استخراج تعداد سوال از متن
    try:
        count = int(text.replace("مسابقه سرعتی", "").strip())
        if count < 1:
            count = 5
        if count > 30:
            count = 30
    except:
        count = 10
    
    # تنظیم حالت زنگ‌اول
    update_group_settings(chat_id, quiz_buzzer_mode=1)
    
    # شروع سشن زنگ‌اول با تعداد مشخص
    _start_buzzer_session(chat_id, total=count)
    
    await update.message.reply_text(
        f"🔔 مسابقه سرعتی با {count} سوال شروع شد!\n"
        f"هرکی زودتر جواب درست بده، امتیاز رو می‌بره!\n"
        f"🏆 آماده‌اید؟ شروع..."
    )
    
    # ارسال اولین سوال
    await start_quiz(update, context, "random")


# ==========================================
# مسابقه معمولی با متن ساده (تایپ در گروه)
# ==========================================

async def start_normal_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع مسابقه معمولی با تعداد سوال مشخص (با تایپ 'مسابقه معمولی 10' در گروه)"""
    chat_id = update.effective_chat.id
    text = update.message.text
    
    # استخراج تعداد سوال از متن
    try:
        count = int(text.replace("مسابقه معمولی", "").strip())
        if count < 1:
            count = 5
        if count > 30:
            count = 30
    except:
        count = 10
    
    # خاموش کردن حالت زنگ‌اول
    update_group_settings(chat_id, quiz_buzzer_mode=0)
    _end_buzzer_session(chat_id)
    
    # ذخیره تعداد سوال در context
    context.chat_data['normal_quiz_count'] = count
    
    await update.message.reply_text(
        f"🎮 مسابقه معمولی با {count} سوال شروع شد!\n"
        f"همه می‌تونن جواب بدن و امتیاز بگیرن!\n"
        f"🏆 آماده‌اید؟ شروع..."
    )
    
    # ارسال اولین سوال
    await start_quiz(update, context, "random")