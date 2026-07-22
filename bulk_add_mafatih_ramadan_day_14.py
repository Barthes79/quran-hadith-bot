"""
افزودن آیتم «دعای روز چهاردهم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_14   (mafitem_ramadan_day_14)
category: ramadan_days

منبع: jamaran.news / tabnak.ir - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_14"
CATEGORY = "ramadan_days"
TITLE = "دعای روز چهاردهم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ لا تُؤاخِذْنی فیهِ بِالْعَثَراتِ وَاَقِلْنی فیهِ مِنَ الْخَطایا وَالْهَفَواتِ وَلا تَجْعَلْنی فیهِ غَرَضاً لِلْبَلایا وَالاْفاتِ بِعِزَّتِکَ یا عِزَّ الْمُسْلِمینَ.
خدایا مرا در این روز به لغزش‌ها مؤاخذه نکن، و از خطاها و لغزش‌ها درگذر، و مرا در آن هدف بلاها و آفت‌ها قرار نده، به عزتت، ای عزت‌بخش مسلمانان.
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
