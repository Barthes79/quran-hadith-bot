"""
افزودن 6 حدیث جدید (بچ 15) و تنظیم مستقیم دسته‌بندی هرکدام،
بدون فراخوانی recategorize_all_hadiths.
⚠️ این اسکریپت را فقط یک‌بار اجرا کن.
نحوه اجرا (روی Railway از تب Console):
    python add_hadiths_batch15.py
"""
import json
from database import init_db, add_hadith, update_hadith_category

CATEGORIES = [
    "🌿 اخلاق و رفتار",
    "🕌 ایمان و عبادت",
    "🕌 ایمان و عبادت",
    "🕌 ایمان و عبادت",
    "❤️ خانواده و محبت",
    "⚖️ عدالت و حقوق",
]  # به همون ترتیب حدیث‌ها در JSON


def main():
    init_db()
    with open("hadiths_batch15_new.json", encoding="utf-8") as f:
        hadiths = json.load(f)
    assert len(hadiths) == len(CATEGORIES), "تعداد حدیث‌ها و دسته‌ها برابر نیست!"
    for h, category in zip(hadiths, CATEGORIES):
        hadith_id = add_hadith(
            arabic_text=h["arabic"], translation_text=h["translation"],
            narrator=h["narrator"], source_book=h["source"],
            chapter=h.get("chapter") or None, hadith_number=h.get("number") or None,
            tafsir_text=h.get("tafsir") or None, topics=h.get("topics"),
        )
        update_hadith_category(hadith_id, category)
        print(f"✅ ثبت و دسته‌بندی شد (شناسه {hadith_id}): {h['translation'][:35]}...")
    print(f"\nنتیجه نهایی: {len(hadiths)} حدیث جدید اضافه و دسته‌بندی شد.")


if __name__ == "__main__":
    main()
