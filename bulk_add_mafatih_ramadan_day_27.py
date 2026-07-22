"""
افزودن آیتم «دعای روز بیست‌وهفتم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_27   (mafitem_ramadan_day_27)
category: ramadan_days

منبع: mashreghnews.ir / namnak.com - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_27"
CATEGORY = "ramadan_days"
TITLE = "دعای روز بیست‌وهفتم ماه مبارک رمضان"

ARABIC_TEXT = """اللَّهُمَّ ارْزُقْنی فیهِ فَضْلَ لَیْلَةِ الْقَدْرِ وَصَیِّرْ اُمُوری فیهِ مِنَ الْعُسْرِ اِلَی الْیُسْرِ وَاقْبَلْ مَعاذیری وَحُطَّ عَنّی الذَّنْبَ وَالْوِزْرَ یا رَؤُوفاً بِعِبادِهِ الصّالِحینَ.
خدایا روزی‌ام کن در این روز فضیلت شب قدر را، و کارهایم را از سختی به آسانی بگردان، و عذرهایم را بپذیر، و گناه و بار گران را از من فرو ریز، ای مهربان به بندگان شایسته‌ی خویش.
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
