import database as db

for i in range(85, 92):
    row = db.get_mafatih_item(i)
    if row:
        print(i, dict(row))
    else:
        print(i, "=> این آیدی توی دیتابیس پیدا نشد!")
