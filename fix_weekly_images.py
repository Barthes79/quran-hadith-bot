import database as db

# نگاشت آیدی هر روز به مسیر عکس مربوطه (طبق فایل‌های موجود در پوشه images/)
IMAGE_MAP = {
    85: "images/shanbe.jpg.png",
    86: "images/yekshanbe.jpg.png",
    87: "images/doshanbe.png",
    88: "images/seshanbe.png",
    89: "images/chaharshanbe.png",
    90: "images/panjshanbe.png",
    91: "images/jome.png",
}

for item_id, path in IMAGE_MAP.items():
    db.update_mafatih_image(item_id, path)
    print(f"✅ id={item_id} -> {path}")

print("\nتمام شد. حالا بررسی نهایی:")
for item_id in IMAGE_MAP:
    row = db.get_mafatih_item(item_id)
    print(item_id, row["title"], "->", row["image_path"])
