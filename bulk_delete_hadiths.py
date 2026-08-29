"""
این اسکریپت یک سری حدیث را یک‌جا از دیتابیس حذف می‌کند.
حذف می‌تواند بر اساس شناسه (id)، منبع، راوی یا موضوع باشد.

⚠️ به‌صورت پیش‌فرض فقط حالت "پیش‌نمایش" (dry-run) اجرا می‌شود و چیزی حذف نمی‌شود.
برای حذف واقعی حتماً --yes را اضافه کنید.

نمونه استفاده (روی Railway از تب Console، یا لوکال):

    # پیش‌نمایش: چه چیزی حذف می‌شود (چیزی حذف نمی‌شود)
    python bulk_delete_hadiths.py --ids 12,13,14

    # حذف واقعی چند شناسه مشخص
    python bulk_delete_hadiths.py --ids 12,13,14 --yes

    # حذف همه احادیث یک منبع خاص
    python bulk_delete_hadiths.py --source "نهج البلاغه" --yes

    # حذف همه احادیث یک راوی خاص در یک باب خاص
    python bulk_delete_hadiths.py --narrator "امام صادق" --chapter "باب زکات" --yes

    # حذف بر اساس فایل JSON حاوی لیست شناسه‌ها، مثلاً: [12, 13, 14]
    python bulk_delete_hadiths.py --file ids_to_delete.json --yes
"""
import argparse
import json
from database import init_db, get_connection, delete_hadith


def find_target_ids(source=None, narrator=None, chapter=None, topic=None):
    conn = get_connection()
    query = "SELECT DISTINCT h.id FROM hadiths h"
    conditions = []
    params = []

    if topic:
        query += " JOIN hadith_topics t ON h.id = t.hadith_id"
        conditions.append("t.topic_name = ?")
        params.append(topic)
    if source:
        conditions.append("h.source_book LIKE ?")
        params.append(f"%{source}%")
    if narrator:
        conditions.append("h.narrator LIKE ?")
        params.append(f"%{narrator}%")
    if chapter:
        conditions.append("h.chapter LIKE ?")
        params.append(f"%{chapter}%")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [r["id"] for r in rows]


def main():
    parser = argparse.ArgumentParser(description="حذف دسته‌جمعی احادیث")
    parser.add_argument("--ids", help="شناسه‌ها با کاما جدا شده، مثلاً 12,13,14")
    parser.add_argument("--file", help="مسیر فایل JSON حاوی لیست شناسه‌ها")
    parser.add_argument("--source", help="حذف همه احادیث این منبع")
    parser.add_argument("--narrator", help="حذف همه احادیث این راوی")
    parser.add_argument("--chapter", help="حذف همه احادیث این باب")
    parser.add_argument("--topic", help="حذف همه احادیث این موضوع")
    parser.add_argument("--yes", action="store_true", help="حذف واقعی انجام شود (بدون این فلگ فقط پیش‌نمایش است)")
    args = parser.parse_args()

    init_db()

    ids = set()

    if args.ids:
        ids.update(int(x.strip()) for x in args.ids.split(",") if x.strip())

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            ids.update(int(x) for x in json.load(f))

    if args.source or args.narrator or args.chapter or args.topic:
        ids.update(find_target_ids(
            source=args.source,
            narrator=args.narrator,
            chapter=args.chapter,
            topic=args.topic,
        ))

    if not ids:
        print("هیچ فیلتری داده نشده یا هیچ حدیثی پیدا نشد. از --ids یا --source یا --narrator یا --chapter یا --topic یا --file استفاده کنید.")
        return

    conn = get_connection()
    rows = []
    for hid in sorted(ids):
        row = conn.execute("SELECT * FROM hadiths WHERE id = ?", (hid,)).fetchone()
        if row:
            rows.append(row)
    conn.close()

    if not rows:
        print("هیچ حدیثی با این شناسه‌ها پیدا نشد.")
        return

    print(f"تعداد {len(rows)} حدیث برای حذف پیدا شد:\n")
    for r in rows:
        preview = (r["translation_text"] or "")[:50].replace("\n", " ")
        print(f"  #{r['id']} | {r['source_book'] or '-'} | {preview}...")

    if not args.yes:
        print("\n⚠️ این فقط پیش‌نمایش بود، چیزی حذف نشد.")
        print("برای حذف واقعی همین دستور را با --yes دوباره اجرا کنید.")
        return

    for r in rows:
        delete_hadith(r["id"])

    print(f"\n✅ {len(rows)} حدیث با موفقیت حذف شد.")


if __name__ == "__main__":
    main()
