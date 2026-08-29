from database import get_connection

def clear_daily():
    conn = get_connection()
    cursor = conn.cursor()
    # پاک کردن تمام مواردی که در دسته daily هستند
    cursor.execute("DELETE FROM mafatih WHERE category = 'daily'")
    conn.commit()
    count = cursor.rowcount
    conn.close()
    print(f"✅ تعداد {count} مورد قدیمی پاک شد.")

if __name__ == "__main__":
    clear_daily()