# -*- coding: utf-8 -*-
"""
اسکریپت انتقال Volume بین دو اکانت Railway، از طریق خود ربات.

دو دستور ادمین اضافه می‌کنه:
  /backupvolume   -> کل پوشه‌ی Volume (همون جایی که دیتابیس توشه) رو zip می‌کنه
                     و برای ادمین توی تلگرام می‌فرسته.
  /restorevolume  -> باید روی فایل zip بکاپ ریپلای بشه؛ فایل رو می‌گیره و
                     داخل پوشه‌ی Volume همین پروژه extract می‌کنه.

نحوه‌ی استفاده در main.py (کنار بقیه‌ی import ها و handler ها اضافه کن):

    from admin_migrate import backup_volume, restore_volume
    app.add_handler(CommandHandler("backupvolume", backup_volume))
    app.add_handler(CommandHandler("restorevolume", restore_volume))

⚠️ نکته‌ی مهم: محدودیت آپلود فایل ربات‌های تلگرام ۵۰ مگابایته. اگه Volume‌ات
(مثلاً به‌خاطر فایل‌های صوتی مداحی) بزرگ‌تر از این باشه، /backupvolume از کار
میفته یا ارور تایم‌اوت می‌ده. اگه به این مشکل خوردی بگو تا نسخه‌ی chunked
(چند تیکه‌ای) اسکریپت رو هم برات بسازم.

⚠️ بعد از اینکه کارت با انتقال تموم شد، حتماً این دو دستور رو از main.py
حذف کن (یا حداقل مطمئن شو فقط ADMIN_IDS بهشون دسترسی دارن) چون /restorevolume
می‌تونه کل دیتابیس رو overwrite کنه.
"""

import os
import tempfile
import zipfile
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS, DATABASE_PATH


def _volume_dir() -> str:
    """پوشه‌ای که فایل دیتابیس توشه -- یعنی همون مسیر mount شده‌ی Volume.
    اگه DATABASE_PATH یه اسم فایل ساده باشه (بدون مسیر پوشه)، یعنی همین
    working directory استفاده می‌شه."""
    d = os.path.dirname(os.path.abspath(DATABASE_PATH))
    return d if os.path.isdir(d) else os.getcwd()


async def backup_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور ادمین: /backupvolume"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    volume_dir = _volume_dir()
    await update.message.reply_text(
        f"⏳ در حال zip کردن محتویات:\n`{volume_dir}`",
        parse_mode="Markdown",
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(tempfile.gettempdir(), f"volume_backup_{timestamp}.zip")

    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(volume_dir):
            for fname in files:
                full_path = os.path.join(root, fname)
                arcname = os.path.relpath(full_path, volume_dir)
                zf.write(full_path, arcname)
                file_count += 1

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)

    if size_mb > 49:
        os.remove(zip_path)
        await update.message.reply_text(
            f"❌ حجم بکاپ {size_mb:.1f} مگابایت شد و از محدودیت ۵۰ مگابایتی "
            "آپلود ربات‌های تلگرام بیشتره. بهم بگو تا نسخه‌ی تکه‌تکه‌شده رو برات بسازم."
        )
        return

    await update.message.reply_text(
        f"📦 بکاپ آماده شد: {file_count} فایل، {size_mb:.1f} مگابایت. در حال ارسال..."
    )

    try:
        with open(zip_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=os.path.basename(zip_path),
                caption=(
                    "✅ بکاپ کامل Volume.\n"
                    "این فایل رو دانلود کن، بعد توی پروژه‌ی جدید همین فایل رو "
                    "به دستور /restorevolume ریپلای کن."
                ),
                read_timeout=120,
                write_timeout=120,
                connect_timeout=60,
            )
    finally:
        os.remove(zip_path)


async def restore_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور ادمین: /restorevolume
    باید روی فایل zip بکاپ (همونی که /backupvolume فرستاده) ریپلای بشه."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    reply = update.message.reply_to_message
    if not reply or not reply.document:
        await update.message.reply_text(
            "❗️ این دستور رو باید روی فایل zip بکاپ، به‌صورت ریپلای بفرستی."
        )
        return

    document = reply.document
    await update.message.reply_text("⏳ در حال دریافت فایل بکاپ...")

    tg_file = await context.bot.get_file(document.file_id)
    tmp_zip_path = os.path.join(
        tempfile.gettempdir(), document.file_name or "restore_volume.zip"
    )
    await tg_file.download_to_drive(tmp_zip_path)

    volume_dir = _volume_dir()
    os.makedirs(volume_dir, exist_ok=True)

    await update.message.reply_text(
        f"📦 در حال استخراج داخل:\n`{volume_dir}`\n"
        "(فایل‌های هم‌نام موجود overwrite می‌شن)",
        parse_mode="Markdown",
    )

    with zipfile.ZipFile(tmp_zip_path, "r") as zf:
        zf.extractall(volume_dir)

    os.remove(tmp_zip_path)

    await update.message.reply_text(
        "✅ بازیابی انجام شد.\n"
        "حالا سرویس رو از پنل Railway یه بار Restart/Redeploy کن تا کانکشن "
        "دیتابیس با فایل تازه‌جایگزین‌شده هماهنگ بشه، بعد /backupvolume و "
        "/restorevolume رو از main.py حذف کن."
    )
