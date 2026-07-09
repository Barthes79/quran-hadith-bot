"""
این اسکریپت یک سری حدیث را بر اساس شناسه (id) یک‌جا ادیت می‌کند.
فقط فیلدهایی که در JSON مشخص کرده باشید تغییر می‌کنند، بقیه فیلدها دست‌نخورده می‌مانند.

اول با list_hadiths.py شناسه‌ی احادیثی که می‌خواهید ادیت کنید را پیدا کنید.

فرمت فایل JSON ورودی (یک لیست، هر آیتم باید "id" داشته باشد):

[
  {
    "id": 12,
    "translation": "متن ترجمه جدید",
    "tafsir": "تفسیر جدید (اختیاری)"
  },
  {
    "id": 15,
    "arabic": "متن عربی جدید",
    "narrator": "امام صادق (ع)",
    "source": "الکافی",
    "chapter": "باب صبر",
    "number": "٤٢",
    "topics": ["صبر", "بلا"]
  }
]

کلیدهای مجاز: id (اجباری), arabic, translation, tafsir, narrator, source, chapter, number, topics

نحوه اجرا (روی Railway از تب Console، یا لوکال):
    python bulk_edit_hadiths.py edits.json
"""
import sys
import json
from database import init_db, get_hadith_by_id, update_hadith, set_hadith_topics


def main():
    if len(sys.argv) < 2:
        print("استفاده: python bulk_edit_hadiths.py <فایل.json>")
        sys.exit(1)

    json_path = sys.argv[1]
    init_db()

    with open(json_path, "r", encoding="utf-8") as f:
        edits = json.load(f)

    updated = 0
    skipped = 0

    for e in edits:
        hadith_id = e.get("id")
        if hadith_id is None:
            print(f"⚠️ رد شد (بدون id): {e}")
            skipped += 1
            continue

        existing = get_hadith_by_id(hadith_id)
        if not existing:
            print(f"⚠️ حدیثی با شناسه {hadith_id} پیدا نشد، رد شد.")
            skipped += 1
            continue

        update_hadith(
            hadith_id,
            arabic_text=e.get("arabic"),
            translation_text=e.get("translation"),
            tafsir_text=e.get("tafsir"),
            narrator=e.get("narrator"),
            source_book=e.get("source"),
            chapter=e.get("chapter"),
            hadith_number=e.get("number"),
        )

        if "topics" in e:
            set_hadith_topics(hadith_id, e["topics"])

        preview = (e.get("translation") or existing["translation_text"] or "")[:40]
        print(f"✅ آپدیت شد (شناسه {hadith_id}): {preview}...")
        updated += 1

    print(f"\nنتیجه نهایی: {updated} حدیث آپدیت شد، {skipped} مورد رد شد.")


if __name__ == "__main__":
    main()
