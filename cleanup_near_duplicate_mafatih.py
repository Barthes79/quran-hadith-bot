"""
پاک‌سازی نهاییِ ردیف‌های نزدیک‌به‌تکراری در جدول mafatih، بر اساس شباهت
محتوای متن عربی (نه فقط عنوان دقیق).

قانون انتخاب «نسخه‌ی نگه‌داشته‌شده» در هر خوشه‌ی تکراری:
1. اگر یکی از نسخه‌ها slugـی دارد که در دکمه‌های منوی mafatih.py استفاده
   شده (یعنی کاربر واقعاً از طریق منو به آن می‌رسد)، همان نگه داشته می‌شود
   — چون حذفش یک دکمه‌ی منو را خراب می‌کند.
2. اگر هیچ‌کدام در منو استفاده نشده (یا بیش از یکی استفاده شده، که یعنی
   باید دستی بررسی شود)، بر اساس کامل‌بودن (صوت/عکس/شرح/طول متن) انتخاب
   می‌شود.
قبل از حذف هر نسخه، فیلدهای خالیِ نسخه‌ی نگه‌داشته‌شده (صوت/عکس/شرح/ترجمه)
از نسخه‌های حذفی پر می‌شود تا داده‌ای از دست نرود.

نحوه اجرا:
    python cleanup_near_duplicate_mafatih.py            -> فقط پیش‌نمایش
    python cleanup_near_duplicate_mafatih.py --apply     -> حذف واقعی + بازسازی ایندکس
"""
import difflib
import sys

from database import get_connection, init_db, rebuild_search_index
from text_utils import normalize_for_search

SIMILARITY_THRESHOLD = 0.85


def load_mafatih_source() -> str:
    for path in ("handlers/mafatih.py", "mafatih.py"):
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            continue
    print("⚠️ هشدار: فایل mafatih.py پیدا نشد؛ نمی‌توانم بررسی کنم کدام slug در منو استفاده می‌شود.")
    print("   این اسکریپت را از پوشه‌ی اصلی پروژه (کنار database.py) اجرا کنید.")
    sys.exit(1)


def find_clusters(rows):
    """گروه‌بندی ردیف‌ها به خوشه‌های محتوای مشابه با Union-Find."""
    normalized = [normalize_for_search(r["arabic_text"] or "") for r in rows]
    n = len(rows)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        len_i = len(normalized[i])
        if len_i < 30:
            continue
        for j in range(i + 1, n):
            len_j = len(normalized[j])
            if len_j < 30 or abs(len_i - len_j) / max(len_i, len_j) > 0.3:
                continue
            ratio = difflib.SequenceMatcher(None, normalized[i], normalized[j]).ratio()
            if ratio >= SIMILARITY_THRESHOLD:
                union(i, j)

    clusters = {}
    for idx in range(n):
        root = find(idx)
        clusters.setdefault(root, []).append(rows[idx])

    return [members for members in clusters.values() if len(members) > 1]


def _completeness_score(row) -> tuple:
    return (
        1 if row["audio_file_id"] else 0,
        1 if row["image_path"] else 0,
        1 if row["tafsir_text"] else 0,
        len(row["arabic_text"] or ""),
        len(row["translation_text"] or ""),
        -row["id"],
    )


def pick_keeper(cluster, source: str):
    used = [r for r in cluster if r["slug"] and f'mafitem_{r["slug"]}"' in source]
    if len(used) == 1:
        return used[0], "این نسخه در منو استفاده می‌شود"
    if len(used) > 1:
        # بیش از یکی در منو استفاده شده -> نمی‌توان خودکار تصمیم گرفت، نیاز به بررسی دستی
        return None, "بیش از یک نسخه در منو استفاده می‌شود؛ این خوشه رد شد، باید دستی بررسی شود"
    keeper = max(cluster, key=_completeness_score)
    return keeper, "هیچ‌کدام در منو استفاده نمی‌شوند؛ کامل‌ترین نسخه انتخاب شد"


def main():
    apply_changes = "--apply" in sys.argv
    source = load_mafatih_source()

    init_db()
    conn = get_connection()
    rows = conn.execute("SELECT * FROM mafatih ORDER BY id").fetchall()
    conn.close()

    clusters = find_clusters(rows)
    if not clusters:
        print("هیچ محتوای نزدیک‌به‌تکراری‌ای پیدا نشد. ✅")
        return

    total_to_delete = 0
    ids_to_delete = []
    merge_updates = []
    skipped = 0

    print(f"🔍 {len(clusters)} خوشه‌ی تکراری پیدا شد:\n")
    for cluster in clusters:
        keeper, reason = pick_keeper(cluster, source)
        print(f"عنوان: {cluster[0]['title']!r}  ({len(cluster)} نسخه)")
        if keeper is None:
            print(f"  ⏭️ رد شد: {reason}")
            for r in cluster:
                print(f"     id={r['id']} | slug={r['slug']!r}")
            print()
            skipped += 1
            continue

        remove = [r for r in cluster if r["id"] != keeper["id"]]
        total_to_delete += len(remove)
        ids_to_delete.extend(r["id"] for r in remove)

        merged = {}
        for field in ("audio_file_id", "image_path", "tafsir_text", "translation_text"):
            if not keeper[field]:
                for r in remove:
                    if r[field]:
                        merged[field] = r[field]
                        break
        if merged:
            merge_updates.append((keeper["id"], merged))

        print(f"  ✅ نگه‌داشته می‌شود: id={keeper['id']} ({reason})")
        for r in remove:
            print(f"  ❌ حذف می‌شود:      id={r['id']} | slug={r['slug']!r}")
        if merged:
            print(f"  🔀 فیلدهای منتقل‌شده قبل از حذف: {', '.join(merged.keys())}")
        print()

    print(f"جمع کل: {total_to_delete} ردیف برای حذف. ({skipped} خوشه رد شد و نیاز به بررسی دستی دارد)\n")

    if not apply_changes:
        print("این فقط پیش‌نمایش بود؛ چیزی حذف نشد.")
        print("برای حذف واقعی: python cleanup_near_duplicate_mafatih.py --apply")
        return

    if not ids_to_delete:
        print("چیزی برای حذف نبود.")
        return

    conn = get_connection()
    for keep_id, fields in merge_updates:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        params = list(fields.values()) + [keep_id]
        conn.execute(f"UPDATE mafatih SET {set_clause} WHERE id = ?", params)

    placeholders = ",".join("?" for _ in ids_to_delete)
    conn.execute(f"DELETE FROM mafatih WHERE id IN ({placeholders})", ids_to_delete)
    conn.commit()
    conn.close()
    print(f"✅ {total_to_delete} ردیف حذف شد.")

    print("در حال بازسازی ایندکس جستجو...")
    rebuild_search_index()
    print("✅ ایندکس جستجو بازسازی شد.")


if __name__ == "__main__":
    main()
