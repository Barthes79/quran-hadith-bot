"""
همه‌ی سوالات کوییز موجود در دیتابیس را نمایش می‌دهد و در یک فایل CSV ذخیره می‌کند
تا راحت‌تر بشه مرورشون کرد (مثلاً با اکسل یا گوگل شیت باز کرد).

نحوه اجرا (از تب Console در Railway یا لوکال، کنار database.py):
    python list_quiz.py
    python list_quiz.py quran          # فقط یک دسته خاص
    python list_quiz.py "" hard        # فقط یک سطح سختی خاص (دسته را خالی بگذار)
"""
import sys
import csv
from database import get_connection

CATEGORY_LABEL = {"quran": "قرآن", "nahj": "نهج‌البلاغه", "hadith": "احادیث", "general": "عمومی"}
DIFFICULTY_LABEL = {"easy": "آسان", "medium": "متوسط", "hard": "سخت"}


def main():
    category = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else None
    difficulty = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None

    conn = get_connection()
    query = "SELECT * FROM quiz_questions"
    conditions = []
    params = []
    if category:
        conditions.append("category = ?")
        params.append(category)
    if difficulty:
        conditions.append("difficulty = ?")
        params.append(difficulty)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY category, difficulty, id"

    rows = conn.execute(query, params).fetchall()

    print(f"تعداد کل سوالات: {len(rows)}\n" + "-" * 50)
    for r in rows:
        cat = CATEGORY_LABEL.get(r["category"], r["category"])
        diff = DIFFICULTY_LABEL.get(r["difficulty"], r["difficulty"])
        print(f"[{r['id']}] ({cat} | {diff}) {r['question_text']}")
        print(f"    الف) {r['option_a']}   ب) {r['option_b']}   ج) {r['option_c']}   د) {r['option_d']}   ✅ پاسخ: {r['correct_option']}")

    out_file = "quiz_export.csv"
    with open(out_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "question", "a", "b", "c", "d", "correct", "category", "difficulty"])
        for r in rows:
            writer.writerow([r["id"], r["question_text"], r["option_a"], r["option_b"],
                              r["option_c"], r["option_d"], r["correct_option"],
                              r["category"], r["difficulty"]])

    print(f"\n📄 خروجی CSV ذخیره شد: {out_file}")

    # آمار خلاصه بر اساس دسته و سطح سختی
    print("\n--- آمار ---")
    stats = {}
    for r in rows:
        key = (r["category"], r["difficulty"])
        stats[key] = stats.get(key, 0) + 1
    for (cat, diff), count in sorted(stats.items()):
        print(f"{CATEGORY_LABEL.get(cat, cat)} / {DIFFICULTY_LABEL.get(diff, diff)}: {count}")


if __name__ == "__main__":
    main()
