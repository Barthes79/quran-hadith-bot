"""
افزودن آیتم «دعای روز بیست‌ودوم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_22   (mafitem_ramadan_day_22)
category: ramadan_days

منبع: jamaran.news - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_22"
CATEGORY = "ramadan_days"
TITLE = "دعای روز بیست‌ودوم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ افْتَحْ لی فیهِ اَبْوابَ فَضْلِکَ وَاَنْزِلْ عَلَیَّ فیهِ بَرَکاتِکَ وَوَفِّقْنی فیهِ لِمُوجِباتِ مَرْضاتِکَ وَاَسْکِنّی فیهِ بُحْبُوحاتِ جَنّاتِکَ یا مُجیبَ دَعْوَةِ الْمُضْطَرّینَ.
خدایا در این روز درهای فضل خود را برایم بگشا، و برکاتت را بر من فرود آر، و مرا در آن به موجبات خشنودی‌ات توفیق ده، و مرا در وسط‌ترین جای بهشت‌هایت جای ده، ای اجابت‌کننده‌ی دعای درماندگان.
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
