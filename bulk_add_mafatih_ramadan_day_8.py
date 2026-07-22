"""
افزودن آیتم «دعای روز هشتم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_8   (mafitem_ramadan_day_8)
category: ramadan_days

منبع: rokna.net / erfan.ir - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_8"
CATEGORY = "ramadan_days"
TITLE = "دعای روز هشتم ماه مبارک رمضان"

ARABIC_TEXT = """اللَّهُمَّ ارْزُقْنی فیهِ رَحْمَةَ الاْیْتامِ وَاِطْعامَ الطَّعامِ وَاِفْشاءَ السَّلامِ وَصُحْبَةَ الْکِرامِ بِطَوْلِکَ یا مَلْجَاَ الاْمِلینَ.
خدایا در این روز، مهربانی با یتیمان و اطعام نیازمندان و گستراندن سلام و همنشینی با بزرگواران را روزی‌ام گردان، به بزرگواری‌ات، ای پناهگاه آرزومندان.
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
