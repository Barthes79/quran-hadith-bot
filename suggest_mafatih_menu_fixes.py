"""
برای هر دکمه‌ی خراب در منوی مفاتیح (شناسه‌ای که به هیچ ردیفی در دیتابیس
وصل نیست)، سعی می‌کند با جستجوی کلیدواژه‌های متن دکمه در عنوان دعاهای
دیتابیس، محتوای احتمالاً مرتبط را پیدا و پیشنهاد کند.

نحوه اجرا:
    python suggest_mafatih_menu_fixes.py
"""
import re
import sys

sys.path.insert(0, ".")
from database import get_connection, get_mafatih_item_flexible
from handlers.mafatih import SUB_KEYBOARDS
from text_utils import normalize_for_search

# ایموجی و کاراکترهای غیرحرفی را از متن دکمه حذف می‌کند تا فقط کلمات بمانند
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F0FF\U00002B00-\U00002BFF]+"
)


def clean_button_text(text: str) -> str:
    text = _EMOJI_RE.sub("", text)
    return normalize_for_search(text)


def find_broken_buttons():
    broken = []
    for sub_key, sub_fn in SUB_KEYBOARDS.items():
        try:
            keyboard = sub_fn()
        except Exception:
            continue
        for row in keyboard.inline_keyboard:
            for btn in row:
                if not btn.callback_data or not btn.callback_data.startswith("mafitem_"):
                    continue
                identifier = btn.callback_data[len("mafitem_"):]
                if not get_mafatih_item_flexible(identifier):
                    broken.append((sub_key, btn.text, identifier))
    return broken


def main():
    broken = find_broken_buttons()
    if not broken:
        print("دکمه‌ی خرابی پیدا نشد. ✅")
        return

    conn = get_connection()
    all_rows = conn.execute("SELECT id, title, category, slug FROM mafatih").fetchall()
    conn.close()

    print(f"{len(broken)} دکمه‌ی خراب — برای هرکدام نزدیک‌ترین محتوا در دیتابیس:\n")

    for sub_key, btn_text, identifier in broken:
        cleaned = clean_button_text(btn_text)
        words = [w for w in cleaned.split() if len(w) > 1]

        candidates = []
        for row in all_rows:
            norm_title = normalize_for_search(row["title"] or "")
            score = sum(1 for w in words if w in norm_title)
            if score > 0:
                candidates.append((score, row))

        candidates.sort(key=lambda x: -x[0])

        print(f"🔴 زیردسته={sub_key} | دکمه={btn_text!r} | شناسه‌ی خراب={identifier!r}")
        if not candidates:
            print("     هیچ محتوای مشابهی در دیتابیس پیدا نشد (شاید اصلاً این دعا هنوز اضافه نشده).")
        else:
            for score, row in candidates[:3]:
                print(f"     احتمال id={row['id']} | slug={row['slug']!r} | عنوان={row['title']!r} | دسته={row['category']} (شباهت کلمه‌ای: {score})")
        print()


if __name__ == "__main__":
    main()
