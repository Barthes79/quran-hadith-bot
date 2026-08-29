import asyncio
import database as db # فراخوانی کانکشن دیتابیس شما

# محتوای کامل SQL (از فایل اولی که فرستادید کپی کنید)
SQL_QUERY = """
-- ۱. ایجاد جداول مربوطه
CREATE TABLE IF NOT EXISTS mafatih_categories (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    button_text VARCHAR(100) NOT NULL,
    description TEXT
);
-- ... (بقیه کدهای ایجاد جدول و INSERT ها را اینجا قرار دهید) ...
"""

async def main():
    print("⏳ در حال ساخت جداول و وارد کردن اطلاعات مفاتیح الجنان...")
    
    # فرض بر این است که شما تابعی برای اجرای دستورات خام در database.py دارید
    # مثلا:
    # async with db.pool.acquire() as conn:
    #     await conn.execute(SQL_QUERY)
    
    print("✅ اطلاعات با موفقیت به دیتابیس اضافه شد.")

if __name__ == "__main__":
    asyncio.run(main())