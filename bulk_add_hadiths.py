"""
این اسکریپت یک فایل JSON حاوی لیستی از احادیث را می‌خواند و همه را یک‌جا
به دیتابیس اضافه می‌کند. برای افزودن حجم بالایی از احادیث (به‌جای فرستادن
تک‌تک با /addhadith در تلگرام) از این استفاده کنید.

نحوه اجرا (روی Railway، از تب Console):
    python bulk_add_hadiths.py hadiths_seed_batch.json

یا لوکال روی سیستم خودتان:
    python bulk_add_hadiths.py hadiths_seed_batch.json
"""
import sys
import json
from database import init_db, add_hadith, get_connection


def hadith_exists(arabic_text: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM hadiths WHERE arabic_text = ?", (arabic_text,)
    ).fetchone()
    conn.close()
    return row is not None


def main():
    if len(sys.argv) < 2:
        print("استفاده: python bulk_add_hadiths.py <فایل.json>")
        sys.exit(1)

    json_path = sys.argv[1]
    init_db()

    with open(json_path, "r", encoding="utf-8") as f:
        hadiths = json.load(f)

    added = 0
    skipped = 0

    for h in hadiths:
        arabic = h.get("arabic", "").strip()
        translation = h.get("translation", "").strip()

        if not arabic or not translation:
            print(f"⚠️ رد شد (فیلد ناقص): {h}")
            continue

        if hadith_exists(arabic):
            print(f"⏭️  از قبل موجود است، رد شد: {translation[:40]}...")
            skipped += 1
            continue

        hadith_id = add_hadith(
            arabic_text=arabic,
            translation_text=translation,
            narrator=h.get("narrator", ""),
            source_book=h.get("source", ""),
            chapter=h.get("chapter", ""),
            hadith_number=h.get("number", ""),
            tafsir_text=h.get("tafsir") or None,
            topics=h.get("topics", []),
        )
        print(f"✅ ثبت شد (شناسه {hadith_id}): {translation[:40]}...")
        added += 1

    print(f"\nنتیجه نهایی: {added} حدیث جدید اضافه شد، {skipped} مورد تکراری رد شد.")


if __name__ == "__main__":
    main()
