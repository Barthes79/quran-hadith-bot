# -*- coding: utf-8 -*-
"""
اسکریپت ریست کردن «پیشرفت قابلیت‌ها» (شمارش صلوات کامل) برای همه‌ی کاربران.

این اسکریپت:
  - pigeon_salavat_count رو برای همه‌ی کاربران به ۰ تنظیم می‌کنه.
  - هیچ داده‌ی دیگه‌ای (کیف‌پول، مقام کبوتر، یخچال، ...) رو تغییر نمی‌ده.

توجه: این عملیات غیرقابل‌بازگشت است مگر اینکه از دیتابیس بکاپ گرفته باشید.
"""

import sqlite3
import sys
import os

from database import get_connection

def confirm(prompt):
    """درخواست تأیید از کاربر."""
    response = input(prompt + " (بله/خیر): ").strip()
    return response.lower() in ("بله", "yes", "y", "ب")

def reset_feature_progress():
    """ریست کردن شمارش صلوات کامل برای همه."""
    print("⚠️  هشدار: این عملیات همه‌ی شمارش‌های صلوات کامل (pigeon_salavat_count) را برای همه‌ی کاربران به ۰ تنظیم می‌کند.")
    print("این کار قابل‌بازگشت نیست مگر اینکه از دیتابیس بکاپ گرفته باشید.")
    
    if not confirm("آیا مطمئن هستید که می‌خواهید ادامه دهید؟"):
        print("❌ عملیات لغو شد.")
        return
    
    if not confirm("تأیید نهایی: آیا واقعاً می‌خواهید همه‌ی کاربران ریست شوند؟"):
        print("❌ عملیات لغو شد.")
        return

    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # شمارش تعداد کاربران قبل از ریست
        cur.execute("SELECT COUNT(*) FROM gamification_profile")
        count_before = cur.fetchone()[0]
        print(f"📊 تعداد کل کاربران در دیتابیس: {count_before}")
        
        if count_before == 0:
            print("⚠️  هیچ کاربری در دیتابیس وجود ندارد.")
            conn.close()
            return
        
        # ریست کردن شمارش به ۰
        cur.execute("UPDATE gamification_profile SET pigeon_salavat_count = 0")
        rows_updated = cur.rowcount
        
        # commit کردن تغییرات
        conn.commit()
        conn.close()
        
        print(f"✅ عملیات با موفقیت انجام شد. {rows_updated} رکورد به‌روزرسانی شد.")
        print("🔓 همه‌ی کاربران از سطح ۰ (شمارش ۰) شروع می‌کنند.")
        
    except Exception as e:
        print(f"❌ خطا در هنگام اجرای عملیات: {e}")
        sys.exit(1)

if __name__ == "__main__":
    reset_feature_progress()