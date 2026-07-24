import uuid
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes
from database import search_hadiths
from services.quran_api import get_ayah


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    کاربر در هر چت/گروهی می‌نویسد: @نام_ربات عبارت
    و نتایج جستجو (هم حدیث هم آیه در صورت فرمت شماره) نمایش داده می‌شود.
    """
    query_text = update.inline_query.query.strip()
    results = []

    if not query_text:
        await update.inline_query.answer(results, cache_time=1)
        return

    # اگر فرمت شماره آیه بود (مثلا 2:255)
    if ":" in query_text and query_text.replace(":", "").isdigit():
        surah, ayah = query_text.split(":")
        try:
            data = await get_ayah(int(surah), int(ayah))
            if data and data.get("arabic"):
                content = f"{data['arabic']}\n\n🔹 ترجمه:\n{data['translation']}"
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title=f"آیه {surah}:{ayah}",
                        description=data["translation"][:80],
                        input_message_content=InputTextMessageContent(content),
                    )
                )
        except Exception:
            pass

    # جستجوی احادیث
    hadith_rows = search_hadiths(query_text)
    for row in hadith_rows[:10]:
        content = f"{row['arabic_text']}\n\n🔹 ترجمه:\n{row['translation_text']}"
        if row["source_book"]:
            content += f"\n\n📚 منبع: {row['source_book']}"
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=f"حدیث - {row['narrator'] or 'معصومین'}",
                description=row["translation_text"][:100],
                input_message_content=InputTextMessageContent(content),
            )
        )

    await update.inline_query.answer(results, cache_time=1)

# اضافه کردن به انتهای فایل inline.py

async def enhanced_inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نسخه پیشرفته جستجوی Inline با پشتیبانی از همه بخش‌ها"""
    from handlers.search import get_search_engine, format_search_result
    
    query_text = update.inline_query.query.strip()
    results = []
    
    if not query_text:
        # نمایش راهنما در حالت خالی
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="🔍 جستجوی هوشمند",
                description="عبارت مورد نظر را وارد کنید...",
                input_message_content=InputTextMessageContent(
                    "🔍 برای جستجو، عبارت مورد نظر را تایپ کنید.\n"
                    "مثال: @نام_ربات صبر\n"
                    "مثال: @نام_ربات 2:255"
                )
            )
        )
        await update.inline_query.answer(results, cache_time=1)
        return
    
    # اگر فرمت آیه بود
    if ":" in query_text and query_text.replace(":", "").isdigit():
        try:
            surah, ayah = query_text.split(":")
            data = await get_ayah(int(surah), int(ayah))
            if data and data.get("arabic"):
                content = f"{data['arabic']}\n\n🔹 ترجمه:\n{data['translation']}"
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title=f"📖 آیه {surah}:{ayah}",
                        description=data["translation"][:80],
                        input_message_content=InputTextMessageContent(content),
                        thumbnail_url="https://cdn-icons-png.flaticon.com/64/3063/3063108.png"
                    )
                )
                await update.inline_query.answer(results, cache_time=1)
                return
        except:
            pass
    
    # جستجوی هوشمند در همه بخش‌ها
    engine = get_search_engine()
    search_results = engine.search_all(query_text, limit_per_category=3)
    
    # اضافه کردن نتایج حدیث
    for item in search_results.get("hadiths", [])[:3]:
        content = f"📿 حدیث\n\n{item['arabic_text'][:300]}..."
        if item.get("translation_text"):
            content += f"\n\n🔹 ترجمه:\n{item['translation_text'][:200]}..."
        results.append(
            InlineQueryResultArticle(
                id=f"hadith_{item['id']}",
                title=f"📿 حدیث - {item.get('narrator', 'معصومین')}",
                description=item.get("translation_text", "")[:100],
                input_message_content=InputTextMessageContent(content),
                thumbnail_url="https://cdn-icons-png.flaticon.com/64/3602/3602123.png"
            )
        )
    
    # اضافه کردن نتایج مفاتیح
    for item in search_results.get("mafatih", [])[:3]:
        content = f"📗 {item['title']}\n\n{item.get('arabic_text', '')[:300]}..."
        if item.get("translation_text"):
            content += f"\n\n🔹 ترجمه:\n{item['translation_text'][:200]}..."
        results.append(
            InlineQueryResultArticle(
                id=f"mafatih_{item['id']}",
                title=f"📗 {item['title']}",
                description=item.get("translation_text", "")[:100],
                input_message_content=InputTextMessageContent(content),
                thumbnail_url="https://cdn-icons-png.flaticon.com/64/3003/3003944.png"
            )
        )
    
    # اضافه کردن نتایج نهج‌البلاغه
    for item in search_results.get("nahj", [])[:3]:
        cat_name = {
            "khutbah": "خطبه",
            "letter": "نامه",
            "hekmat": "حکمت"
        }.get(item.get("category", ""), item.get("category", ""))
        
        content = f"🕌 {cat_name} {item.get('number', '')}\n"
        if item.get("title"):
            content += f"📌 {item['title']}\n\n"
        content += f"{item.get('arabic_text', '')[:300]}..."
        if item.get("translation_text"):
            content += f"\n\n🔹 ترجمه:\n{item['translation_text'][:200]}..."
        
        results.append(
            InlineQueryResultArticle(
                id=f"nahj_{item['id']}",
                title=f"🕌 {cat_name} {item.get('number', '')}",
                description=item.get("title", "") or item.get("translation_text", "")[:100],
                input_message_content=InputTextMessageContent(content),
                thumbnail_url="https://cdn-icons-png.flaticon.com/64/2270/2270963.png"
            )
        )
    
    # اگر نتیجه‌ای پیدا نشد
    if not results:
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="🔍 نتیجه‌ای پیدا نشد",
                description=f"برای «{query_text}» نتیجه‌ای یافت نشد.",
                input_message_content=InputTextMessageContent(
                    f"🔍 نتیجه‌ای برای «{query_text}» پیدا نشد.\n"
                    "لطفاً عبارت دیگری را امتحان کنید."
                )
            )
        )
    
    await update.inline_query.answer(results[:50], cache_time=1)