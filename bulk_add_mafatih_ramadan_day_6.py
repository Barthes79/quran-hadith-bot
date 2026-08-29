"""
افزودن آیتم «دعای روز ششم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_6   (mafitem_ramadan_day_6)
category: ramadan_days

منبع: ترجمه استاد انصاریان (erfan.ir) / ahlolbait.com - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_6"
CATEGORY = "ramadan_days"
TITLE = "دعای روز ششم ماه مبارک رمضان"

ARABIC_TEXT = """اللَّهُمَّ لا تَخْذُلْنی فیهِ لِتَعَرُّضِ مَعْصِیَتِکَ وَلا تَضْرِبْنی بِسِیاطِ نَقِمَتِکَ وَزَحْزِحْنی فیهِ مِنْ مُوجِباتِ سَخَطِکَ بِمَنِّکَ وَاَیادیکَ یا مُنْتَهی رَغْبَةِ الرّاغِبینَ.
خدایا مرا در این روز به واسطه‌ی ارتکاب نافرمانی‌ات خوار مساز، و به تازیانه‌ی خشم و عذابت نزن، و از موجبات خشمت دورم گردان، به مِنّت و نعمت‌هایت، ای نهایتِ آرزوی مشتاقان.
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
