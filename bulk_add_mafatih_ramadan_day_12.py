"""
افزودن آیتم «دعای روز دوازدهم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_12   (mafitem_ramadan_day_12)
category: ramadan_days

منبع: beytoote.com / namnak.com - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_12"
CATEGORY = "ramadan_days"
TITLE = "دعای روز دوازدهم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ زَیِّنّی فیهِ بِالسَّتْرِ وَالْعَفافِ وَاسْتُرْنی فیهِ بِلِباسِ الْقُنُوعِ وَالْکَفافِ وَاحْمِلْنی فیهِ عَلَی الْعَدْلِ وَالاِْنْصافِ وَاَمِنّی فیهِ مِنْ کُلِّ ما اَخافُ بِعِصْمَتِکَ یا عِصْمَةَ الْخائِفینَ.
خدایا در این ماه مرا با پوشش و عفت زینت ده، و با جامه‌ی قناعت و بسنده‌کردن بپوشان، و بر رعایت عدل و انصاف وادارم کن، و از هر آنچه می‌ترسم در امانم دار، به نگهداری‌ات، ای نگهدارنده‌ی ترسیدگان.
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
