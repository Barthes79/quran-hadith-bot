"""
افزودن آیتم «دعای روز اول ماه رمضان» به دیتابیس مفاتیح‌الجنان.

slug: ramadan_day_1   (دکمه‌ی موجود در get_keyboard_for_ramadan_days -> mafitem_ramadan_day_1)
category: ramadan_days
"""

from database import add_mafatih_item

SLUG = "ramadan_day_1"
CATEGORY = "ramadan_days"
TITLE = "دعای روز اول ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ اجْعَلْ صِیامی فیهِ صِیامَ الصّائِمینَ وَقِیامی فیهِ قِیامَ الْقائِمینَ وَنَبِّهْنی فیهِ عَنْ نَوْمَةِ الْغافِلینَ وَهَبْ لی جُرْمی فیهِ یا اِلهَ الْعالَمینَ وَاعْفُ عَنّی یا عافِیاً عَنِ الْمُجْرِمینَ.
خدایا قرار بده روزه‌ی مرا در آن روزه‌ی روزه‌داران واقعی، و قیام و عبادتم را در آن، قیام شب‌زنده‌داران؛ و بیدارم فرما در آن از خواب بی‌خبران، و ببخش به من گناهم را در این روز، ای معبود جهانیان، و درگذر از من، ای بخشنده‌ی گناهکاران.
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
