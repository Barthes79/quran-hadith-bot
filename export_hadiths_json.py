"""
این اسکریپت تمام احادیث موجود در دیتابیس را در قالب JSON خروجی می‌گیرد
تا هنگام افزودن احادیث جدید بتوان از عدم تکرار مطمئن شد.

نحوه اجرا (روی Railway از تب Console):
    python export_hadiths_json.py

خروجی در فایل all_hadiths_export.json ذخیره می‌شود.
"""
import json
from database import init_db, get_connection


def main():
    init_db()
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, arabic_text, translation_text, narrator, source_book, "
        "chapter, hadith_number FROM hadiths ORDER BY id"
    ).fetchall()
    conn.close()

    data = [
        {
            "id": r["id"],
            "arabic": r["arabic_text"],
            "translation": r["translation_text"],
            "narrator": r["narrator"],
            "source": r["source_book"],
            "chapter": r["chapter"],
            "number": r["hadith_number"],
        }
        for r in rows
    ]

    with open("all_hadiths_export.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(data)} حدیث در all_hadiths_export.json ذخیره شد.")


if __name__ == "__main__":
    main()
