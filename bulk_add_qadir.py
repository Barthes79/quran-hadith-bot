# verify_ghadir.py
import database as db

def verify():
    item = db.get_mafatih_by_slug("ghadir_day")
    if item:
        print(f"✅ عید غدیر پیدا شد!")
        print(f"   ID: {item['id']}")
        print(f"   Title: {item['title']}")
        print(f"   Category: {item['category']}")
        print(f"   Slug: {item['slug']}")
    else:
        print("❌ عید غدیر پیدا نشد!")
        
        # لیست همه آیتم‌ها
        print("\nلیست همه آیتم‌ها:")
        conn = db.get_connection()
        rows = conn.execute("SELECT id, slug, title FROM mafatih").fetchall()
        for row in rows:
            print(f"   ID: {row['id']}, Slug: {row['slug']}, Title: {row['title']}")
        conn.close()

if __name__ == "__main__":
    verify()