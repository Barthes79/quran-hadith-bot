"""
پیدا کردن و حذف ردیف‌های تکراری در جدول mafatih.

چرا لازم است:
ستون slug روی مفاتیح یکتا (UNIQUE) است، اما چون nullable است و SQLite چند
مقدار NULL را «متفاوت» در نظر می‌گیرد، اگر یک دعا بدون slug دوبار اضافه شود
(مثلاً یک‌بار از یک اسکریپت عمومی و یک‌بار از یک اسکریپت اختصاصی)، هیچ‌چیز
جلویش را نمی‌گیرد و همان دعا با دو id مختلف در نتایج جستجو تکراری نشان
داده می‌شود.

نحوه‌ی تشخیص تکراری:
دو ردیف را وقتی «تکراری» در نظر می‌گیریم که category یکسان باشد و عنوانشان
(بعد از نرمال‌سازی حروف عربی/فارسی) یکسان باشد.

از بین هر گروه تکراری، «بهترین» ردیف نگه داشته می‌شود: اولویت با ردیفی
است که audio_file_id و image_path و tafsir_text بیشتری دارد و متن
arabic_text/translation_text طولانی‌تری دارد؛ در تساوی، قدیمی‌ترین id
(اولین ثبت) نگه داشته می‌شود.

نحوه‌ی اجرا (روی Railway، از تب Console):
    python dedupe_mafatih.py            -> فقط نمایش می‌دهد چه چیزهایی تکراری‌اند (چیزی حذف نمی‌شود)
    python dedupe_mafatih.py --apply    -> واقعاً ردیف‌های تکراری اضافه را حذف می‌کند و ایندکس را می‌سازد
"""
import sys
from collections import defaultdict

from database import get_connection, init_db, rebuild_search_index
from text_utils import normalize_for_search


def _completeness_score(row) -> tuple:
    """امتیاز «کامل بودن» یک ردیف برای تصمیم اینکه کدام نسخه نگه داشته شود."""
    return (
        1 if row["audio_file_id"] else 0,
        1 if row["image_path"] else 0,
        1 if row["tafsir_text"] else 0,
        len(row["arabic_text"] or ""),
        len(row["translation_text"] or ""),
        -row["id"],  # در تساوی کامل، id کوچک‌تر (قدیمی‌تر) ترجیح داده می‌شود
    )


def find_duplicate_groups():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM mafatih ORDER BY id").fetchall()
    conn.close()

    groups = defaultdict(list)
    for row in rows:
        key = (row["category"], normalize_for_search(row["title"] or ""))
        groups[key].append(row)

    return {k: v for k, v in groups.items() if len(v) > 1}


def main():
    apply_changes = "--apply" in sys.argv

    init_db()
    dup_groups = find_duplicate_groups()

    if not dup_groups:
        print("هیچ ردیف تکراری‌ای در جدول mafatih پیدا نشد. ✅")
        return

    total_to_delete = 0
    ids_to_delete = []

    print(f"🔍 {len(dup_groups)} گروه تکراری پیدا شد:\n")
    for (category, norm_title), rows in dup_groups.items():
        keep = max(rows, key=_completeness_score)
        remove = [r for r in rows if r["id"] != keep["id"]]
        total_to_delete += len(remove)
        ids_to_delete.extend(r["id"] for r in remove)

        print(f"دسته: {category} | عنوان: {rows[0]['title']}")
        print(f"  ✅ نگه‌داشته می‌شود: id={keep['id']}")
        for r in remove:
            print(f"  ❌ حذف می‌شود:      id={r['id']}")
        print()

    print(f"جمع کل: {total_to_delete} ردیف تکراری برای حذف.\n")

    if not apply_changes:
        print("این فقط یک پیش‌نمایش بود؛ چیزی حذف نشد.")
        print("برای حذف واقعی، دوباره اجرا کنید: python dedupe_mafatih.py --apply")
        return

    conn = get_connection()
    placeholders = ",".join("?" for _ in ids_to_delete)
    conn.execute(f"DELETE FROM mafatih WHERE id IN ({placeholders})", ids_to_delete)
    conn.commit()
    conn.close()
    print(f"✅ {total_to_delete} ردیف تکراری حذف شد.")

    print("در حال بازسازی ایندکس جستجو...")
    rebuild_search_index()
    print("✅ ایندکس جستجو بازسازی شد.")


if __name__ == "__main__":
    main()
