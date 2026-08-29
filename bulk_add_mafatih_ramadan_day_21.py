"""
افزودن آیتم «دعای روز بیست‌ویکم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_21   (mafitem_ramadan_day_21)
category: ramadan_days

توجه: این آیتم متفاوت است از «qadr_21» (اعمال شب قدر بیست‌ویکم، زیرمنوی
جداگانه‌ی «شب‌های قدر»). این‌جا دعای روزانه‌ی عمومیِ روز بیست‌ویکم رمضان است.

منبع: jamaran.news - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_21"
CATEGORY = "ramadan_days"
TITLE = "دعای روز بیست‌ویکم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ اجْعَلْ لی فیهِ اِلی مَرْضاتِکَ دَلیلاً وَلا تَجْعَلْ لِلشَّیْطانِ فیهِ عَلَیَّ سَبیلاً وَاجْعَلِ الْجَنَّةَ لی مَنْزِلاً وَمَقیلاً یا قاضِیَ حَوائِجِ الطّالِبینَ.
خدایا در این روز راهنمایی به‌سوی خشنودی‌ات را برایم قرار ده، و شیطان را در آن بر من راهی مده، و بهشت را برایم منزل و آسایشگاه گردان، ای برآورنده‌ی حاجت‌های خواهندگان.
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
