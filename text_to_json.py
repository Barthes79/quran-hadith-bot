"""
تبدیل یک فایل متنی ساده (که نوشتنش خیلی راحت‌تر از JSON است) به فایل JSON
مناسب برای اسکریپت‌های bulk_add_*.py

چرا این اسکریپت؟
چون نوشتن دستی JSON برای صدها خطبه/نامه/حکمت/دعا/حدیث خیلی وقت‌گیر و پر خطاست
(باید مراقب کوتیشن، کاما، براکت باشید). این‌جا فقط کافیست هر مورد را با همان
برچسب‌های ساده‌ای که در دستورهای /addhadith، /addnahj، /addmafatih استفاده
می‌کنید بنویسید و موردها را با یک خط شامل فقط ---- از هم جدا کنید.

نحوه اجرا:
    python text_to_json.py nahj    nahj_input.txt    nahj_seed_batch.json
    python text_to_json.py mafatih mafatih_input.txt mafatih_seed_batch.json
    python text_to_json.py hadith  hadith_input.txt  hadiths_seed_batch.json

بعد از تولید فایل JSON، طبق معمول اجرا کنید:
    python bulk_add_nahj.py nahj_seed_batch.json
    python bulk_add_mafatih.py mafatih_seed_batch.json
    python bulk_add_hadiths.py hadiths_seed_batch.json

------------------------------------------------------------------
فرمت فایل ورودی (input.txt) برای هر نوع:

نوع nahj (خطبه/نامه/حکمت):
    دسته: خطبه
    شماره: 1
    عنوان: خطبه‌ای در آغاز خلافت
    عربی: ...متن عربی...
    ترجمه: ...ترجمه فارسی...
    شرح: ...(اختیاری)...
    ----
    دسته: حکمت
    شماره: 147
    عربی: ...
    ترجمه: ...
    ----
    (و همین‌طور ادامه بدهید...)

نوع mafatih (ادعیه/زیارات/اعمال):
    دسته: زیارت
    عنوان: زیارت عاشورا
    عربی: ...
    ترجمه: ...(اختیاری)...
    توضیح: ...(اختیاری)...
    ----
    دسته: روزانه
    عنوان: دعای صباح
    عربی: ...
    ----

نوع hadith:
    عربی: ...
    ترجمه: ...
    شرح: ...(اختیاری)...
    راوی: امام علی (ع)
    منبع: غررالحکم
    باب: باب الصبر
    شماره: 1
    موضوعات: صبر، امید
    ----
    (مورد بعدی...)

نکته‌ها:
- خط جداکننده باید فقط شامل چند خط تیره پشت‌سرهم باشد (مثلاً ---- یا -----).
- ترتیب فیلدها مهم نیست؛ فقط برچسب («دسته:»، «عربی:» و ...) باید دقیق باشد.
- برای دسته‌ها این مقادیر مجاز است:
    nahj    -> خطبه / نامه / حکمت
    mafatih -> روزانه / زیارت / هفتگی / ماهانه / مناجات / خاص
------------------------------------------------------------------
"""
import sys
import re
import json

NAHJ_CATEGORY_MAP = {"خطبه": "khutbah", "نامه": "letter", "حکمت": "hekmat"}
MAFATIH_CATEGORY_MAP = {
    "روزانه": "daily", "زیارت": "ziyarat", "هفتگی": "weekly",
    "ماهانه": "monthly", "مناجات": "munajat", "خاص": "special",
}

FIELD_LABELS = {
    "nahj": ["دسته", "شماره", "عنوان", "عربی", "ترجمه", "شرح"],
    "mafatih": ["دسته", "عنوان", "عربی", "ترجمه", "توضیح"],
    "hadith": ["عربی", "ترجمه", "شرح", "راوی", "منبع", "باب", "شماره", "موضوعات"],
}


def parse_fields(chunk: str, labels: list) -> dict:
    pattern = r"(?=(?:" + "|".join(labels) + r")\s*:)"
    parts = re.split(pattern, chunk.strip())
    fields = {}
    for part in parts:
        part = part.strip()
        if not part or ":" not in part:
            continue
        key, value = part.split(":", 1)
        key = key.strip()
        if key in labels:
            fields[key] = value.strip()
    return fields


def split_entries(text: str) -> list:
    # هر خط شامل فقط سه یا چند خط‌تیره، جداکننده‌ی موردهاست
    entries = re.split(r"\n\s*-{3,}\s*\n", text.strip())
    return [e for e in entries if e.strip()]


def convert_nahj(entries):
    items = []
    for chunk in entries:
        f = parse_fields(chunk, FIELD_LABELS["nahj"])
        category_fa = f.get("دسته", "").strip()
        category = NAHJ_CATEGORY_MAP.get(category_fa)
        if not category:
            print(f"⚠️ رد شد (دسته نامعتبر «{category_fa}»): {chunk[:60]}...")
            continue
        try:
            number = int(f.get("شماره", ""))
        except ValueError:
            print(f"⚠️ رد شد (شماره نامعتبر): {chunk[:60]}...")
            continue
        items.append({
            "category": category,
            "number": number,
            "title": f.get("عنوان") or "",
            "arabic": f.get("عربی", ""),
            "translation": f.get("ترجمه", ""),
            "tafsir": f.get("شرح", ""),
        })
    return items


def convert_mafatih(entries):
    items = []
    for chunk in entries:
        f = parse_fields(chunk, FIELD_LABELS["mafatih"])
        category_fa = f.get("دسته", "").strip()
        category = MAFATIH_CATEGORY_MAP.get(category_fa)
        if not category:
            print(f"⚠️ رد شد (دسته نامعتبر «{category_fa}»): {chunk[:60]}...")
            continue
        items.append({
            "category": category,
            "title": f.get("عنوان", ""),
            "arabic": f.get("عربی", ""),
            "translation": f.get("ترجمه", ""),
            "tafsir": f.get("توضیح", ""),
        })
    return items


def convert_hadith(entries):
    items = []
    for chunk in entries:
        f = parse_fields(chunk, FIELD_LABELS["hadith"])
        topics_raw = f.get("موضوعات", "")
        topics = [t.strip() for t in topics_raw.split("،") if t.strip()] or \
                 [t.strip() for t in topics_raw.split(",") if t.strip()]
        items.append({
            "arabic": f.get("عربی", ""),
            "translation": f.get("ترجمه", ""),
            "tafsir": f.get("شرح", ""),
            "narrator": f.get("راوی", ""),
            "source": f.get("منبع", ""),
            "chapter": f.get("باب", ""),
            "number": f.get("شماره", ""),
            "topics": topics,
        })
    return items


CONVERTERS = {"nahj": convert_nahj, "mafatih": convert_mafatih, "hadith": convert_hadith}


def main():
    if len(sys.argv) < 4 or sys.argv[1] not in CONVERTERS:
        print("استفاده: python text_to_json.py <nahj|mafatih|hadith> <input.txt> <output.json>")
        sys.exit(1)

    kind, input_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]

    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()

    entries = split_entries(text)
    items = CONVERTERS[kind](entries)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(items)} مورد از {len(entries)} بخشِ پیدا‌شده تبدیل و در «{output_path}» ذخیره شد.")
    print(f"حالا اجرا کنید:  python bulk_add_{'hadiths' if kind == 'hadith' else kind}.py {output_path}")


if __name__ == "__main__":
    main()
