"""
اگر ادعیه‌ی ایام هفته (دعای شنبه تا جمعه) قبلاً با دسته‌ی "weekly" در دیتابیس
ثبت شده باشند، این اسکریپت دسته‌ی آن‌ها را به "daily" تغییر می‌دهد تا زیرمجموعه‌ی
«ادعیه روزانه» نمایش داده شوند (به‌جای «اعمال ایام هفته»).

اگر هنوز اصلاً ثبت نشده‌اند، نیازی به اجرای این اسکریپت نیست؛ کافیست همان
دستور همیشگی را بزنید:
    python bulk_add_mafatih.py doahaftegi.json
(فایل doahaftegi.json از قبل به‌روزرسانی شده و دسته‌ی هر ۷ مورد "daily" است)

نحوه‌ی اجرا (روی Railway، از تب Console):
    python fix_weekly_to_daily.py
"""
from database import get_connection

TITLES = [
    "دعای روز شنبه",
    "دعای روز یکشنبه",
    "دعای روز دوشنبه",
    "دعای روز سه شنبه",
    "دعای روز چهارشنبه",
    "دعای روز پنجشنبه",
    "دعای روز جمعه",
]


def main():
    conn = get_connection()
    cur = conn.cursor()
    total = 0
    for title in TITLES:
        cur.execute(
            "UPDATE mafatih SET category = 'daily' WHERE category = 'weekly' AND title = ?",
            (title,),
        )
        if cur.rowcount:
            print(f"🔄 «{title}» از weekly به daily منتقل شد.")
            total += cur.rowcount
    conn.commit()
    conn.close()
    print(f"\nنتیجه نهایی: {total} مورد منتقل شد.")


if __name__ == "__main__":
    main()
