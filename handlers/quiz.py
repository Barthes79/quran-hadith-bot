import re
import time

QUIZ_TIME_LIMIT = 20  # زمان پاسخ‌گویی به ثانیه
QUIZ_START_TIMES = {}
QUIZ_ANSWERS = {}
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from database import (
    get_random_quiz_question, get_quiz_question_by_id,
    add_score, get_leaderboard, add_quiz_question,
)


def quiz_keyboard(qid: int):
    buttons = [
        [InlineKeyboardButton("الف", callback_data=f"quizans_{qid}_a"),
         InlineKeyboardButton("ب", callback_data=f"quizans_{qid}_b")],
        [InlineKeyboardButton("ج", callback_data=f"quizans_{qid}_c"),
         InlineKeyboardButton("د", callback_data=f"quizans_{qid}_d")],
    ]
    return InlineKeyboardMarkup(buttons)


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_random_quiz_question()
    if not row:
        await update.message.reply_text(
            "هنوز سوالی برای مسابقه ثبت نشده است.\n"
            "ادمین می‌تواند با دستور /addquiz سوال جدید اضافه کند."
        )
        return

    text = (
        f"❓ {row['question_text']}\n\n"
        f"الف) {row['option_a']}\n"
        f"ب) {row['option_b']}\n"
        f"ج) {row['option_c']}\n"
        f"د) {row['option_d']}\n\n"
        "هرکس زودتر جواب درست را بزند، امتیاز می‌گیرد! 🏆"
    )
    sent = await update.message.reply_text(text, reply_markup=quiz_keyboard(row["id"]))
    key = (update.effective_chat.id, sent.message_id)
    QUIZ_START_TIMES[key] = time.time()
    QUIZ_ANSWERS[key] = {"qid": row["id"], "answers": {}}

    context.job_queue.run_once(
        finish_quiz,
        QUIZ_TIME_LIMIT,
        data={"chat_id": update.effective_chat.id,
              "message_id": sent.message_id,
              "qid": row["id"]}
    )


async def quiz_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    key = (query.message.chat.id, query.message.message_id)

    if key not in QUIZ_ANSWERS:
        await query.answer("⏰ زمان پاسخ‌گویی تمام شده است.", show_alert=True)
        return

    _, qid, chosen = query.data.split("_")
    qid = int(qid)

    user = query.from_user
    username = user.username or user.first_name or "ناشناس"

    QUIZ_ANSWERS[key]["answers"][user.id] = {
        "username": username,
        "chosen": chosen
    }

    await query.answer("✅ جواب شما ثبت شد")


async def finish_quiz(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    key = (data["chat_id"], data["message_id"])

    quiz = QUIZ_ANSWERS.pop(key, None)
    QUIZ_START_TIMES.pop(key, None)

    if not quiz:
        return

    row = get_quiz_question_by_id(data["qid"])
    if not row:
        return

    correct = []
    wrong = []

    for uid, ans in quiz["answers"].items():
        if ans["chosen"] == row["correct_option"]:
            correct.append(ans["username"])
            add_score(data["chat_id"], uid, ans["username"], points=1)
        else:
            wrong.append(ans["username"])

    option_map = {"a": "الف", "b": "ب", "c": "ج", "d": "د"}
    correct_text_map = {
        "a": row["option_a"],
        "b": row["option_b"],
        "c": row["option_c"],
        "d": row["option_d"],
    }

    result_text = (
        "⏰ زمان پاسخ‌گویی تمام شد!\n\n"
        f"✅ درست‌ها:\n{chr(10).join(correct) if correct else 'هیچ‌کس'}\n\n"
        f"❌ غلط‌ها:\n{chr(10).join(wrong) if wrong else 'هیچ‌کس'}\n\n"
        f"📌 جواب صحیح: {option_map[row['correct_option']]}) {correct_text_map[row['correct_option']]}"
    )

    await context.bot.edit_message_text(
        chat_id=data["chat_id"],
        message_id=data["message_id"],
        text=result_text
    )


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_leaderboard(update.effective_chat.id)
    if not rows:
        await update.message.reply_text("هنوز کسی در این گروه امتیازی کسب نکرده است.")
        return

    lines = ["🏆 جدول امتیازات این گروه:\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows):
        prefix = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{prefix} {row['username']} — {row['score']} امتیاز")

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
            "پاسخ: الف (یا ب، ج، د)"
        )
        return

    body = full_text[1]
    field_labels = ["سوال", "الف", "ب", "ج", "د", "پاسخ"]
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

    qid = add_quiz_question(question, option_a, option_b, option_c, option_d, correct_option)
    await update.message.reply_text(f"✅ سوال با شناسه {qid} با موفقیت ثبت شد.")
