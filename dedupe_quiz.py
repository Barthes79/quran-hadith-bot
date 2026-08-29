"""
سوالات تکراری کوییز را پیدا می‌کند (بر اساس متن سوال) و فقط یک نسخه از هرکدام
را نگه می‌دارد. در بین نسخه‌های تکراری، نسخه‌ای که دسته‌بندی‌اش «general» نیست
(یعنی درست‌تر دسته‌بندی شده) نگه داشته می‌شود.

نحوه اجرا:
    python dedupe_quiz.py            # فقط نمایش می‌دهد چه چیزی حذف خواهد شد (dry-run)
    python dedupe_quiz.py --apply    # واقعاً حذف می‌کند
"""
import sys
from collections import defaultdict
from database import get_connection


def main():
    apply_changes = "--apply" in sys.argv

    conn = get_connection()
    rows = conn.execute("SELECT * FROM quiz_questions ORDER BY id").fetchall()

    groups = defaultdict(list)
    for r in rows:
        key = r["question_text"].strip()
        groups[key].append(r)

    to_delete = []
    for question_text, group in groups.items():
        if len(group) <= 1:
            continue
        # ترجیح: نگه‌داشتن نسخه‌ای که دسته‌اش "general" نیست؛ در غیر این صورت کوچک‌ترین id
        non_general = [r for r in group if r["category"] != "general"]
        keeper = non_general[0] if non_general else group[0]
        for r in group:
            if r["id"] != keeper["id"]:
                to_delete.append((r, keeper))

    if not to_delete:
        print("✅ هیچ سوال تکراری‌ای پیدا نشد.")
        return

    print(f"🔍 {len(to_delete)} سوال تکراری پیدا شد:\n")
    for dup, keeper in to_delete:
        print(f"  حذف [{dup['id']}] ({dup['category']}/{dup['difficulty']}) — "
              f"نگه‌داشته می‌شود: [{keeper['id']}] ({keeper['category']}/{keeper['difficulty']})")
        print(f"    {dup['question_text'][:60]}")

    if not apply_changes:
        print(f"\n⚠️ این فقط پیش‌نمایش بود. برای حذف واقعی اجرا کن:\n    python dedupe_quiz.py --apply")
        return

    ids_to_delete = [dup["id"] for dup, _ in to_delete]
    conn.executemany("DELETE FROM quiz_questions WHERE id = ?", [(i,) for i in ids_to_delete])
    conn.commit()
    print(f"\n✅ {len(ids_to_delete)} سوال تکراری حذف شد.")

    remaining = conn.execute("SELECT COUNT(*) c FROM quiz_questions").fetchone()["c"]
    print(f"📊 تعداد سوالات باقی‌مانده: {remaining}")


if __name__ == "__main__":
    main()
