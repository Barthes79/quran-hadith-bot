"""
اسکریپت کمکی برای پیدا کردن custom_emoji_id
--------------------------------------------
۱) اول یه پیام حاوی ایموجی سفارشی (که می‌خوای آی‌دیش رو داشته باشی) رو
   به ربات خودت فوروارد/ارسال کن.
۲) این اسکریپت رو اجرا کن:
      python get_custom_emoji_id.py
۳) توکن ربات رو وقتی پرسید وارد کن (یا در متغیر محیطی BOT_TOKEN بذار).
۴) خروجی، متن پیام‌ها + هر custom_emoji_id که پیدا بشه رو نشون می‌ده.

نکته: اگه ربات از webhook استفاده می‌کنه، باید موقتاً webhook رو حذف کنی
(deleteWebhook) تا getUpdates کار کنه، یا از همون آپدیت‌های ذخیره‌شده در
دیتابیس/لاگ ربات استفاده کنی.
"""

import os
import requests

TOKEN = os.environ.get("BOT_TOKEN") or input("توکن ربات را وارد کنید: ").strip()

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"


def main():
    resp = requests.get(f"{BASE_URL}/getUpdates", params={"limit": 50})
    data = resp.json()

    if not data.get("ok"):
        print("خطا در دریافت آپدیت‌ها:", data)
        return

    updates = data["result"]
    if not updates:
        print("هیچ آپدیتی پیدا نشد. یه پیام جدید به ربات بفرست و دوباره امتحان کن.")
        print("اگه ربات webhook فعال داره، اول باید موقتاً حذفش کنی:")
        print(f"  {BASE_URL}/deleteWebhook")
        return

    found_any = False
    for upd in updates:
        msg = upd.get("message") or upd.get("channel_post")
        if not msg:
            continue

        text = msg.get("text", "")
        entities = msg.get("entities", [])

        custom_emojis = [e for e in entities if e.get("type") == "custom_emoji"]
        if not custom_emojis:
            continue

        found_any = True
        print("─" * 40)
        print("متن پیام:", text)
        for e in custom_emojis:
            emoji_slice = text[e["offset"]: e["offset"] + e["length"]]
            print(f"  ایموجی: {emoji_slice}   ->   custom_emoji_id: {e['custom_emoji_id']}")

    if not found_any:
        print("هیچ custom_emoji ای توی پیام‌های اخیر پیدا نشد.")
        print("مطمئن شو پیامی که فرستادی واقعاً حاوی یه ایموجی سفارشی/پرمیوم بوده،")
        print("نه یه ایموجی یونیکد معمولی.")


if __name__ == "__main__":
    main()
