"""
افزودن آیتم «دعای روز هفدهم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_17   (mafitem_ramadan_day_17)
category: ramadan_days

منبع: beytoote.com / jamaran.news - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_17"
CATEGORY = "ramadan_days"
TITLE = "دعای روز هفدهم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ اهْدِنی فیهِ لِصالِحِ الاَْعْمالِ وَاقْضِ لی فیهِ الْحَوائِجَ وَالاْمالَ یا مَنْ لا یَحْتاجُ اِلَی التَّفْسیرِ وَالسُّؤالِ یا عالِماً بِما فی صُدُورِ الْعالَمینَ صَلِّ عَلی مُحَمَّدٍ وَآلِهِ الطّاهِرینَ.
خدایا، مرا در این روز به کارهای شایسته راهنمایی کن، و حاجت‌ها و آرزوهایم را برآورده ساز، ای که نیازی به شرح و پرسش نداری، ای دانا به آنچه در سینه‌های جهانیان است، بر محمد و خاندان پاکش درود فرست.
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
