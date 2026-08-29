"""
افزودن آیتم «دعای روز دوم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_2   (mafitem_ramadan_day_2)
category: ramadan_days
"""

from database import add_mafatih_item

SLUG = "ramadan_day_2"
CATEGORY = "ramadan_days"
TITLE = "دعای روز دوم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ قَرِّبْنی فیهِ اِلی مَرْضاتِکَ وَجَنِّبْنی فیهِ مِنْ سَخَطِکَ وَنَقِماتِکَ وَوَفِّقْنی فیهِ لِقِرائَةِ آیاتِکَ بِرَحْمَتِکَ یا اَرْحَمَ الرّاحِمینَ.
پروردگارا، در این روز پربرکت مرا به رضایت و خشنودی خویش نزدیک کن و از خشم و عذابت دورم گردان؛ و توفیقم ده تا خاضعانه تسلیم تو باشم و تو را از هرچه به اندیشه‌ام درآید بزرگ‌تر بدانم. خدایا در این ماه توفیق تلاوت قرآن را بر من ارزانی دار تا چشمم به درخشش آیاتت روشن و منور شود و قلبم با هدایتِ کتابت آرام گیرد؛ به حق رحمتت، ای رحم‌کننده‌ترین رحم‌کنندگان. آمین.
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
