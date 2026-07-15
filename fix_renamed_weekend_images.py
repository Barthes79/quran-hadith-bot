import database as db

db.update_mafatih_image(85, "images/shanbe.png")
db.update_mafatih_image(86, "images/yekshanbe.png")

print("✅ مسیر عکس شنبه و یکشنبه به‌روزرسانی شد.")

for item_id in (85, 86):
    row = db.get_mafatih_item(item_id)
    print(item_id, row["title"], "->", row["image_path"])
