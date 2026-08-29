"""
افزودن آیتم «دعای روز نوزدهم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_19   (mafitem_ramadan_day_19)
category: ramadan_days

توجه: این آیتم متفاوت است از قبلاً ساخته‌شده «qadr_19» (اعمال شب قدر نوزدهم،
که خودش زیرمنوی جداگانه‌ای زیر «شب‌های قدر» است). این‌جا صحبت از دعای روزانه‌ی
عمومیِ روز نوزدهم رمضان است که در منوی «دعای روزانه» می‌آید.

منبع: tehran.ivo.ir / borna.news - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_19"
CATEGORY = "ramadan_days"
TITLE = "دعای روز نوزدهم ماه مبارک رمضان"

ARABIC_TEXT = """اللَّهُمَّ وَفِّرْ فیهِ حَظّی مِنْ بَرَکاتِهِ وَسَهِّلْ سَبیلی اِلی خَیْراتِهِ وَلا تَحْرِمْنی قَبُولَ حَسَناتِهِ یا هادِیاً اِلَی الْحَقِّ الْمُبینِ.
خدایا در این روز بهره‌ام را از برکاتش وافر گردان، و راهم را به‌سوی نیکی‌هایش هموار کن، و از پذیرفته‌شدن نیکی‌هایم در آن محرومم مساز، ای هدایت‌کننده به‌سوی حق آشکار.
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
