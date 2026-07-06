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
