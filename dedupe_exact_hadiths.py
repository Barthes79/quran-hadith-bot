"""
پیدا کردن و حذف حدیث‌هایی که متن عربی‌شان کاملاً یکسان است (یعنی به اشتباه
دوبار وارد پایگاه‌داده شده‌اند، مثلاً به‌خاطر اجرای دوباره‌ی یک اسکریپت
افزودن). برای هر گروه تکراری، فقط قدیمی‌ترین (کمترین id) نگه داشته می‌شود
و بقیه حذف می‌گردند. جدول hadith_topics هم برای ردیف‌های حذف‌شده پاک می‌شود.

نحوه اجرا (روی Railway از تب Console):
    python dedupe_exact_hadiths.py            # فقط نمایش گزارش (dry run)
    python dedupe_exact_hadiths.py --apply     # واقعاً حذف می‌کند
"""
import sys
import re
from collections import defaultdict
from database import init_db, get_connection


def normalize(text):
    if not text:
        return ""
    text = re.sub(r"[\u064B-\u065F\u0670\u06D6-\u06ED]", "", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ی").replace("ي", "ی").replace("ك", "ک")
    text = text.replace("ة", "ه")
    text = re.sub(r"[.,;:!؟،()«»\-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    apply_changes = "--apply" in sys.argv

    init_db()
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, arabic_text FROM hadiths ORDER BY id"
    ).fetchall()

    groups = defaultdict(list)
    for r in rows:
        key = normalize(r["arabic_text"])
        groups[key].append(r["id"])

    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}

    to_delete = []
    print(f"تعداد گروه‌های تکراری پیدا شده: {len(dup_groups)}\n" + "-" * 50)
    for key, ids in dup_groups.items():
        keep = min(ids)
        remove = [i for i in ids if i != keep]
        to_delete.extend(remove)
        print(f"نگه‌داشته می‌شود: {keep}  |  حذف می‌شود: {remove}  |  {key[:50]}")

    print(f"\nمجموع ردیف‌هایی که حذف خواهند شد: {len(to_delete)}")

    if not apply_changes:
        print("\n(این فقط گزارش بود، چیزی حذف نشد. برای حذف واقعی دوباره با --apply اجرا کن.)")
        return

    cur = conn.cursor()
    for hid in to_delete:
        cur.execute("DELETE FROM hadith_topics WHERE hadith_id = ?", (hid,))
        cur.execute("DELETE FROM hadiths WHERE id = ?", (hid,))
    conn.commit()
    print(f"\n✅ {len(to_delete)} حدیث تکراری حذف شد.")


if __name__ == "__main__":
    main()
