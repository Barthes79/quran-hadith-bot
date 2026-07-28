"""
حذف بخش «سوره‌های قرآنی مفاتیح» از دیتابیس.
این اسکریپت رکوردهای مربوط به ۶ آیتم زیر را از جدول mafatih حذف می‌کند:
حدیث کساء، مکارم‌الاخلاق، سوره یس، سوره الرحمن، سوره واقعه، روم و عنکبوت

نحوه‌ی اجرا (روی سرور Railway یا لوکال، هرجا که فایل دیتابیس sqlite هست):
    python delete_quran_surahs.py
یا برای فقط نمایش بدون حذف واقعی (dry-run):
    python delete_quran_surahs.py --dry-run
"""

import sqlite3
import sys
import os

# مسیر دیتابیس را در صورت نیاز عوض کنید (مثلاً روی Railway Volume)
DB_PATH = os.environ.get("DB_PATH", "bot_database.db")

SLUGS_TO_DELETE = [
    "hadith_kisa",
    "dua_makarem",
    "surah_yasin",
    "surah_rahman",
    "surah_waqiah",
    "surah_rom_ankabut",
]


def main():
    dry_run = "--dry-run" in sys.argv

    if not os.path.exists(DB_PATH):
        print(f"❌ دیتابیس در مسیر {DB_PATH} پیدا نشد. مسیر درست را با DB_PATH بدهید.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    placeholders = ",".join("?" for _ in SLUGS_TO_DELETE)

    # پیدا کردن رکوردها چه با ستون slug و چه با id متنی (برای اطمینان از سازگاری با هر دو حالت)
    cur.execute(
        f"SELECT id, slug, title FROM mafatih WHERE slug IN ({placeholders}) OR id IN ({placeholders})",
        SLUGS_TO_DELETE + SLUGS_TO_DELETE,
    )
    rows = cur.fetchall()

    if not rows:
        print("⚠️ هیچ رکوردی با این شناسه‌ها پیدا نشد. شاید نام ستون‌ها فرق دارد یا قبلاً حذف شده‌اند.")
        conn.close()
        return

    print(f"رکوردهای زیر پیدا شدند ({len(rows)} مورد):")
    for r in rows:
        print(f"  id={r['id']}  slug={r['slug']}  title={r['title']}")

    if dry_run:
        print("\n(dry-run) چیزی حذف نشد.")
        conn.close()
        return

    cur.execute(
        f"DELETE FROM mafatih WHERE slug IN ({placeholders}) OR id IN ({placeholders})",
        SLUGS_TO_DELETE + SLUGS_TO_DELETE,
    )
    conn.commit()
    print(f"\n✅ {cur.rowcount} رکورد با موفقیت حذف شد.")
    conn.close()


if __name__ == "__main__":
    main()
