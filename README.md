# ربات تلگرامی قرآن و احادیث معصومین

ربات تلگرامی برای مطالعه‌ی آیات قرآن (متن عربی + ترجمه + تفسیر) و احادیث معصومین
(متن عربی + ترجمه + توضیح)، با قابلیت استفاده‌ی راحت در گروه‌های تلگرامی.

## ✨ قابلیت‌های فعلی (فاز ۱ و ۲)

- 📖 مرور تمام ۱۱۴ سوره قرآن، مشاهده‌ی هر آیه با متن عربی و ترجمه‌ی فارسی
- انتخاب مترجم (مکارم شیرازی / انصاریان / فولادوند)
- 📿 مرور احادیث بر اساس موضوع، حدیث تصادفی، جستجوی متنی
- ⭐ افزودن آیه/حدیث به علاقه‌مندی‌ها
- 🔍 **Inline Mode**: در هر چت یا گروهی بنویسید `@نام_ربات صبر` یا `@نام_ربات 2:255`
- 👥 قابلیت‌های گروهی: `/groupsettings` برای ادمین‌ها، فعال‌سازی پست خودکار روزانه
- پیام خوش‌آمدگویی خودکار وقتی ربات به گروه اضافه می‌شود
- دستور `/addhadith` برای ادمین‌ها جهت افزودن حدیث جدید به دیتابیس

## 🚧 در فازهای بعدی باید اضافه شود

- اتصال واقعی به دیتابیس تفسیر قرآن (فعلاً placeholder است)
- جمع‌آوری و وارد کردن حجم بیشتری از احادیث (فعلاً فقط ۳ حدیث نمونه برای تست دارد)
- حالت Quiz / مسابقه
- تبدیل متن به تصویر برای اشتراک‌گذاری زیبا

---

## ⚙️ راه‌اندازی محلی (تست روی سیستم خودتان)

