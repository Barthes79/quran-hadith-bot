"""
اجرای این فایل چند حدیث نمونه به دیتابیس اضافه می‌کند تا بتوانید
ساختار ربات را قبل از وارد کردن داده‌های واقعی تست کنید.

اجرا:  python seed_sample_data.py
"""
from database import init_db, add_hadith

init_db()

sample_hadiths = [
    {
        "arabic_text": "الصَّبْرُ مِفْتَاحُ الْفَرَجِ",
        "translation_text": "صبر، کلید گشایش (فرج) است.",
        "narrator": "امام علی (ع)",
        "source_book": "غررالحکم",
        "chapter": "باب الصبر",
        "hadith_number": "1",
        "topics": ["صبر", "امید"],
    },
    {
        "arabic_text": "مَنْ عَرَفَ نَفْسَهُ فَقَدْ عَرَفَ رَبَّهُ",
        "translation_text": "هر کس خودش را بشناسد، پروردگارش را شناخته است.",
        "narrator": "پیامبر اکرم (ص)",
        "source_book": "غررالحکم",
        "chapter": "باب معرفت النفس",
        "hadith_number": "2",
        "topics": ["خودشناسی", "معرفت"],
    },
    {
        "arabic_text": "خَيْرُ النَّاسِ مَنْ يَنْفَعُ النَّاسَ",
        "translation_text": "بهترین مردم کسی است که به مردم سود برساند.",
        "narrator": "پیامبر اکرم (ص)",
        "source_book": "بحارالانوار",
        "chapter": "باب الاحسان",
        "hadith_number": "3",
        "topics": ["نیکوکاری", "اخلاق اجتماعی"],
    },
]

for h in sample_hadiths:
    hid = add_hadith(
        h["arabic_text"], h["translation_text"], h["narrator"],
        h["source_book"], h["chapter"], h["hadith_number"], topics=h["topics"],
    )
    print(f"✅ حدیث ثبت شد با شناسه {hid}: {h['translation_text'][:30]}...")

print("\nداده‌های نمونه با موفقیت اضافه شدند.")
