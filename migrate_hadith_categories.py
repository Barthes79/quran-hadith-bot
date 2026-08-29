#!/usr/bin/env python3
"""
اسکریپت مهاجرت برای اضافه کردن ستون category به جدول hadiths
و دسته‌بندی اولیه حدیث‌های موجود
"""

from database import add_category_column, recategorize_all_hadiths

def main():
    print("🔄 شروع مهاجرت دسته‌بندی احادیث...")
    
    # اضافه کردن ستون
    print("📌 اضافه کردن ستون category...")
    add_category_column()
    
    # دسته‌بندی مجدد
    print("📌 دسته‌بندی مجدد حدیث‌های موجود...")
    count = recategorize_all_hadiths()
    
    print(f"✅ مهاجرت کامل شد! {count} حدیث دسته‌بندی شدند.")

if __name__ == "__main__":
    main()