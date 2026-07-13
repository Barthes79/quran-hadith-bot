"""
این اسکریپت یک فایل JSON حاوی لیستی از ادعیه/زیارت/اعمال مفاتیح‌الجنان را
می‌خواند و همه را یک‌جا به دیتابیس اضافه می‌کند (به‌جای ثبت تک‌تک با /addmafatih).

فرمت هر آیتم در JSON:
{
    "category": "daily",     // یکی از: daily/ziyarat/weekly/monthly/munajat/special
    "title": "دعای کمیل",
    "arabic": "...",          // اگر آیتم عکس دارد، می‌تواند خالی باشد
    "translation": "...",     // اختیاری
    "tafsir": "...",          // اختیاری
    "image": "images/xxx.png" // اختیاری؛ مسیر فایل عکس (اگر عکس موجود نباشد نادیده گرفته می‌شود)
}

نحوه اجرا (روی Railway، از تب Console، یا لوکال):
    python bulk_add_mafatih.py mafatih_seed_batch.json
"""
import os
import sys
import json
from database import init_db, add_mafatih_item, get_connection, update_mafatih_image

VALID_CATEGORIES = {"daily", "ziyarat", "weekly", "monthly", "munajat", "special"}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def resolve_image_path(image_path):
    if not image_path:
        return None
    full_path = image_path if os.path.isabs(image_path) else os.path.join(BASE_DIR, image_path)
    return full_path if os.path.isfile(full_path) else None


def get_existing_item(category: str, title: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT id, image_path FROM mafatih WHERE category = ? AND title = ?", (category, title)
    ).fetchone()
    conn.close()
    return row


def main():
    if len(sys.argv) < 2:
        print("استفاده: python bulk_add_mafatih.py <فایل.json>")
        sys.exit(1)

    json_path = sys.argv[1]
    init_db()

    with open(json_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    added = 0
    updated = 0
    skipped = 0

    for it in items:
        category = (it.get("category") or "").strip()
        title = (it.get("title") or "").strip()
        arabic = (it.get("arabic") or "").strip()
        raw_image = (it.get("image") or "").strip() or None

        if category not in VALID_CATEGORIES:
            print(f"⚠️ رد شد (دسته نامعتبر): {it}")
            skipped += 1
            continue

        translation = (it.get("translation") or "").strip()
        if not title or (not arabic and not raw_image and not translation):
            print(f"⚠️ رد شد (فیلد ناقص - حداقل عربی، عکس یا ترجمه لازم است): {it}")
            skipped += 1
            continue

        resolved = resolve_image_path(raw_image)
        if raw_image and not resolved:
            print(f"⚠️ توجه: فایل عکس «{raw_image}» پیدا نشد؛ فعلاً بدون عکس ثبت/به‌روزرسانی می‌شود: {title}")
        # فقط اگر فایل واقعاً روی دیسک پیدا شد، مسیر (نسبی) را در دیتابیس ذخیره کن
        image_path = raw_image if resolved else None

        existing = get_existing_item(category, title)
        if existing is not None:
            # آیتم از قبل موجود است. اگر عکس جدید پیدا شده و آیتم قبلاً عکس نداشت، فقط عکسش را به‌روزرسانی کن.
            if image_path and not existing["image_path"]:
                update_mafatih_image(existing["id"], image_path)
                print(f"🔄 عکس برای آیتم موجود «{title}» ثبت شد.")
                updated += 1
            else:
                print(f"⏭️  از قبل موجود است، رد شد: {title}")
                skipped += 1
            continue

        item_id = add_mafatih_item(
            category=category,
            title=title,
            arabic_text=arabic,
            translation_text=it.get("translation") or None,
            tafsir_text=it.get("tafsir") or None,
            image_path=image_path,
        )
        print(f"✅ ثبت شد (شناسه {item_id}): {title}")
        added += 1

    print(f"\nنتیجه نهایی: {added} مورد جدید اضافه شد، {updated} مورد به‌روزرسانی شد، {skipped} مورد رد شد.")


if __name__ == "__main__":
    main()
