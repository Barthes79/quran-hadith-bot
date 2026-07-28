from database import get_mafatih_by_slug

item = get_mafatih_by_slug("kumayl")
if not item:
    print("چیزی با slug='kumayl' پیدا نشد!")
else:
    print(f"id: {item['id']}")
    print(f"عنوان: {item['title']}")
    print(f"audio_file_id: {item['audio_file_id']!r}")
