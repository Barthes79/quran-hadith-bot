"""
افزودن آیتم «دعای روز بیست‌وچهارم ماه رمضان» به دیتابیس مفاتیح‌الجنان.
slug: ramadan_day_24   (mafitem_ramadan_day_24)
category: ramadan_days

منبع: jamaran.news / tabnak.ir - تأیید شده با جستجوی وب.
"""

from database import add_mafatih_item

SLUG = "ramadan_day_24"
CATEGORY = "ramadan_days"
TITLE = "دعای روز بیست‌وچهارم ماه مبارک رمضان"

ARABIC_TEXT = """بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِیمِ

اللَّهُمَّ اِنّی اَسْئَلُکَ فیهِ ما یُرْضیکَ وَاَعُوذُ بِکَ مِمّا یُؤْذیکَ وَاَسْئَلُکَ التَّوْفیقَ فیهِ لاَِنْ اُطیعَکَ وَلا اَعْصِیَکَ یا جَوادَ السّائِلینَ.
خدایا از تو می‌خواهم در این روز آنچه تو را خشنود سازد، و به تو پناه می‌برم از آنچه تو را بیازارد، و از تو توفیق می‌خواهم که فرمانت برم و نافرمانی‌ات نکنم، ای بخشنده به خواهندگان.
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
