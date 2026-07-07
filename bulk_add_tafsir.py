"""
مشابه bulk_add_hadiths.py، این اسکریپت یک فایل JSON از تفسیرهای آیات را
می‌خواند و همه را یک‌جا به دیتابیس اضافه می‌کند.

نحوه اجرا (از تب Console در Railway یا لوکال):
    python bulk_add_tafsir.py tafsir_seed_batch.json
"""
import sys
import json
from database import init_db, set_ayah_tafsir


def main():
    if len(sys.argv) < 2:
        print("استفاده: python bulk_add_tafsir.py <فایل.json>")
        sys.exit(1)

    json_path = sys.argv[1]
    init_db()

    with open(json_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    added = 0
    for item in items:
        try:
            set_ayah_tafsir(
                int(item["surah"]), int(item["ayah"]),
                item["tafsir"], item.get("source", "")
            )
            print(f"✅ ثبت شد: سوره {item['surah']} آیه {item['ayah']}")
            added += 1
        except KeyError as e:
            print(f"⚠️ فیلد ناقص، رد شد: {e}")

    print(f"\nنتیجه نهایی: {added} تفسیر ثبت/به‌روزرسانی شد.")


if __name__ == "__main__":
    main()
