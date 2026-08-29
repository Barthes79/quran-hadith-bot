"""
افزودن آیتم «دعای روز بیست‌ونهم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_29   (mafitem_ramadan_day_29)
category: ramadan_days

منبع: jamaran.news / ziaossalehin.ir - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_29"
CATEGORY = "ramadan_days"
TITLE = "دعای روز بیست‌ونهم ماه مبارک رمضان"

ARABIC_TEXT = """اللَّهُمَّ غَشِّنی فیهِ بِالرَّحْمَةِ وَارْزُقْنی فیهِ التَّوْفیقَ وَالْعِصْمَةَ وَطَهِّرْ قَلْبی مِنْ غَیاهِبِ التُّهْمَةِ یا رَحیماً بِعِبادِهِ الْمُؤْمِنینَ.
خدایا مرا در این روز به رحمتت فراگیر، و توفیق و خودنگهداری از گناه را روزی‌ام کن، و دلم را از تاریکی‌های تهمت پاک گردان، ای مهربان به بندگان با ایمانش.
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
