"""
افزودن آیتم «دعای روز بیست‌وهشتم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_28   (mafitem_ramadan_day_28)
category: ramadan_days

منبع: ziaossalehin.ir / jamaran.news - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_28"
CATEGORY = "ramadan_days"
TITLE = "دعای روز بیست‌وهشتم ماه مبارک رمضان"

ARABIC_TEXT = """اللَّهُمَّ وَفِّرْ حَظّی فیهِ مِنَ النَّوافِلِ وَاَکْرِمْنی فیهِ بِاِحْضارِ الْمَسائِلِ وَقَرِّبْ فیهِ وَسیلَتی اِلَیْکَ مِنْ بَیْنِ الْوَسائِلِ یا مَنْ لا یَشْغَلُهُ اِلْحاحُ الْمُلِحّینَ.
خدایا بهره‌ام را در این روز از نمازهای مستحبی افزون کن، و مرا با برآورده‌شدن حاجاتم گرامی دار، و وسیله‌ام را به‌سویت از میان همه‌ی وسیله‌ها نزدیک گردان، ای که اصرارِ اصرارکنندگان سرگرمت نمی‌کند.
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
