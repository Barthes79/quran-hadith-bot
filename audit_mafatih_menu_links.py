"""
بررسی می‌کند که آیا هر دکمه‌ی «mafitem_<شناسه>» در منوی مفاتیح واقعاً به یک
ردیف موجود در دیتابیس اشاره می‌کند یا خیر. اگر دکمه‌ای به شناسه‌ای اشاره کند
که در دیتابیس پیدا نمی‌شود (مثل باگ «فرج» که به faraj_allah اشاره می‌کرد
درحالی‌که در دیتابیس فقط faraj بود)، اینجا نشان داده می‌شود.

نحوه اجرا (از پوشه‌ی اصلی پروژه، کنار database.py و پوشه‌ی handlers):
    python audit_mafatih_menu_links.py
"""
import sys

sys.path.insert(0, ".")
from database import get_mafatih_item_flexible
from handlers.mafatih import SUB_KEYBOARDS


def main():
    broken = []
    checked = 0

    for sub_key, sub_fn in SUB_KEYBOARDS.items():
        try:
            keyboard = sub_fn()
        except Exception as e:
            print(f"⚠️ خطا در ساخت کیبورد زیردسته‌ی {sub_key}: {e}")
            continue
        for row in keyboard.inline_keyboard:
            for btn in row:
                if not btn.callback_data or not btn.callback_data.startswith("mafitem_"):
                    continue
                identifier = btn.callback_data[len("mafitem_"):]
                checked += 1
                item = get_mafatih_item_flexible(identifier)
                if not item:
                    broken.append((sub_key, btn.text, identifier))

    print(f"{checked} دکمه بررسی شد.\n")
    if not broken:
        print("همه‌ی دکمه‌ها به محتوای موجود در دیتابیس وصل‌اند. ✅")
        return

    print(f"❌ {len(broken)} دکمه‌ی خراب پیدا شد (به هیچ ردیفی در دیتابیس وصل نیستند):\n")
    for sub_key, btn_text, identifier in broken:
        print(f"  زیردسته={sub_key} | متن دکمه={btn_text!r} | شناسه‌ی گم‌شده={identifier!r}")


if __name__ == "__main__":
    main()
