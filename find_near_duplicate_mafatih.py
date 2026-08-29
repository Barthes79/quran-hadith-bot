"""
اسکریپت تشخیصی: ردیف‌های «نزدیک به تکراری» در جدول mafatih را بر اساس
شباهتِ متن عربی (نه فقط عنوان) پیدا می‌کند. این برای مواردی است که عنوان
دو ثبت فرق دارد (مثلاً «دعای کمیل» در برابر «دعای کمیل (همراه با ترجمه و
صوت)») ولی محتوایشان همان دعا/زیارت است.

فقط نمایش می‌دهد؛ چیزی حذف نمی‌کند. برای هر جفتِ مشابه، مشخص می‌کند کدام
slug (اگر داشته باشد) در منو استفاده می‌شود تا معلوم شود کدام یک ایمن
برای حذف است.

نحوه اجرا:
    python find_near_duplicate_mafatih.py
"""
import difflib
from database import get_connection
from text_utils import normalize_for_search

SIMILARITY_THRESHOLD = 0.85  # بالای این عدد را «به‌احتمال زیاد تکراری» در نظر می‌گیریم


def used_in_menu(slug_or_none) -> bool:
    """بررسی می‌کند آیا این slug در فایل mafatih.py به‌عنوان callback_data یک
    دکمه‌ی منو استفاده شده یا خیر (یعنی حذفش یک دکمه از منو را خراب می‌کند)."""
    if not slug_or_none:
        return False
    try:
        with open("handlers/mafatih.py", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        try:
            with open("mafatih.py", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            return None  # نامشخص؛ فایل پیدا نشد
    return f'mafitem_{slug_or_none}"' in content


def main():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM mafatih ORDER BY id").fetchall()
    conn.close()

    normalized = [normalize_for_search(r["arabic_text"] or "") for r in rows]

    # برای کارایی، فقط ردیف‌هایی که طول متنشان نزدیک به هم است را با هم مقایسه کن
    n = len(rows)
    found_any = False
    checked_pairs = set()

    for i in range(n):
        len_i = len(normalized[i])
        if len_i < 30:
            continue  # متن‌های خیلی کوتاه را رد کن (مقایسه‌شان بی‌معنی است)
        for j in range(i + 1, n):
            len_j = len(normalized[j])
            if len_j < 30:
                continue
            # اگر طول دو متن خیلی با هم فرق دارد، قطعاً محتوای متفاوتی هستند
            if abs(len_i - len_j) / max(len_i, len_j) > 0.3:
                continue

            ratio = difflib.SequenceMatcher(None, normalized[i], normalized[j]).ratio()
            if ratio >= SIMILARITY_THRESHOLD:
                found_any = True
                r1, r2 = rows[i], rows[j]
                print(f"🔶 شباهت {ratio:.0%} بین:")
                for r in (r1, r2):
                    in_menu = used_in_menu(r["slug"])
                    menu_note = (
                        "در منو استفاده می‌شود ⚠️ حذف نشود" if in_menu
                        else ("در هیچ دکمه‌ای در منو استفاده نمی‌شود ✅ حذفش ایمن است" if in_menu is False
                              else "وضعیت استفاده در منو نامشخص")
                    )
                    print(f"   id={r['id']} | عنوان={r['title']!r} | دسته={r['category']} | "
                          f"slug={r['slug']!r} | صوت={'دارد' if r['audio_file_id'] else 'ندارد'} | {menu_note}")
                print()

    if not found_any:
        print("هیچ محتوای نزدیک‌به‌تکراری‌ای پیدا نشد. ✅")


if __name__ == "__main__":
    main()
