"""
افزودن آیتم «دعای روز یازدهم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_11   (mafitem_ramadan_day_11)
category: ramadan_days

منبع: jamaran.news / erfan.ir - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_11"
CATEGORY = "ramadan_days"
TITLE = "دعای روز یازدهم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ حَبِّبْ اِلَیَّ فیهِ الاِْحْسانَ وَکَرِّهْ اِلَیَّ فیهِ الْفُسُوقَ وَالْعِصْیانَ وَحَرِّمْ عَلَیَّ فیهِ السَّخَطَ وَالنّیرانَ بِعَوْنِکَ یا غِیاثَ الْمُسْتَغیثینَ.
خدایا، در این ماه نیکی را نزد من پسندیده گردان، و نافرمانی و گناه را در نظرم ناخوشایند ساز، و خشم و آتش برافروخته را بر من حرام گردان، به یاری‌ات، ای فریادرس دادخواهان.
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
