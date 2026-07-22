"""
افزودن آیتم «دعای روز هفتم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_7   (mafitem_ramadan_day_7)
category: ramadan_days

منبع: jamaran.news / erfan.ir - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_7"
CATEGORY = "ramadan_days"
TITLE = "دعای روز هفتم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ اَعِنّی فیهِ عَلی صِیامِهِ وَقِیامِهِ وَجَنِّبْنی فیهِ مِنْ هَفَواتِهِ وَآثامِهِ وَارْزُقْنی فیهِ ذِکْرَکَ بِدَوامِهِ بِتَوْفیقِکَ یا هادِیَ الْمُضِلّینَ.
خدایا مرا در این روز بر روزه‌داری و شب‌زنده‌داری‌اش یاری کن، و از لغزش‌ها و گناهانش دورم گردان، و ذکرِ دائمی خودت را در آن روزی‌ام کن، به توفیق خودت، ای راهنمای گمراهان.
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
