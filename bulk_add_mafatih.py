"""
این اسکریپت یک فایل JSON حاوی لیستی از ادعیه/زیارت/اعمال مفاتیح‌الجنان را
می‌خواند و همه را یک‌جا به دیتابیس اضافه می‌کند (به‌جای ثبت تک‌تک با /addmafatih).

فرمت هر آیتم در JSON:
{
    "category": "daily",     // یکی از: daily/ziyarat/weekly/monthly/munajat/special
    "title": "دعای کمیل",
    "arabic": "...",
    "translation": "...",     // اختیاری
    "tafsir": "..."           // اختیاری
}

نحوه اجرا (روی Railway، از تب Console، یا لوکال):
    python bulk_add_mafatih.py mafatih_seed_batch.json
"""
import sys
import json
from database import init_db, add_mafatih_item, get_connection

VALID_CATEGORIES = {"daily", "ziyarat", "weekly", "monthly", "munajat", "special"}


def item_exists(category: str, title: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM mafatih WHERE category = ? AND title = ?", (category, title)
    ).fetchone()
    conn.close()
    return row is not None


def main():
    if len(sys.argv) < 2:
        print("استفاده: python bulk_add_mafatih.py <فایل.json>")
        sys.exit(1)

    json_path = sys.argv[1]
    init_db()

    with open(json_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    added = 0
    skipped = 0

    for it in items:
        category = (it.get("category") or "").strip()
        title = (it.get("title") or "").strip()
        arabic = (it.get("arabic") or "").strip()

        if category not in VALID_CATEGORIES:
            print(f"⚠️ رد شد (دسته نامعتبر): {it}")
            skipped += 1
            continue

        if not title or not arabic:
            print(f"⚠️ رد شد (فیلد ناقص): {it}")
            skipped += 1
            continue

        if item_exists(category, title):
            print(f"⏭️  از قبل موجود است، رد شد: {title}")
            skipped += 1
            continue

        item_id = add_mafatih_item(
            category=category,
            title=title,
            arabic_text=arabic,
            translation_text=it.get("translation") or None,
            tafsir_text=it.get("tafsir") or None,
        )
        print(f"✅ ثبت شد (شناسه {item_id}): {title}")
        added += 1

    print(f"\nنتیجه نهایی: {added} مورد جدید اضافه شد، {skipped} مورد رد شد.")


if __name__ == "__main__":
    main()
