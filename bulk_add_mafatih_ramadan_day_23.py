"""
افزودن آیتم «دعای روز بیست‌وسوم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_23   (mafitem_ramadan_day_23)
category: ramadan_days

توجه: این آیتم متفاوت است از «qadr_23» (اعمال شب قدر بیست‌وسوم، زیرمنوی
جداگانه‌ی «شب‌های قدر»). این‌جا دعای روزانه‌ی عمومیِ روز بیست‌وسوم رمضان است.

منبع: hodanet.net (سی روز سی دعا) - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_23"
CATEGORY = "ramadan_days"
TITLE = "دعای روز بیست‌وسوم ماه مبارک رمضان"

ARABIC_TEXT = """اللَّهُمَّ اغْسِلْنی فیهِ مِنَ الذُّنُوبِ وَطَهِّرْنی فیهِ مِنَ الْعُیُوبِ وَامْتَحِنْ قَلْبی فیهِ بِتَقْوَی الْقُلُوبِ یا مُقیلَ عَثَراتِ الْمُذْنِبینَ.
خدایا مرا در این روز از گناهان شست‌وشو ده و پاکیزه گردان، و مرا از هر عیب و نقصی پاک ساز، و دلم را در آن به تقوای دل‌ها بیازمای، ای پذیرنده‌ی عذر لغزش‌های گناهکاران.
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
