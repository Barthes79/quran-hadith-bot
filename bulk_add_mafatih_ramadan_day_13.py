"""
افزودن آیتم «دعای روز سیزدهم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_13   (mafitem_ramadan_day_13)
category: ramadan_days

منبع: jamaran.news / namnak.com - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_13"
CATEGORY = "ramadan_days"
TITLE = "دعای روز سیزدهم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ طَهِّرْنی فیهِ مِنَ الدَّنَسِ وَالاْقْذارِ وَصَبِّرْنی فیهِ عَلی کائِناتِ الاْقْدارِ وَوَفِّقْنی فیهِ لِلتُّقی وَصُحْبَةِ الاَْبْرارِ بِعَوْنِکَ یا قُرَّةَ عَیْنِ الْمَساکینَ.
خدایا مرا در این روز از چرک و پلیدی پاک گردان، و شکیبایی‌ام ده در برابر آنچه از تقدیرها که پیش می‌آید، و توفیقم ده در آن برای تقوا و همنشینی با نیکان، به یاری‌ات، ای روشنی چشم مستمندان.
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
