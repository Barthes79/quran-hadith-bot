import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")  # توکن ربات از BotFather
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot_database.db")

# آدرس پروکسی (برای هاست‌های ایرانی که به تلگرام/APIهای خارجی دسترسی مستقیم ندارند)
# مثال: socks5://127.0.0.1:1080  یا  http://127.0.0.1:8080
# اگر نیازی به پروکسی نیست (مثلاً روی سیستم خودتان یا هاست خارجی)، این را در .env خالی بگذارید.
PROXY_URL = os.getenv("PROXY_URL", "").strip() or None

# API قرآن (رایگان، بدون نیاز به کلید)
QURAN_API_BASE = "https://api.alquran.cloud/v1"

# ادیشن‌های پیش‌فرض ترجمه فارسی موجود در alquran.cloud
DEFAULT_TRANSLATIONS = {
    "makarem": "fa.makarem",       # ترجمه مکارم شیرازی
    "ansarian": "fa.ansarian",     # ترجمه انصاریان
    "fooladvand": "fa.fooladvand", # ترجمه فولادوند
}
DEFAULT_TRANSLATION_KEY = "makarem"
