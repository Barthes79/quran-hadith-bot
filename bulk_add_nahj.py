"""
این اسکریپت یک فایل JSON حاوی لیستی از خطبه‌ها/نامه‌ها/حکمت‌های نهج‌البلاغه را
می‌خواند و همه را یک‌جا به دیتابیس اضافه می‌کند (به‌جای ثبت تک‌تک با /addnahj).

فرمت هر آیتم در JSON:
{
    "category": "khutbah",   // یکی از: khutbah (خطبه) / letter (نامه) / hekmat (حکمت)
    "number": 1,              // شماره‌ی متعارف (بر اساس نسخه صبحی صالح)
    "title": "...",           // اختیاری
    "arabic": "...",
    "translation": "...",
    "tafsir": "..."           // اختیاری
}

نحوه اجرا (روی Railway، از تب Console، یا لوکال):
    python bulk_add_nahj.py nahj_seed_batch.json
"""
import sys
import json
from database import init_db, add_nahj_item

VALID_CATEGORIES = {"khutbah", "letter", "hekmat"}
TOTALS = {"khutbah": 241, "letter": 79, "hekmat": 480}


def main():
    if len(sys.argv) < 2:
        print("استفاده: python bulk_add_nahj.py <فایل.json>")
        sys.exit(1)

    json_path = sys.argv[1]
    init_db()

    with open(json_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    added = 0
    skipped = 0

    for it in items:
        category = (it.get("category") or "").strip()
        number = it.get("number")
        arabic = (it.get("arabic") or "").strip()
        translation = (it.get("translation") or "").strip()

        if category not in VALID_CATEGORIES:
            print(f"⚠️ رد شد (دسته نامعتبر): {it}")
            skipped += 1
            continue

        try:
            number = int(number)
        except (TypeError, ValueError):
            print(f"⚠️ رد شد (شماره نامعتبر): {it}")
            skipped += 1
            continue

        if not (1 <= number <= TOTALS[category]):
            print(f"⚠️ رد شد (شماره خارج از بازه‌ی {category}): {it}")
            skipped += 1
            continue

        if not arabic or not translation:
            print(f"⚠️ رد شد (فیلد ناقص): {it}")
            skipped += 1
            continue

        add_nahj_item(
            category=category,
            number=number,
            arabic_text=arabic,
            translation_text=translation,
            title=it.get("title") or None,
            tafsir_text=it.get("tafsir") or None,
        )
        print(f"✅ ثبت شد: {category} شماره {number}")
        added += 1

    print(f"\nنتیجه نهایی: {added} مورد ثبت/به‌روزرسانی شد، {skipped} مورد رد شد.")


if __name__ == "__main__":
    main()
