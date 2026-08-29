from database import get_connection

def add_image_column():
    conn = get_connection()
    try:
        conn.execute("ALTER TABLE mafatih ADD COLUMN image_url TEXT")
        conn.commit()
        print("✅ ستون image_url با موفقیت اضافه شد.")
    except Exception as e:
        print(f"⚠️ احتمالا ستون از قبل وجود دارد: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_image_column()