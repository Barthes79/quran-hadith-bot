
import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

# سوالات ساده اولیه (بعداً می‌تونی ببری DB)
QUESTIONS = [
    {
        "question": "کدام گزینه یک حدیث مشهور درباره علم است؟",
        "options": [
            "طلب العلم فریضة",
            "الصبر مفتاح الفرج",
            "الدنیا دار الغرور",
            "الوقت سیف"
        ],
        "correct": 0
    },
    {
        "question": "کدام گزینه درباره صبر است؟",
        "options": [
            "طلب العلم فریضة",
            "الصبر مفتاح الفرج",
            "من جد وجد",
            "العدل اساس الملک"
        ],
        "correct": 1
    }
]

active_quiz = {}
scores = {}

async def send_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    q = random.choice(QUESTIONS)

    keyboard = [
        [InlineKeyboardButton("1", callback_data="quiz_0"),
         InlineKeyboardButton("2", callback_data="quiz_1")],
        [InlineKeyboardButton("3", callback_data="quiz_2"),
         InlineKeyboardButton("4", callback_data="quiz_3")]
    ]

    text = (
    "🧠 Quiz Time!\n\n"
    f"{q['question']}\n\n"
    f"1) {q['options'][0]}\n"
    f"2) {q['options'][1]}\n"
    f"3) {q['options'][2]}\n"
    f"4) {q['options'][3]}"
)

    msg = await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    active_quiz[msg.message_id] = q


async def quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    msg_id = query.message.message_id

    if msg_id not in active_quiz:
        return

    q = active_quiz[msg_id]
    data = query.data

    chosen = int(data.split("_")[1])

    if chosen == q["correct"]:
        await query.edit_message_text("✅ درست بود! آفرین 🎉")
        uid = query.from_user.id
        scores[uid] = scores.get(uid, 0) + 1
    else:
        await query.edit_message_text("❌ اشتباه بود!")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🏆 Leaderboard:\n\n"

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    for i, (uid, score) in enumerate(sorted_scores[:10]):
        text += f"{i+1}. User {uid} — {score}\n"

    await update.message.reply_text(text)
