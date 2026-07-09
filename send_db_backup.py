"""
ارسال فایل کامل دیتابیس ربات (شامل همه‌ی خطبه‌ها، نامه‌ها، حکمت‌ها،
حدیث‌ها، کاربران، علاقه‌مندی‌ها و ...) به آیدی ادمین در تلگرام،
تا بتوانید آن را دانلود و روی هاست جدید آپلود کنید.

اجرا روی هاست فعلی (کنسول):
    python send_db_backup.py

بعد از اجرا، فایل .db را در چت خصوصی خودتان با ربات دریافت می‌کنید.
سپس کافیست همان فایل را در هاست جدید، در همان مسیر/اسم DATABASE_PATH قرار دهید.
"""
import os
import requests
from config import BOT_TOKEN, ADMIN_IDS, DATABASE_PATH, PROXY_URL


def main():
    if not BOT_TOKEN:
        print("⚠️ BOT_TOKEN تنظیم نشده است.")
        return
    if not ADMIN_IDS:
        print("⚠️ ADMIN_IDS تنظیم نشده است.")
        return
    if not os.path.exists(DATABASE_PATH):
        print(f"⚠️ فایل دیتابیس پیدا نشد: {DATABASE_PATH}")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    proxies = None
    if PROXY_URL:
        proxies = {"http": PROXY_URL, "https": PROXY_URL}

    for admin_id in ADMIN_IDS:
        with open(DATABASE_PATH, "rb") as f:
            resp = requests.post(
                url,
                data={"chat_id": admin_id, "caption": "📦 بک‌آپ کامل دیتابیس ربات"},
                files={"document": (os.path.basename(DATABASE_PATH), f)},
                proxies=proxies,
                timeout=120,
            )
        if resp.ok:
            print(f"✅ فایل برای ادمین {admin_id} ارسال شد.")
        else:
            print(f"❌ ارسال برای ادمین {admin_id} ناموفق بود: {resp.status_code} {resp.text}")


if __name__ == "__main__":
    main()
