# check_city_codes.py
# این اسکریپت رو روی سروری که به prayer.aviny.com دسترسی داره اجرا کن
# (روی همون جایی که ربات ران میشه، چون در محیط من دسترسی به این دامنه بسته‌ست).
#
# هدف: چک کردن اینکه هر عدد کد شهر، واقعاً به کدوم شهر اشاره می‌کنه،
# تا مطمئن بشیم دیکشنری CITY_CODES توی prayer.py درست تنظیم شده یا نه.

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# دیکشنری فعلی توی prayer.py -- برای مقایسه
CURRENT_CITY_CODES = {
    "تهران": 1, "مشهد": 2, "اصفهان": 3, "شیراز": 4, "تبریز": 5,
    "کرج": 6, "قم": 7, "اهواز": 8, "کرمانشاه": 9, "رشت": 10,
    "یزد": 11, "کرمان": 12, "اراک": 13, "همدان": 14, "زنجان": 15,
    "ساری": 16, "گرگان": 17, "بوشهر": 18, "بیرجند": 19, "خرم‌آباد": 20,
    "ارومیه": 21, "شهرکرد": 22, "بندرعباس": 23, "زاهدان": 24, "سنندج": 25,
    "قزوین": 26, "سمنان": 27, "مازندران": 28, "گلستان": 29, "لرستان": 30,
}

def check(code_range=range(1, 60)):
    print(f"{'کد':<5}{'CityName واقعی از API':<25}")
    print("-" * 40)
    for code in code_range:
        try:
            r = requests.get(
                f"https://prayer.aviny.com/api/prayertimes/{code}",
                timeout=10, verify=False
            )
            r.raise_for_status()
            data = r.json()
            real_name = data.get("CityName", "؟")
            print(f"{code:<5}{real_name:<25}")
        except Exception as e:
            print(f"{code:<5}خطا: {e}")

def compare_with_current():
    """می‌گه کدوم شهرهای توی دیکشنری فعلی، اسمشون با اسم واقعی API فرق داره"""
    print("\n== مقایسه با CITY_CODES فعلی توی prayer.py ==\n")
    for name, code in CURRENT_CITY_CODES.items():
        try:
            r = requests.get(
                f"https://prayer.aviny.com/api/prayertimes/{code}",
                timeout=10, verify=False
            )
            r.raise_for_status()
            data = r.json()
            real_name = data.get("CityName", "؟")
            status = "✅ درست" if name in real_name or real_name in name else "❌ اشتباه"
            print(f"{status}  |  کد {code}: انتظار='{name}'  واقعی='{real_name}'")
        except Exception as e:
            print(f"⚠️  کد {code} ({name}): خطا در دریافت -> {e}")

if __name__ == "__main__":
    # ابتدا کدهای ۱ تا ۵۹ رو چک کن ببین چه شهرهایی واقعاً دارن
    check(range(1, 60))
    # بعد مقایسه کن ببین کدوم مورد توی دیکشنری فعلیت غلطه
    compare_with_current()
