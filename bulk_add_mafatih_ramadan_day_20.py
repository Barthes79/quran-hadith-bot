"""
افزودن آیتم «دعای روز بیستم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_20   (mafitem_ramadan_day_20)
category: ramadan_days

منبع: jamaran.news / imna.ir - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_20"
CATEGORY = "ramadan_days"
TITLE = "دعای روز بیستم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ افْتَحْ لی فیهِ اَبْوابَ الْجِنانِ وَاَغْلِقْ عَنّی فیهِ اَبْوابَ النّیرانِ وَوَفِّقْنی فیهِ لِتِلاوَةِ الْقُرْآنِ یا مُنَزِّلَ السَّکینَةِ فی قُلُوبِ الْمُؤْمِنینَ.
خدایا در این روز درهای بهشت را به رویم بگشا، و درهای آتش دوزخ را از من ببند، و مرا به تلاوت قرآن توفیق ده، ای نازل‌کننده‌ی آرامش در دل‌های مؤمنان.
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
