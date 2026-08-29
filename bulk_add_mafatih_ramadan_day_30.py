"""
افزودن آیتم «دعای روز سی‌ام ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_30   (mafitem_ramadan_day_30)
category: ramadan_days

آخرین آیتم از سری ۳۰ دعای روزانه‌ی ماه رمضان.

منبع: eghtesadonline.com / iribnews.ir / beytoote.com - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_30"
CATEGORY = "ramadan_days"
TITLE = "دعای روز سی‌ام ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ اجْعَلْ صِیامی فیهِ بِالشُّکْرِ وَالْقَبُولِ عَلی ما تَرْضاهُ وَیَرْضاهُ الرَّسُولُ مُحْکَمَةً فُرُوعُهُ بِالاُْصُولِ بِحَقِّ سَیِّدِنا مُحَمَّدٍ وَآلِهِ الطّاهِرینَ وَالْحَمْدُ لِلّهِ رَبِّ الْعالَمینَ.
خدایا روزه‌ام را در این ماه مورد سپاس و پذیرش قرار ده، بر طبق آنچه تو و پیامبرت آن را می‌پسندید، درحالی‌که فروعش بر اصولش استوار باشد؛ به‌حق سرورمان محمد و خاندان پاکش، و ستایش ویژه‌ی پروردگار جهانیان است.
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
