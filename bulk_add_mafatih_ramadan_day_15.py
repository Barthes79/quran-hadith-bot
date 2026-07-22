"""
افزودن آیتم «دعای روز پانزدهم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_15   (mafitem_ramadan_day_15)
category: ramadan_days

منبع: mehrnews.com / jamaran.news - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_15"
CATEGORY = "ramadan_days"
TITLE = "دعای روز پانزدهم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ ارْزُقْنی فیهِ طاعَةَ الْخاشِعینَ وَاشْرَحْ فیهِ صَدْری بِاِنابَةِ الْمُخْبِتینَ بِاَمانِکَ یا اَمانَ الْخائِفینَ.
خدایا در این روز فرمانبرداری فروتنان را روزی‌ام کن، و سینه‌ام را در آن با بازگشتِ خاضعانه‌ی دلدادگان بگشا، به امان‌دادنت، ای امان‌دهنده‌ی هراسندگان.
"""

TRANSLATION_TEXT = None
AUDIO_FILE_ID = None


def main():
    add_mafatih_item(
        slug=SLUG,
        category=CATEGORY,
        title=TITLE,
        arabic_text=ARABIC_TEXT.strip(),
        translation_text=TRANSLATION_TEXT,
        audio_file_id=AUDIO_FILE_ID,
    )
    print(f"✅ آیتم «{TITLE}» (slug={SLUG}) ثبت/بروزرسانی شد. طول متن: {len(ARABIC_TEXT.strip())} کاراکتر.")


if __name__ == "__main__":
    main()
