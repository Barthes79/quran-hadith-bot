"""
افزودن ۵۶ حدیث جدید (بچ ۵) و تنظیم مستقیم دسته‌بندی هرکدام،
بدون فراخوانی recategorize_all_hadiths (که دسته‌بندی دستی قبلی را
بازنویسی می‌کند).

نحوه اجرا (روی Railway از تب Console، در همان پوشه‌ی پروژه):
    python add_hadiths_batch5.py
"""
import json
from database import init_db, add_hadith, update_hadith_category

CATEGORIES = [
    "🤝 مردم و جامعه", "👑 اهل‌بیت و ولایت", "🌿 اخلاق و رفتار", "🌿 اخلاق و رفتار",
    "👑 اهل‌بیت و ولایت", "🌿 اخلاق و رفتار", "🕌 ایمان و عبادت", "👑 اهل‌بیت و ولایت",
    "👑 اهل‌بیت و ولایت", "🧠 علم و حکمت", "🌿 اخلاق و رفتار", "🕊️ روح و معنویت",
    "🕌 ایمان و عبادت", "🕌 ایمان و عبادت", "❤️ خانواده و محبت", "⚖️ عدالت و حقوق",
    "🕌 ایمان و عبادت", "💰 مال و زندگی", "🧠 علم و حکمت", "❤️ خانواده و محبت",
    "🕊️ روح و معنویت", "🌿 اخلاق و رفتار", "🤝 مردم و جامعه", "🕌 ایمان و عبادت",
    "🌿 اخلاق و رفتار", "🌱 دنیا و آخرت", "🕌 ایمان و عبادت", "🌿 اخلاق و رفتار",
    "🌿 اخلاق و رفتار", "🕊️ روح و معنویت", "❤️ خانواده و محبت", "🧠 علم و حکمت",
    "🤝 مردم و جامعه", "❤️ خانواده و محبت", "🌿 اخلاق و رفتار", "🤝 مردم و جامعه",
    "🕊️ روح و معنویت", "👑 اهل‌بیت و ولایت", "🧠 علم و حکمت", "🕌 ایمان و عبادت",
    "👑 اهل‌بیت و ولایت", "🕌 ایمان و عبادت", "🕌 ایمان و عبادت", "👑 اهل‌بیت و ولایت",
    "🌿 اخلاق و رفتار", "🌿 اخلاق و رفتار", "🤝 مردم و جامعه", "🧠 علم و حکمت",
    "⚖️ عدالت و حقوق", "🧠 علم و حکمت", "🕌 ایمان و عبادت", "🧠 علم و حکمت",
    "🤝 مردم و جامعه", "🌿 اخلاق و رفتار", "👑 اهل‌بیت و ولایت", "👑 اهل‌بیت و ولایت",
]


def main():
    init_db()
    with open("hadiths_batch5_new.json", encoding="utf-8") as f:
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
