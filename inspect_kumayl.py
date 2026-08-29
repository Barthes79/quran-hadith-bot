"""
اسکریپت تشخیصی: تمام ردیف‌های جدول mafatih که عنوانشان شامل «کمیل» است را
با جزئیات کامل نشان می‌دهد (بدون حذف چیزی) تا مشخص شود آیا واقعاً دو دعای
متفاوت هستند یا دو ثبتِ همان دعا با عنوان کمی متفاوت.

نحوه اجرا:
    python inspect_kumayl.py
"""
from database import get_connection

conn = get_connection()
rows = conn.execute(
    "SELECT * FROM mafatih WHERE title LIKE ? OR arabic_text LIKE ?",
    ("%کمیل%", "%کمیل%"),
).fetchall()
conn.close()

if not rows:
    print("هیچ ردیفی با «کمیل» پیدا نشد.")
else:
    print(f"{len(rows)} ردیف پیدا شد:\n")
    for r in rows:
        print(f"id={r['id']}")
        print(f"  عنوان دقیق: {r['title']!r}")
        print(f"  دسته: {r['category']}")
        print(f"  slug: {r['slug']!r}")
        print(f"  صوت: {'دارد' if r['audio_file_id'] else 'ندارد'}")
        print(f"  عکس: {'دارد' if r['image_path'] else 'ندارد'}")
        print(f"  طول متن عربی: {len(r['arabic_text'] or '')}")
        print(f"  طول ترجمه: {len(r['translation_text'] or '')}")
        print()
