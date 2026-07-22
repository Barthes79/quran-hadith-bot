"""
افزودن آیتم «دعای روز بیست‌وپنجم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_25   (mafitem_ramadan_day_25)
category: ramadan_days

منبع: جماران / صدا و سیما - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_25"
CATEGORY = "ramadan_days"
TITLE = "دعای روز بیست‌وپنجم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ اجْعَلْنی فیهِ مُحِبّاً لاَِوْلِیائِکَ وَمُعادِیاً لاَِعْدائِکَ مُسْتَنّاً بِسُنَّةِ خاتَمِ اَنْبِیائِکَ یا عاصِمَ قُلُوبِ النَّبِیّینَ.
خدایا مرا در این روز دوستدار دوستانت و دشمن دشمنانت قرار ده، و پیرو راه و روش خاتم پیامبرانت گردان، ای نگهدارنده‌ی دل‌های پیامبران.
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
