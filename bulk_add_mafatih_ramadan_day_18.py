"""
افزودن آیتم «دعای روز هجدهم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_18   (mafitem_ramadan_day_18)
category: ramadan_days

منبع: tehran.ivo.ir (دامپزشکی استان تهران) - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_18"
CATEGORY = "ramadan_days"
TITLE = "دعای روز هجدهم ماه مبارک رمضان"

ARABIC_TEXT = """اللَّهُمَّ نَبِّهْنی فیهِ لِبَرَکاتِ اَسْحارِهِ وَنَوِّرْ فیهِ قَلْبی بِضِیاءِ اَنْوارِهِ وَخُذْ بِکُلِّ اَعْضائی اِلَی اتِّباعِ آثارِهِ بِنُورِکَ یا مُنَوِّرَ قُلُوبِ الْعارِفینَ.
خدایا مرا در این ماه به برکت‌های سحرهایش آگاه کن، و دلم را با روشنایی انوارش روشنی بخش، و همه‌ی اعضایم را به پیروی از آثارش بگمار، به نور خودت، ای روشنی‌بخش دل‌های عارفان.
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
