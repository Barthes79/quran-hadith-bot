"""
این اسکریپت لیست احادیث ثبت‌شده را همراه با شناسه (id) هرکدام نشان می‌دهد
تا قبل از حذف یا ادیت، بتوانید شناسه دقیق حدیث موردنظرتان را پیدا کنید.

نحوه اجرا (روی Railway از تب Console، یا لوکال):
    python list_hadiths.py
    python list_hadiths.py --source "الکافی"
    python list_hadiths.py --narrator "امام علی"
    python list_hadiths.py --topic "صبر"
    python list_hadiths.py --limit 100
"""
import argparse
from database import init_db, list_hadiths


def main():
    parser = argparse.ArgumentParser(description="نمایش لیست احادیث همراه با شناسه")
    parser.add_argument("--source", help="فیلتر بر اساس منبع (مثلاً الکافی)", default=None)
    parser.add_argument("--narrator", help="فیلتر بر اساس راوی/معصوم", default=None)
    parser.add_argument("--topic", help="فیلتر بر اساس موضوع", default=None)
    parser.add_argument("--limit", type=int, default=50, help="حداکثر تعداد نتایج")
    args = parser.parse_args()

    init_db()
    rows = list_hadiths(
        source_book=args.source,
        narrator=args.narrator,
        topic=args.topic,
        limit=args.limit,
    )

    if not rows:
        print("هیچ حدیثی با این فیلتر پیدا نشد.")
        return

    print(f"{'ID':<5} {'منبع':<15} {'باب':<15} {'شماره':<8} {'راوی':<15} ترجمه")
    print("-" * 100)
    for r in rows:
        preview = (r["translation_text"] or "")[:50].replace("\n", " ")
        print(
            f"{r['id']:<5} "
            f"{(r['source_book'] or '')[:14]:<15} "
            f"{(r['chapter'] or '')[:14]:<15} "
            f"{(r['hadith_number'] or '')[:7]:<8} "
            f"{(r['narrator'] or '')[:14]:<15} "
            f"{preview}..."
        )

    print(f"\nمجموع نمایش داده‌شده: {len(rows)} حدیث")
    print("برای حذف یا ادیت، شناسه (ID) هایی که می‌خواهید را از این لیست بردارید.")


if __name__ == "__main__":
    main()
