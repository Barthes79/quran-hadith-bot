"""
افزودن آیتم «دعای روز دهم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_10   (mafitem_ramadan_day_10)
category: ramadan_days

منبع: magiran.com (روزنامه ایران) - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_10"
CATEGORY = "ramadan_days"
TITLE = "دعای روز دهم ماه مبارک رمضان"

ARABIC_TEXT = """اللَّهُمَّ اجْعَلْنی فیهِ مِنَ الْمُتَوَکِّلینَ عَلَیْکَ وَاجْعَلْنی فیهِ مِنَ الْفائِزینَ لَدَیْکَ وَاجْعَلْنی فیهِ مِنَ الْمُقَرَّبینَ اِلَیْکَ بِاِحْسانِکَ یا غایَةَ الطّالِبینَ.
خدایا مرا در این روز از توکل‌کنندگان بر خودت قرار ده، و از رستگاران نزد خودت قرار ده، و از مقربان درگاهت قرار ده، به احسان خودت، ای نهایتِ آرزوی خواهندگان.
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
