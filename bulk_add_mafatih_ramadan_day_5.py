"""
افزودن آیتم «دعای روز پنجم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_5   (mafitem_ramadan_day_5)
category: ramadan_days
"""

from database import add_mafatih_item

SLUG = "ramadan_day_5"
CATEGORY = "ramadan_days"
TITLE = "دعای روز پنجم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ اجْعَلْنی فیهِ مِنَ الْمُسْتَغْفِرینَ وَاجْعَلْنی فیهِ مِنْ عِبادِکَ الصّالِحینَ الْقانِتینَ وَاجْعَلْنی فیهِ مِنْ اَوْلِیائِکَ الْمُقَرَّبینَ بِرَأْفَتِکَ یا اَرْحَمَ الرّاحِمینَ.
خدایا در این روز مرا از آمرزش‌خواهان قرار ده، و مرا از بندگان شایسته و فرمانبردارت قرار ده، و مرا از دوستان نزدیکت، به مهربانی خودت، قرار ده، ای مهربان‌ترین مهربانان.
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
