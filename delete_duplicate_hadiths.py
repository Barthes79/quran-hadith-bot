"""
حذف احادیث تکراری (۱۰ گروه شناسایی‌شده).
برای هر گروه، نسخه‌ای که منبع/سند کامل‌تر داشت نگه داشته شده است.

نحوه اجرا (روی Railway از تب Console):
    python delete_duplicate_hadiths.py
"""
from database import init_db, delete_hadith, get_hadith_by_id

# شناسه‌هایی که حذف می‌شوند (نسخه‌ی تکراری با سند ضعیف‌تر)
IDS_TO_DELETE = [126, 96, 73, 110, 90, 93, 95, 111, 123, 124]


def main():
    init_db()
    deleted = []
    skipped = []
    for hadith_id in IDS_TO_DELETE:
        row = get_hadith_by_id(hadith_id)
        if row is None:
            skipped.append(hadith_id)
            continue
        delete_hadith(hadith_id)
        deleted.append(hadith_id)

    print(f"✅ حذف شد: {deleted}")
    if skipped:
        print(f"⚠️ قبلاً وجود نداشت (احتمالاً حذف‌شده): {skipped}")


if __name__ == "__main__":
    main()
