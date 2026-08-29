"""
اسکریپت bulk_add_mafatih.py برای آیتم‌هایی که از قبل در دیتابیس ثبت شده‌اند،
فقط عکس را (در صورت نبودن) به‌روزرسانی می‌کند و به ترجمه دست نمی‌زند.
این اسکریپت برعکس آن است: ترجمه‌ی آیتم‌های موجود را از روی فایل JSON
(با تطبیق category + title) به‌روزرسانی می‌کند.

نحوه اجرا (روی Railway، از تب Console):
    python update_mafatih_translations.py doahaftegi.json
"""
import sys
import json
from database import get_connection, update_mafatih_translation


def main():
    if len(sys.argv) < 2:
        print("استفاده: python update_mafatih_translations.py <فایل.json>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        items = json.load(f)

    conn = get_connection()
    updated = 0
    not_found = 0

    for it in items:
        category = (it.get("category") or "").strip()
        title = (it.get("title") or "").strip()
        translation = (it.get("translation") or "").strip()
        if not category or not title or not translation:
            continue

        row = conn.execute(
            "SELECT id FROM mafatih WHERE category = ? AND title = ?", (category, title)
        ).fetchone()

        if row is None:
            print(f"⚠️ پیدا نشد، رد شد: {title}")
            not_found += 1
            continue

        update_mafatih_translation(row["id"], translation)
        print(f"🔄 ترجمه «{title}» به‌روزرسانی شد.")
        updated += 1

    conn.close()
    print(f"\nنتیجه نهایی: {updated} مورد به‌روزرسانی شد، {not_found} مورد پیدا نشد.")


if __name__ == "__main__":
    main()
