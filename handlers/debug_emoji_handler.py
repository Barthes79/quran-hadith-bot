"""
هندلر موقت برای پیدا کردن custom_emoji_id
-------------------------------------------
این فایل رو داخل پروژه (کنار start.py) بذار، و طبق دستورالعمل پایین فایل
دو خط به main.py اضافه کن. بعدش هر پیامی که حاوی ایموجی سفارشی باشه رو
مستقیم به ربات بفرست (نه فوروارد، مستقیم بفرست) — ربات خودش
custom_emoji_id رو برات ریپلای می‌کنه.

⚠️ کار تمام شد؟ این هندلر رو از main.py حذف کن (یا فایل رو پاک کن) چون
کاربردی برای کاربرای عادی نداره و بهتره توی پروداکشن نمونه.
"""

from telegram import Update
from telegram.ext import ContextTypes


async def debug_custom_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.entities:
        return

    custom_emojis = [e for e in msg.entities if e.type == "custom_emoji"]
    if not custom_emojis:
        return

    lines = []
    for e in custom_emojis:
        emoji_slice = msg.text[e.offset: e.offset + e.length]
        lines.append(f"{emoji_slice} → `{e.custom_emoji_id}`")

    await msg.reply_text(
        "🔎 *custom_emoji_id پیدا شده:*\n" + "\n".join(lines),
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────────────────────
# نحوه‌ی اضافه کردن به main.py (فقط موقت):
#
#   from debug_emoji_handler import debug_custom_emoji
#   from telegram.ext import MessageHandler, filters
#   app.add_handler(MessageHandler(filters.ALL, debug_custom_emoji), group=0)
#
# نکته: group=0 یعنی این هندلر قبل از بقیه‌ی هندلرها چک می‌شه، ولی چون
# فقط روی پیام‌های حاوی custom_emoji واکنش نشون می‌ده (بقیه رو return
# می‌کنه بدون کاری)، مزاحم بقیه‌ی هندلرهای فعلی ربات نمی‌شه.
# ─────────────────────────────────────────────────────────────
