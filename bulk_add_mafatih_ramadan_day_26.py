"""
افزودن آیتم «دعای روز بیست‌وششم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_26   (mafitem_ramadan_day_26)
category: ramadan_days

منبع: erfan.ir (ترجمه استاد انصاریان) - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_26"
CATEGORY = "ramadan_days"
TITLE = "دعای روز بیست‌وششم ماه مبارک رمضان"

ARABIC_TEXT = """اللَّهُمَّ اجْعَلْ سَعْیی فیهِ مَشْکُوراً وَذَنْبی فیهِ مَغْفُوراً وَعَمَلی فیهِ مَقْبُولاً وَعَیْبی فیهِ مَسْتُوراً یا اَسْمَعَ السّامِعینَ.
خدایا کوششم را در این روز مورد سپاس، و گناهم را آمرزیده، و عملم را پذیرفته، و عیبم را پوشیده قرار ده، ای شنواترین شنوایان.
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
