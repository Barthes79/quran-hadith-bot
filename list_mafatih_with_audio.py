"""
لیست تمام دعاهایی که در دیتابیس audio_file_id دارند — برای اینکه بدانید
باید برای کدام‌ها دوباره صدا آپلود کنید (چون احتمالاً همه‌ی این file_idها
مال یک بات دیگر بوده‌اند و برای این بات نامعتبرند).

نحوه اجرا:
    python list_mafatih_with_audio.py
"""
from database import get_connection

conn = get_connection()
rows = conn.execute(
    "SELECT id, title, category, slug FROM mafatih WHERE audio_file_id IS NOT NULL AND audio_file_id != '' ORDER BY category, title"
).fetchall()
conn.close()

if not rows:
    print("هیچ دعایی audio_file_id ندارد.")
else:
    print(f"{len(rows)} دعا فایل صوتی دارند (که احتمالاً باید دوباره آپلود شوند):\n")
    for r in rows:
        identifier = r["slug"] if r["slug"] else r["id"]
        print(f"/setmafaudio {identifier}   ->  {r['title']}  (دسته: {r['category']})")
