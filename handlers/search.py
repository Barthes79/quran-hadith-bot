import re
import logging
from typing import List, Dict, Any, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from thefuzz import fuzz, process
import sqlite3

from database import get_connection, search_hadiths, get_nahj_item, get_mafatih_by_id
from services.quran_api import get_ayah
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

# تنظیمات جستجو
SEARCH_RESULTS_PER_PAGE = 5
MIN_FUZZY_SCORE = 60  # حداقل امتیاز برای نمایش نتیجه


class SmartSearch:
    """کلاس اصلی جستجوی هوشمند"""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._init_fts_tables()
    
    def _init_fts_tables(self):
        """ایجاد جداول FTS برای جستجوی تمام‌متن"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # جدول FTS برای احادیث
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS hadiths_fts USING fts5(
                id UNINDEXED,
                arabic_text,
                translation_text,
                tafsir_text,
                narrator,
                source_book,
                chapter,
                topic_names
            )
        """)
        
        # جدول FTS برای مفاتیح
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS mafatih_fts USING fts5(
                id UNINDEXED,
                title,
                arabic_text,
                translation_text,
                tafsir_text,
                category
            )
        """)
        
        # جدول FTS برای نهج‌البلاغه
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS nahj_fts USING fts5(
                id UNINDEXED,
                category,
                number UNINDEXED,
                title,
                arabic_text,
                translation_text,
                tafsir_text
            )
        """)
        
        conn.commit()
        
        # به‌روزرسانی داده‌های FTS
        self._sync_fts_tables()
        conn.close()
    
    def _sync_fts_tables(self):
        """همگام‌سازی جداول FTS با داده‌های اصلی"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # همگام‌سازی احادیث
        cur.execute("""
            INSERT OR REPLACE INTO hadiths_fts(
                id, arabic_text, translation_text, tafsir_text, 
                narrator, source_book, chapter, topic_names
            )
            SELECT 
                h.id, h.arabic_text, h.translation_text, 
                COALESCE(h.tafsir_text, ''),
                COALESCE(h.narrator, ''),
                COALESCE(h.source_book, ''),
                COALESCE(h.chapter, ''),
                COALESCE(GROUP_CONCAT(t.topic_name, ' '), '')
            FROM hadiths h
            LEFT JOIN hadith_topics t ON h.id = t.hadith_id
            GROUP BY h.id
        """)
        
        # همگام‌سازی مفاتیح
        cur.execute("""
            INSERT OR REPLACE INTO mafatih_fts(
                id, title, arabic_text, translation_text, tafsir_text, category
            )
            SELECT 
                id, title, arabic_text, 
                COALESCE(translation_text, ''),
                COALESCE(tafsir_text, ''),
                category
            FROM mafatih
        """)
        
        # همگام‌سازی نهج‌البلاغه
        cur.execute("""
            INSERT OR REPLACE INTO nahj_fts(
                id, category, number, title, arabic_text, translation_text, tafsir_text
            )
            SELECT 
                id, category, number, 
                COALESCE(title, ''),
                arabic_text, translation_text,
                COALESCE(tafsir_text, '')
            FROM nahj_balagha
        """)
        
        conn.commit()
        conn.close()
    
    def fts_search(self, table: str, query: str, limit: int = 20) -> List[Dict]:
        """جستجوی تمام‌متن با FTS5"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # تبدیل عبارت به فرمت FTS (با عملگر AND)
        words = query.strip().split()
        fts_query = " AND ".join([f'"{w}"' for w in words]) if len(words) > 1 else f'"{query}"'
        
        try:
            rows = conn.execute(f"""
                SELECT 
                    {table}.*,
                    rank as relevance
                FROM {table}_fts fts
                JOIN {table} ON {table}.id = fts.id
                WHERE {table}_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (fts_query, limit)).fetchall()
        except sqlite3.OperationalError:
            # اگر عبارت جستجو خالی یا مشکل‌دار بود
            rows = []
        
        conn.close()
        return [dict(row) for row in rows]
    
    def fuzzy_search(self, items: List[Dict], query: str, 
                     text_fields: List[str], limit: int = 10) -> List[Tuple[Dict, int]]:
        """جستجوی فازی با امتیازدهی"""
        results = []
        query_lower = query.lower()
        
        for item in items:
            best_score = 0
            best_match = ""
            
            for field in text_fields:
                text = item.get(field, "")
                if not text:
                    continue
                
                # امتیاز تطابق کامل
                if query_lower in text.lower():
                    score = 100
                else:
                    # امتیاز فازی
                    score = fuzz.partial_ratio(query_lower, text.lower())
                
                if score > best_score:
                    best_score = score
                    best_match = text
            
            if best_score >= MIN_FUZZY_SCORE:
                results.append((item, best_score, best_match))
        
        # مرتب‌سازی بر اساس امتیاز
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
    
    def search_hadiths_advanced(self, query: str, limit: int = 20) -> List[Dict]:
        """جستجوی پیشرفته احادیث با ترکیب FTS و فازی"""
        # ۱. ابتدا جستجوی FTS
        fts_results = self.fts_search("hadiths", query, limit=limit)
        
        if len(fts_results) >= limit:
            return fts_results
        
        # ۲. اگر نتیجه کافی نبود، جستجوی فازی
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        all_hadiths = conn.execute(
            "SELECT * FROM hadiths"
        ).fetchall()
        conn.close()
        
        fuzzy_results = self.fuzzy_search(
            [dict(row) for row in all_hadiths],
            query,
            ["arabic_text", "translation_text", "tafsir_text", "narrator", "source_book", "chapter"],
            limit=limit
        )
        
        # ترکیب نتایج (حذف تکراری‌ها)
        fts_ids = {r["id"] for r in fts_results}
        combined = list(fts_results)
        
        for item, score, _ in fuzzy_results:
            if item["id"] not in fts_ids:
                item["relevance"] = score  # امتیاز فازی را به عنوان relevance اضافه می‌کنیم
                combined.append(item)
                if len(combined) >= limit:
                    break
        
        return combined
    
    def search_mafatih_advanced(self, query: str, limit: int = 20) -> List[Dict]:
        """جستجوی پیشرفته مفاتیح"""
        # جستجوی FTS
        fts_results = self.fts_search("mafatih", query, limit=limit)
        
        if len(fts_results) >= limit:
            return fts_results
        
        # جستجوی فازی
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        all_items = conn.execute("SELECT * FROM mafatih").fetchall()
        conn.close()
        
        fuzzy_results = self.fuzzy_search(
            [dict(row) for row in all_items],
            query,
            ["title", "arabic_text", "translation_text", "tafsir_text"],
            limit=limit
        )
        
        fts_ids = {r["id"] for r in fts_results}
        combined = list(fts_results)
        
        for item, score, _ in fuzzy_results:
            if item["id"] not in fts_ids:
                item["relevance"] = score
                combined.append(item)
                if len(combined) >= limit:
                    break
        
        return combined
    
    def search_nahj_advanced(self, query: str, limit: int = 20) -> List[Dict]:
        """جستجوی پیشرفته نهج‌البلاغه"""
        fts_results = self.fts_search("nahj_balagha", query, limit=limit)
        
        if len(fts_results) >= limit:
            return fts_results
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        all_items = conn.execute("SELECT * FROM nahj_balagha").fetchall()
        conn.close()
        
        fuzzy_results = self.fuzzy_search(
            [dict(row) for row in all_items],
            query,
            ["title", "arabic_text", "translation_text", "tafsir_text"],
            limit=limit
        )
        
        fts_ids = {r["id"] for r in fts_results}
        combined = list(fts_results)
        
        for item, score, _ in fuzzy_results:
            if item["id"] not in fts_ids:
                item["relevance"] = score
                combined.append(item)
                if len(combined) >= limit:
                    break
        
        return combined
    
    def search_all(self, query: str, limit_per_category: int = 5) -> Dict[str, List]:
        """جستجو در همه بخش‌ها به صورت همزمان"""
        return {
            "hadiths": self.search_hadiths_advanced(query, limit=limit_per_category),
            "mafatih": self.search_mafatih_advanced(query, limit=limit_per_category),
            "nahj": self.search_nahj_advanced(query, limit=limit_per_category),
        }


# نمونه Singleton برای استفاده در سراسر برنامه
_search_engine = None

def get_search_engine() -> SmartSearch:
    global _search_engine
    if _search_engine is None:
        _search_engine = SmartSearch()
    return _search_engine


# ============================================
# هندلرهای جستجو
# ============================================

def get_category_emoji(category: str) -> str:
    """دریافت ایموجی مناسب برای هر دسته"""
    emojis = {
        "hadiths": "📿",
        "mafatih": "📗",
        "nahj": "🕌",
        "khutbah": "📜",
        "letter": "✉️",
        "hekmat": "💎",
    }
    return emojis.get(category, "🔍")


def format_search_result(item: Dict, category: str, score: int = None) -> str:
    """فرمت‌بندی نتیجه جستجو برای نمایش"""
    emoji = get_category_emoji(category)
    
    if category == "hadiths":
        text = f"{emoji} **حدیث**\n"
        text += f"📖 {item.get('arabic_text', '')[:200]}\n\n"
        text += f"🔹 ترجمه: {item.get('translation_text', '')[:150]}"
        if item.get("narrator"):
            text += f"\n👤 راوی: {item['narrator']}"
        if item.get("source_book"):
            text += f"\n📚 منبع: {item['source_book']}"
        text += f"\n🆔 شناسه: {item['id']}"
        
    elif category == "mafatih":
        text = f"{emoji} **{item.get('title', 'دعا')}**\n"
        if item.get("arabic_text"):
            text += f"\n🌿 {item['arabic_text'][:200]}"
        if item.get("translation_text"):
            text += f"\n\n🔹 ترجمه: {item['translation_text'][:150]}"
        text += f"\n📂 دسته: {item.get('category', '-')}"
        
    elif category == "nahj" or category in ["khutbah", "letter", "hekmat"]:
        cat_name = {
            "khutbah": "خطبه",
            "letter": "نامه",
            "hekmat": "حکمت"
        }.get(item.get("category", ""), item.get("category", ""))
        
        text = f"{emoji} **{cat_name} {item.get('number', '')}**"
        if item.get("title"):
            text += f"\n📌 {item['title']}"
        if item.get("arabic_text"):
            text += f"\n\n🌿 {item['arabic_text'][:200]}"
        if item.get("translation_text"):
            text += f"\n\n🔹 ترجمه: {item['translation_text'][:150]}"
    
    if score is not None:
        text += f"\n\n🎯 امتیاز تطابق: {score}%"
    
    return text


def get_search_keyboard(results: Dict, query: str, page: int = 0) -> InlineKeyboardMarkup:
    """ساخت کیبورد برای نتایج جستجو"""
    buttons = []
    
    # نمایش نتایج به صورت دسته‌بندی شده
    for category, items in results.items():
        if items:
            first_item = items[0]
            label = {
                "hadiths": f"📿 احادیث ({len(items)})",
                "mafatih": f"📗 مفاتیح ({len(items)})",
                "nahj": f"🕌 نهج‌البلاغه ({len(items)})",
            }.get(category, category)
            
            # دکمه برای نمایش نتایج این دسته
            buttons.append([
                InlineKeyboardButton(
                    label,
                    callback_data=f"search_cat_{category}_{query[:50]}_{page}"
                )
            ])
    
    # دکمه‌های ناوبری
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"search_page_{page-1}_{query[:50]}"))
    nav_row.append(InlineKeyboardButton("🔄 جستجوی جدید", callback_data="menu_search"))
    if len(buttons) > 0:
        nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"search_page_{page+1}_{query[:50]}"))
    
    if nav_row:
        buttons.append(nav_row)
    
    buttons.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_back")])
    
    return InlineKeyboardMarkup(buttons)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str = None):
    """دستور اصلی جستجو"""
    if query is None:
        # اگر کاربر فقط /search زده باشد
        await update.message.reply_text(
            "🔍 **جستجوی هوشمند**\n\n"
            "عبارت مورد نظر خود را وارد کنید.\n"
            "مثال: `صبر` یا `توحید` یا `2:255`\n\n"
            "می‌توانید در تمام بخش‌های زیر جستجو کنید:\n"
            "📿 احادیث\n📗 مفاتیح‌الجنان\n🕌 نهج‌البلاغه",
            parse_mode="Markdown"
        )
        return
    
    # بررسی اگر فرمت آیه بود
    if ":" in query and query.replace(":", "").isdigit():
        try:
            surah, ayah = query.split(":")
            data = await get_ayah(int(surah), int(ayah))
            if data:
                text = f"📖 **سوره {surah} - آیه {ayah}**\n\n"
                text += f"{data['arabic']}\n\n"
                text += f"🔹 ترجمه:\n{data['translation']}"
                await update.message.reply_text(text, parse_mode="Markdown")
                return
        except:
            pass
    
    # جستجوی پیشرفته
    engine = get_search_engine()
    results = engine.search_all(query, limit_per_category=5)
    
    # بررسی اینکه آیا نتیجه‌ای پیدا شده
    total_results = sum(len(items) for items in results.values())
    if total_results == 0:
        # پیشنهاد کلمات مشابه
        suggestion = await get_suggestion(query)
        if suggestion:
            await update.message.reply_text(
                f"🔍 **نتیجه‌ای برای «{query}» پیدا نشد.**\n\n"
                f"💡 آیا منظور شما «{suggestion}» بود؟\n"
                f"برای جستجو دوباره عبارت را ارسال کنید.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"🔍 **نتیجه‌ای برای «{query}» پیدا نشد.**\n\n"
                "لطفاً عبارت دیگری را امتحان کنید یا از جستجوی دقیق‌تر استفاده کنید.",
                parse_mode="Markdown"
            )
        return
    
    # ذخیره نتایج در context برای استفاده در callback
    context.user_data["search_results"] = results
    context.user_data["search_query"] = query
    
    # نمایش خلاصه نتایج
    text = f"🔍 **نتایج جستجوی «{query}»**\n\n"
    text += f"📊 **{total_results}** نتیجه یافت شد:\n\n"
    
    for category, items in results.items():
        if items:
            label = {
                "hadiths": "📿 احادیث",
                "mafatih": "📗 مفاتیح",
                "nahj": "🕌 نهج‌البلاغه",
            }.get(category, category)
            text += f"• {label}: {len(items)} مورد\n"
    
    await update.message.reply_text(
        text,
        reply_markup=get_search_keyboard(results, query),
        parse_mode="Markdown"
    )


async def search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای کلیک روی نتایج جستجو"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    parts = data.split("_")
    
    if len(parts) < 3:
        return
    
    action = parts[1]
    
    if action == "cat":
        # نمایش نتایج یک دسته خاص
        category = parts[2]
        search_query = "_".join(parts[3:-1])  # عبارت جستجو ممکن است شامل _ باشد
        page = int(parts[-1])
        
        results = context.user_data.get("search_results", {})
        items = results.get(category, [])
        
        if not items:
            await query.edit_message_text("نتیجه‌ای برای این دسته پیدا نشد.")
            return
        
        # صفحه‌بندی نتایج
        start = page * SEARCH_RESULTS_PER_PAGE
        end = start + SEARCH_RESULTS_PER_PAGE
        page_items = items[start:end]
        
        text = f"🔍 **نتایج {get_category_emoji(category)}**\n\n"
        for item in page_items:
            score = item.get("relevance", 0)
            text += format_search_result(item, category, score) + "\n\n"
            text += "─" * 30 + "\n\n"
        
        # دکمه‌های برگشت
        buttons = []
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                "◀️ قبلی",
                callback_data=f"search_cat_{category}_{search_query}_{page-1}"
            ))
        if end < len(items):
            nav_row.append(InlineKeyboardButton(
                "بعدی ▶️",
                callback_data=f"search_cat_{category}_{search_query}_{page+1}"
            ))
        if nav_row:
            buttons.append(nav_row)
        
        buttons.append([InlineKeyboardButton("🔙 بازگشت به نتایج", callback_data=f"search_back_{search_query}")])
        buttons.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_back")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
    
    elif action == "page":
        # تغییر صفحه نتایج کلی
        page = int(parts[2])
        search_query = "_".join(parts[3:])
        
        results = context.user_data.get("search_results", {})
        await query.edit_message_text(
            f"🔍 **نتایج جستجوی «{search_query}»**\n\n"
            f"📊 **{sum(len(items) for items in results.values())}** نتیجه یافت شد:\n\n",
            reply_markup=get_search_keyboard(results, search_query, page),
            parse_mode="Markdown"
        )
    
    elif action == "back":
        # برگشت به نتایج کلی
        search_query = "_".join(parts[2:])
        results = context.user_data.get("search_results", {})
        await query.edit_message_text(
            f"🔍 **نتایج جستجوی «{search_query}»**\n\n"
            f"📊 **{sum(len(items) for items in results.values())}** نتیجه یافت شد:\n\n",
            reply_markup=get_search_keyboard(results, search_query),
            parse_mode="Markdown"
        )


async def get_suggestion(query: str) -> str:
    """پیشنهاد کلمه مشابه در صورت عدم وجود نتیجه"""
    # لیست کلمات کلیدی معروف
    common_words = [
        "صبر", "توحید", "اخلاق", "نماز", "روزه", "حج", "زکات", "جهاد",
        "توبه", "استغفار", "توکل", "ایمان", "اسلام", "قرآن", "حدیث",
        "امام", "علی", "حسین", "فاطمه", "محمد", "نبوت", "معاد", "عدل"
    ]
    
    # پیدا کردن نزدیک‌ترین کلمه
    best_match = process.extractOne(query, common_words, scorer=fuzz.partial_ratio)
    if best_match and best_match[1] > 60:
        return best_match[0]
    
    return None


# ============================================
# ادغام با سیستم موجود
# ============================================

async def enhanced_text_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """جایگزین text_search_handler قبلی با جستجوی هوشمند"""
    # اگر کاربر در گروه بود و فقط یک کلمه ساده ارسال کرد، از جستجوی سریع استفاده کن
    if update.effective_chat.type != "private":
        # در گروه‌ها فقط جستجوی حدیث انجام بده
        engine = get_search_engine()
        results = engine.search_hadiths_advanced(text, limit=5)
        
        if not results:
            await update.message.reply_text(
                f"🔍 حدیثی با عبارت «{text}» پیدا نشد."
            )
            return
        
        # نمایش اولین نتیجه
        first_result = results[0]
        text_msg = format_search_result(first_result, "hadiths", first_result.get("relevance", 0))
        
        # دکمه برای دیدن بقیه نتایج
        buttons = [[
            InlineKeyboardButton(
                f"📚 {len(results)} نتیجه یافت شد - مشاهده همه",
                callback_data=f"search_cat_hadiths_{text[:50]}_0"
            )
        ]]
        
        await update.message.reply_text(
            text_msg,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
        return
    
    # در چت خصوصی از جستجوی کامل استفاده کن
    await search_command(update, context, text)