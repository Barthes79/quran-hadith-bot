"""
افزودن آیتم «دعای روز چهارم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_4   (mafitem_ramadan_day_4)
category: ramadan_days
"""

from database import add_mafatih_item

SLUG = "ramadan_day_4"
CATEGORY = "ramadan_days"
TITLE = "دعای روز چهارم ماه مبارک رمضان"

ARABIC_TEXT = """اللَّهُمَّ قَوِّنی فیهِ عَلی اِقامَةِ اَمْرِکَ وَاَذِقْنی فیهِ حَلاوَةَ ذِکْرِکَ وَاَوْزِعْنی فیهِ لاَِداءِ شُکْرِکَ بِکَرَمِکَ وَاحْفَظْنی فیهِ بِحِفْظِکَ وَسِتْرِکَ یا اَبْصَرَ النّاظِرینَ.
خدایا در این ماه برای برپاداشتن امرت نیرومندم ساز، و شیرینی یاد خودت را به من بچشان، و ادای شکرت را به من الهام کن، و به نگهداری و پوششت نگاهم دار، ای بیناترین بینندگان.
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
