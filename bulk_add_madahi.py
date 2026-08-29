"""
bulk_add_madahi.py

اضافه کردن دسته‌ای فایل‌های مداحی/مولودی از روی یه فایل JSON.

نحوه‌ی اجرا:
    python3 bulk_add_madahi.py madahi_seed_batch.json

فرمت فایل JSON (لیستی از آبجکت‌ها):
[
    {
        "content_type": "madahi",           // یا "molodi"
        "occasion": "محرم و عاشورا",         // اسم مناسبت (هر متنی، لازم نیست از قبل تعریف شده باشه)
        "title": "السلام علیک یا اباعبدالله",
        "reciter": "کریمی",                  // اختیاری، اگه نداری بذار "" یا اصلاً ننویس
        "audio_file_id": "AwACAgIC..."       // از دستور دیباگِ file_id توی خودِ ربات بگیر
    },
    ...
]

نکته: file_id ها رو با فوروارد کردن فایل صوتی به ربات (همون هندلر دیباگ
موجود که Audio/Voice file_id رو نشون می‌ده) به دست میاری.
"""
import json
import sys

from database import init_db, add_madahi

VALID_TYPES = ("madahi", "molodi")


def main(path: str):
    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f)

    if not isinstance(items, list):
        print("❌ فایل JSON باید یه لیست از آبجکت‌ها باشه.")
        sys.exit(1)

    init_db()

    added = 0
    skipped = 0

    for i, item in enumerate(items, start=1):
        content_type = (item.get("content_type") or "madahi").strip()
        occasion = (item.get("occasion") or "").strip()
        title = (item.get("title") or "").strip()
        reciter = (item.get("reciter") or "").strip() or None
        audio_file_id = (item.get("audio_file_id") or "").strip()

        if content_type not in VALID_TYPES:
            print(f"⚠️  ردیف {i}: content_type نامعتبر ({content_type!r})، رد شد.")
            skipped += 1
            continue
        if not occasion or not title or not audio_file_id:
            print(f"⚠️  ردیف {i}: occasion/title/audio_file_id خالیه، رد شد.")
            skipped += 1
            continue

        item_id = add_madahi(content_type, occasion, title, audio_file_id, reciter=reciter)
        print(f"✅ ردیف {i}: اضافه شد (id={item_id}) - {title}")
        added += 1

    print(f"\nتمام شد. {added} مورد اضافه شد، {skipped} مورد رد شد.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("استفاده: python3 bulk_add_madahi.py <path-to-json-file>")
        sys.exit(1)
    main(sys.argv[1])
