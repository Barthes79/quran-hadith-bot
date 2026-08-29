"""
افزودن آیتم «دعای روز نهم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_9   (mafitem_ramadan_day_9)
category: ramadan_days

منبع: jamaran.news / namnak.com - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_9"
CATEGORY = "ramadan_days"
TITLE = "دعای روز نهم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ اجْعَلْ لی فیهِ نَصیباً مِنْ رَحْمَتِکَ الْواسِعَةِ وَاهْدِنی فیهِ لِبَراهینِکَ السّاطِعَةِ وَخُذْ بِناصِیَتی اِلی مَرْضاتِکَ الْجامِعَةِ بِمَحَبَّتِکَ یا اَمَلَ الْمُشْتاقینَ.
خدایا در این روز، بهره‌ای از رحمت گسترده‌ات نصیبم گردان، و مرا به برهان‌های درخشانت هدایت کن، و زمامم را به‌سوی خشنودی همه‌جانبه‌ات بکش، به محبت خودت، ای آرزوی مشتاقان.
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
