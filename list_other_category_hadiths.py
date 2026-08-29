"""
لیست همه‌ی احادیثی که الان دسته‌شان «💎 موضوعات دیگر» است
(یعنی از منوی احادیث حذف شده‌اند) به همراه موضوعات ثبت‌شده‌شان.

نحوه اجرا (روی Railway از تب Console):
    python list_other_category_hadiths.py
"""
from database import init_db, get_connection


def main():
    init_db()
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, narrator, source_book, translation_text FROM hadiths "
        "WHERE category = '💎 موضوعات دیگر' ORDER BY id"
    ).fetchall()

    print(f"تعداد کل: {len(rows)}\n" + "-" * 60)
    for r in rows:
        topics = conn.execute(
            "SELECT topic_name FROM hadith_topics WHERE hadith_id = ?",
            (r["id"],)
        ).fetchall()
        topic_str = ", ".join(t["topic_name"] for t in topics) or "—"
        preview = (r["translation_text"] or "")[:45].replace("\n", " ")
        print(f"id={r['id']:<5} narrator={r['narrator']:<20} topics=[{topic_str}] | {preview}...")

    conn.close()


if __name__ == "__main__":
    main()
