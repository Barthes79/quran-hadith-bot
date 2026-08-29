"""
این اسکریپت ایندکس جستجو (FTS5) را از نو، از روی جدول‌های hadiths،
nahj_balagha و mafatih می‌سازد.

معمولاً لازم نیست دستی اجرایش کنید چون:
- اولین بار که ربات بالا می‌آید (main.py) اگر ایندکس خالی باشد خودش می‌سازدش.
- هر add/update محتوا (از تلگرام یا از bulk_add_*.py) به‌صورت خودکار ایندکس را
  هم‌گام نگه می‌دارد.

فقط در این حالت‌ها لازمش دارید:
- اگر مستقیم روی دیتابیس (مثلاً با DB Browser) دستکاری کرده‌اید.
- اگر بعد از یک به‌روزرسانی بزرگ مطمئن می‌خواهید ایندکس ۱۰۰٪ تازه باشد.

نحوه اجرا (روی Railway، از تب Console):
    python rebuild_search_index.py
"""
from database import init_db, rebuild_search_index


def main():
    init_db()
    rebuild_search_index()


if __name__ == "__main__":
    main()
