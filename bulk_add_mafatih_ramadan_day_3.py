"""
افزودن آیتم «دعای روز سوم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_3   (mafitem_ramadan_day_3)
category: ramadan_days
"""

from database import add_mafatih_item

SLUG = "ramadan_day_3"
CATEGORY = "ramadan_days"
TITLE = "دعای روز سوم ماه مبارک رمضان"

ARABIC_TEXT = """اللَّهُمَّ ارْزُقْنی فیهِ الذِّهْنَ وَالتَّنْبیهَ وَباعِدْنی فیهِ مِنَ السَّفاهَةِ وَالتَّمْویهِ وَاجْعَلْ لی نَصیباً مِنْ کُلِّ خَیْرٍ تُنْزِلُ فیهِ بِجُودِکَ یا اَجْوَدَ الاْجْوَدینَ.
خدایا در این ماه به من تیزهوشی و بیداری عنایت فرما، و از بی‌خردی و اشتباه دورم ساز، و از هر خیری که در این ماه نازل می‌کنی برایم بهره‌ای قرار ده، به حق جودت، ای جودمندترین جودمندان.
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
