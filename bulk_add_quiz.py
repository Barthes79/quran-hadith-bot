"""
مشابه bulk_add_hadiths.py، این اسکریپت یک فایل JSON از سوالات مسابقه را
می‌خواند و همه را یک‌جا به دیتابیس اضافه می‌کند.

نحوه اجرا (از تب Console در Railway یا لوکال):
    python bulk_add_quiz.py quiz_seed_batch.json
"""
import sys
import json
from database import init_db, add_quiz_question


def main():
    if len(sys.argv) < 2:
        print("استفاده: python bulk_add_quiz.py <فایل.json>")
        sys.exit(1)

    json_path = sys.argv[1]
    init_db()

    with open(json_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    added = 0
    for q in questions:
        try:
            qid = add_quiz_question(
                q["question"], q["a"], q["b"], q["c"], q["d"], q["correct"]
            )
            print(f"✅ ثبت شد (شناسه {qid}): {q['question'][:40]}...")
            added += 1
        except KeyError as e:
            print(f"⚠️ فیلد ناقص در سوال، رد شد: {e}")

    print(f"\nنتیجه نهایی: {added} سوال جدید اضافه شد.")


if __name__ == "__main__":
    main()