### ۱. ساخت ربات در تلگرام
با [@BotFather](https://t.me/BotFather) یک ربات جدید بسازید و توکن آن را کپی کنید.

### ۲. نصب پیش‌نیازها
```bash
git clone <آدرس-ریپوی-شما>
cd quran-hadith-bot
python -m venv venv
source venv/bin/activate   # ویندوز: venv\Scripts\activate
pip install -r requirements.txt
```

### ۳. تنظیم متغیرهای محیطی
فایل `.env.example` را کپی کرده و به `.env` تغییر نام دهید، سپس توکن و آیدی عددی خودتان
(از [@userinfobot](https://t.me/userinfobot)) را وارد کنید:
```bash
cp .env.example .env
```

### ۴. (اختیاری) افزودن داده‌ی نمونه برای تست
```bash
python seed_sample_data.py
```

### ۵. اجرای ربات
```bash
python main.py
```

اگر همه‌چیز درست باشد، در تلگرام به ربات خود `/start` بزنید.

---

## ☁️ دیپلوی روی Railway یا Render (رایگان)

### Railway
1. پروژه را در گیت‌هاب پوش کنید.
2. در [railway.app](https://railway.app) یک پروژه جدید بسازید و ریپوی گیت‌هاب را متصل کنید.
3. در بخش **Variables** مقادیر `BOT_TOKEN` و `ADMIN_IDS` را وارد کنید.
4. Railway به‌صورت خودکار `requirements.txt` و `Procfile` را تشخیص داده و اجرا می‌کند.
   (چون این ربات با polling کار می‌کند نه webhook، نیازی به دامنه یا HTTPS نیست.)

### Render
1. یک سرویس جدید از نوع **Background Worker** بسازید.
2. ریپوی گیت‌هاب را متصل کنید.
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python main.py`
5. متغیرهای محیطی (`BOT_TOKEN`, `ADMIN_IDS`) را در بخش Environment اضافه کنید.

> ⚠️ نکته مهم: دیتابیس فعلی SQLite است و روی فایل محلی سرور ذخیره می‌شود.
> در پلن‌های رایگان Railway/Render معمولاً فایل‌سیستم پایدار (persistent) نیست
> و ممکن است بعد از هر ری‌استارت دیتابیس خالی شود. برای استفاده‌ی جدی و طولانی‌مدت،
> پیشنهاد می‌شود از یک دیتابیس PostgreSQL رایگان (مثلاً از همان Railway یا Supabase)
> استفاده کنید. در فاز بعدی می‌توانیم `database.py` را به PostgreSQL مهاجرت دهیم.

---

## 🇮🇷 دیپلوی روی VPS ایرانی

چون سرورهای داخل ایران معمولاً به `api.telegram.org` و APIهای خارجی (مثل alquran.cloud)
دسترسی مستقیم ندارند، دو نکته مهم است:

1. **نوع سرور**: حتماً از **VPS** استفاده کنید (نه هاست اشتراکی cPanel)، چون ربات باید
   به‌صورت یک پروسه‌ی دائمی و ۲۴ ساعته اجرا شود.
2. **پروکسی**: باید یک پروکسی (SOCKS5 یا HTTP) روی سرور یا در دسترس سرور داشته باشید و
   آدرس آن را در متغیر `PROXY_URL` در فایل `.env` قرار دهید. کد به‌صورت خودکار همه‌ی
   درخواست‌ها (هم ارتباط با تلگرام، هم API قرآن) را از این پروکسی رد می‌کند.

### مراحل نصب روی VPS (Ubuntu)

```bash
# اتصال به سرور
ssh user@your-server-ip

# نصب پیش‌نیازها
sudo apt update && sudo apt install python3 python3-venv python3-pip git -y

# دریافت کد از گیت‌هاب
git clone <آدرس-ریپوی-شما>
cd quran-hadith-bot

# ساخت محیط مجازی و نصب پکیج‌ها
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# تنظیم فایل env
cp .env.example .env
nano .env   # BOT_TOKEN, ADMIN_IDS و PROXY_URL را وارد کنید
```

### اجرای دائمی با systemd (توصیه می‌شود)

یک فایل سرویس بسازید تا ربات همیشه در پس‌زمینه اجرا بماند و در صورت ری‌استارت سرور
هم خودش بالا بیاید:

```bash
sudo nano /etc/systemd/system/quranbot.service
```

محتوای فایل:
```ini
[Unit]
Description=Quran and Hadith Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/quran-hadith-bot
ExecStart=/root/quran-hadith-bot/venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

سپس:
```bash
sudo systemctl daemon-reload
sudo systemctl enable quranbot
sudo systemctl start quranbot

# مشاهده لاگ‌ها برای بررسی وضعیت
sudo journalctl -u quranbot -f
```

با این روش دیتابیس SQLite هم روی خود سرور و به‌صورت پایدار باقی می‌ماند (بر خلاف
هاست‌های رایگان مثل Railway/Render که ممکن است ری‌استارت شود).

---

## 📚 افزودن حدیث جدید

فقط ادمین‌های تعریف‌شده در `ADMIN_IDS` می‌توانند با فرمت زیر حدیث اضافه کنند
(هر خط را در پیام دستور بعد از `/addhadith` وارد کنید):

```
/addhadith
عربی: الصَّبْرُ مِفْتَاحُ الْفَرَجِ
ترجمه: صبر، کلید گشایش (فرج) است.
راوی: امام علی (ع)
منبع: غررالحکم
باب: باب الصبر
شماره: 1
موضوعات: صبر، امید
```

## 📂 ساختار پروژه

```
quran-hadith-bot/
├── main.py                 # نقطه شروع و اتصال هندلرها
├── config.py                # تنظیمات و متغیرهای محیطی
├── database.py               # مدیریت دیتابیس SQLite
├── seed_sample_data.py       # افزودن داده‌ی نمونه برای تست
├── services/
│   └── quran_api.py           # اتصال به API قرآن (alquran.cloud) + کش
├── handlers/
│   ├── start.py                # منوی اصلی و تنظیمات کاربر
│   ├── quran.py                 # مرور سوره‌ها و آیات
│   ├── hadith.py                 # مرور احادیث، جستجو، افزودن حدیث
│   ├── inline.py                  # inline mode برای گروه‌ها
│   └── admin.py                    # تنظیمات گروه و پست خودکار روزانه
├── requirements.txt
├── Procfile
└── .env.example
```
