"""
افزودن ۴۳ حدیث جدید (بچ ۷) و تنظیم مستقیم دسته‌بندی هرکدام،
بدون فراخوانی recategorize_all_hadiths.

نحوه اجرا (روی Railway از تب Console، در همان پوشه‌ی پروژه):
    python add_hadiths_batch7.py
"""
import json
from database import init_db, add_hadith, update_hadith_category

CATEGORIES = [
    "⚖️ عدالت و حقوق", "💰 مال و زندگی", "👑 اهل‌بیت و ولایت", "🌿 اخلاق و رفتار",
    "🧠 علم و حکمت", "👑 اهل‌بیت و ولایت", "👑 اهل‌بیت و ولایت", "👑 اهل‌بیت و ولایت",
    "⚖️ عدالت و حقوق", "🌿 اخلاق و رفتار", "🕊️ روح و معنویت", "🧠 علم و حکمت",
    "🌿 اخلاق و رفتار", "💰 مال و زندگی", "🕊️ روح و معنویت", "🤝 مردم و جامعه",
    "👑 اهل‌بیت و ولایت", "🕌 ایمان و عبادت", "🕌 ایمان و عبادت", "👑 اهل‌بیت و ولایت",
    "👑 اهل‌بیت و ولایت", "⚖️ عدالت و حقوق", "🕌 ایمان و عبادت", "🌿 اخلاق و رفتار",
    "🌿 اخلاق و رفتار", "🕌 ایمان و عبادت", "🧠 علم و حکمت", "🌿 اخلاق و رفتار",
    "🕌 ایمان و عبادت", "👑 اهل‌بیت و ولایت", "🌱 دنیا و آخرت", "🕌 ایمان و عبادت",
    "🌿 اخلاق و رفتار", "👑 اهل‌بیت و ولایت", "🤝 مردم و جامعه", "❤️ خانواده و محبت",
    "🤝 مردم و جامعه", "❤️ خانواده و محبت", "🤝 مردم و جامعه", "🌿 اخلاق و رفتار",
    "🌿 اخلاق و رفتار", "🕌 ایمان و عبادت", "⚖️ عدالت و حقوق",
]


def main():
    init_db()
    with open("hadiths_batch7_new.json", encoding="utf-8") as f:
        hadiths = json.load(f)

    assert len(hadiths) == len(CATEGORIES), "تعداد حدیث‌ها و دسته‌ها برابر نیست!"

    for h, category in zip(hadiths, CATEGORIES):
        hadith_id = add_hadith(
            arabic_text=h["arabic"],
            translation_text=h["translation"],
            narrator=h["narrator"],
            source_book=h["source"],
            chapter=h.get("chapter") or None,
            hadith_number=h.get("number") or None,
            tafsir_text=h.get("tafsir") or None,
            topics=h.get("topics"),
        )
        update_hadith_category(hadith_id, category)
        print(f"✅ ثبت و دسته‌بندی شد (شناسه {hadith_id}): {h['translation'][:35]}...")

    print(f"\nنتیجه نهایی: {len(hadiths)} حدیث جدید اضافه و دسته‌بندی شد.")


if __name__ == "__main__":
    main()
