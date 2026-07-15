import database as db

ARABIC_TEXT = """📿 بدان که سجده شکر بعد از نمازها مستحب مؤکد است و دعاها و اذکار بسیاری در آن حال وارد شده است.

📿 از حضرت رضا (علیه السّلام) روایت شده است که اگر خواهی در سجده شکر بگو:
🔸 صد مرتبه:
شُکْراً شُکْراً

📿 و اگر خواهی بگو:
🔸 صد مرتبه:
عَفْواً عَفْواً

📿 و نیز از آن حضرت نقل شده است که کمترین ذکری که در این سجده گویند، آن است که بگوید:
🔸 سه مرتبه:
شُکْراً لِلّهِ"""

def main():
    db.init_db()
    item_id = db.add_mafatih_item(
        category="post_prayers",
        title="سجده شکر",
        arabic_text=ARABIC_TEXT,
        translation_text=None,
        tafsir_text=None,
        slug="sajda_shukr"
    )
    print(f"✅ سجده شکر با موفقیت ثبت شد. id={item_id}, slug=sajda_shukr")

if __name__ == "__main__":
    main()