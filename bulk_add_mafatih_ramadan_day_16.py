"""
افزودن آیتم «دعای روز شانزدهم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_16   (mafitem_ramadan_day_16)
category: ramadan_days

منبع: erfan.ir (ترجمه استاد انصاریان) / jamaran.news - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_16"
CATEGORY = "ramadan_days"
TITLE = "دعای روز شانزدهم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ وَفِّقْنی فیهِ لِمُوافَقَةِ الاَْبْرارِ وَجَنِّبْنی فیهِ مُرافَقَةَ الاَْشْرارِ وَآوِنی فیهِ بِرَحْمَتِکَ اِلی دارِ الْقَرارِ بِاِلهِیَّتِکَ یا اِلهَ الْعالَمینَ.
خدایا، مرا در این ماه به همراهی و همسویی با نیکان توفیق ده، و از همنشینی با بدان دورم کن، و به رحمتت مرا به خانه‌ی آرامش جای ده، به پرستیدگی‌ات، ای پرستیده‌ی جهانیان.
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
