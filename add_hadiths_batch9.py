"""
افزودن ۴۶ حدیث جدید (بچ ۹) و تنظیم مستقیم دسته‌بندی هرکدام،
بدون فراخوانی recategorize_all_hadiths.

⚠️ این اسکریپت را فقط یک‌بار اجرا کن؛ اگر بعداً نتیجه را چک نکردی و دوباره
اجرا کردی، این ۴۶ حدیث دوباره (تکراری) وارد پایگاه‌داده می‌شوند.

نحوه اجرا (روی Railway از تب Console، در همان پوشه‌ی پروژه):
    python add_hadiths_batch9.py
"""
import json
from database import init_db, add_hadith, update_hadith_category

CATEGORIES = [
    "🧠 علم و حکمت", "🌿 اخلاق و رفتار", "🤝 مردم و جامعه", "🕌 ایمان و عبادت",
    "🌱 دنیا و آخرت", "🕊️ روح و معنویت", "👑 اهل‌بیت و ولایت", "🕌 ایمان و عبادت",
    "🌿 اخلاق و رفتار", "🕊️ روح و معنویت", "🤝 مردم و جامعه", "👑 اهل‌بیت و ولایت",
    "👑 اهل‌بیت و ولایت", "🌿 اخلاق و رفتار", "👑 اهل‌بیت و ولایت", "👑 اهل‌بیت و ولایت",
    "👑 اهل‌بیت و ولایت", "👑 اهل‌بیت و ولایت", "🕌 ایمان و عبادت", "👑 اهل‌بیت و ولایت",
    "🕌 ایمان و عبادت", "🕌 ایمان و عبادت", "⚖️ عدالت و حقوق", "👑 اهل‌بیت و ولایت",
    "👑 اهل‌بیت و ولایت", "💰 مال و زندگی", "🕌 ایمان و عبادت", "🤝 مردم و جامعه",
    "🌿 اخلاق و رفتار", "🌱 دنیا و آخرت", "🌿 اخلاق و رفتار", "🌿 اخلاق و رفتار",
    "🕊️ روح و معنویت", "🕊️ روح و معنویت", "🌱 دنیا و آخرت", "👑 اهل‌بیت و ولایت",
    "⚖️ عدالت و حقوق", "🌿 اخلاق و رفتار", "👑 اهل‌بیت و ولایت", "👑 اهل‌بیت و ولایت",
    "👑 اهل‌بیت و ولایت", "🌿 اخلاق و رفتار", "🕌 ایمان و عبادت", "🕊️ روح و معنویت",
    "👑 اهل‌بیت و ولایت", "🕊️ روح و معنویت",
]


def main():
    init_db()
    with open("hadiths_batch9_new.json", encoding="utf-8") as f:
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
