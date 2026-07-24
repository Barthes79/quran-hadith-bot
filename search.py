# اضافه کردن importهای جدید در بالای فایل
from handlers.search import (
    search_command, search_callback, text_search_handler, search_page_callback
)
from search_engine import init_search

# در تابع main()، بعد از init_db()، موتور جستجو را مقداردهی کنید:
def main():
    init_db()
    init_search()  # <-- اضافه کنید
    
    # ... بقیه کدها ...

    # اضافه کردن هندلرهای جستجو (بعد از سایر هندلرها)
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CallbackQueryHandler(search_callback, pattern="^search_"))
    app.add_handler(CallbackQueryHandler(search_page_callback, pattern="^search_page_"))
    
    # هندلر متنی برای جستجو (در گروه‌ها)
    # این هندلر باید قبل از general_text_handler باشد
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_search_handler))

    # ... بقیه کدها ...