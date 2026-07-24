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

SEARCH_RESULTS_PER_PAGE = 20  # افزایش به ۲۰ نتیجه در هر صفحه
MIN_FUZZY_SCORE = 30  # کاهش آستانه برای پیدا کردن نتایج بیشتر


class SmartSearch:
    """کلاس اصلی جستجوی هوشمند"""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
    
    def search_hadiths_advanced(self, query: str, limit: int = 100) -> List[Dict]:
        """جستجوی پیشرفته احادیث - بدون محدودیت"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # جستجوی مستقیم با LIKE (دقیق‌تر از FTS)
        like = f"%{query}%"
        like_arabic = f"%{query}%"
        
        # جستجو در ترجمه و عربی
        rows = conn.execute("""
            SELECT * FROM hadiths 
            WHERE translation_text LIKE ? 
            OR arabic_text LIKE ?
            OR tafsir_text LIKE ?
            OR narrator LIKE ?
            OR source_book LIKE ?
            OR chapter LIKE ?
            ORDER BY id
            LIMIT ?
        """, (like, like_arabic, like, like, like, like, limit)).fetchall()
        
        results = [dict(row) for row in rows]
        conn.close()
        
        # اگر نتیجه کم بود، جستجوی فازی انجام بده
        if len(results) < 10:
            fuzzy_results = self._fuzzy_search_hadiths(query)
            # ترکیب و حذف تکراری
            existing_ids = {r["id"] for r in results}
            for item in fuzzy_results:
                if item["id"] not in existing_ids:
                    results.append(item)
                    if len(results) >= limit:
                        break
        
        return results
    
    def _fuzzy_search_hadiths(self, query: str, limit: int = 100) -> List[Dict]:
        """جستجوی فازی در احادیث"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        all_hadiths = conn.execute("SELECT * FROM hadiths").fetchall()
        conn.close()
        
        query_lower = query.lower()
        scored = []
        
        for item in all_hadiths:
            item_dict = dict(item)
            best_score = 0
            
            # بررسی در ترجمه
            if item_dict.get("translation_text"):
                score = fuzz.partial_ratio(query_lower, item_dict["translation_text"].lower())
                if score > best_score:
                    best_score = score
            
            # بررسی در عربی
            if item_dict.get("arabic_text"):
                score = fuzz.partial_ratio(query_lower, item_dict["arabic_text"].lower())
                if score > best_score:
                    best_score = score
            
            # بررسی در راوی و منبع
            if item_dict.get("narrator"):
                score = fuzz.partial_ratio(query_lower, item_dict["narrator"].lower())
                if score > best_score:
                    best_score = score
            
            if best_score >= MIN_FUZZY_SCORE:
                scored.append((item_dict, best_score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored[:limit]]
    
    def search_mafatih_advanced(self, query: str, limit: int = 100) -> List[Dict]:
        """جستجوی پیشرفته مفاتیح - بدون محدودیت"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        like = f"%{query}%"
        
        rows = conn.execute("""
            SELECT * FROM mafatih 
            WHERE title LIKE ? 
            OR arabic_text LIKE ?
            OR translation_text LIKE ?
            OR tafsir_text LIKE ?
            OR category LIKE ?
            ORDER BY id
            LIMIT ?
        """, (like, like, like, like, like, limit)).fetchall()
        
        results = [dict(row) for row in rows]
        conn.close()
        
        # اگر نتیجه کم بود، جستجوی فازی
        if len(results) < 10:
            fuzzy_results = self._fuzzy_search_mafatih(query)
            existing_ids = {r["id"] for r in results}
            for item in fuzzy_results:
                if item["id"] not in existing_ids:
                    results.append(item)
                    if len(results) >= limit:
                        break
        
        return results
    
    def _fuzzy_search_mafatih(self, query: str, limit: int = 100) -> List[Dict]:
        """جستجوی فازی در مفاتیح"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        all_items = conn.execute("SELECT * FROM mafatih").fetchall()
        conn.close()
        
        query_lower = query.lower()
        scored = []
        
        for item in all_items:
            item_dict = dict(item)
            best_score = 0
            
            if item_dict.get("title"):
                score = fuzz.partial_ratio(query_lower, item_dict["title"].lower())
                if score > best_score:
                    best_score = score
            
            if item_dict.get("translation_text"):
                score = fuzz.partial_ratio(query_lower, item_dict["translation_text"].lower())
                if score > best_score:
                    best_score = score
            
            if item_dict.get("arabic_text"):
                score = fuzz.partial_ratio(query_lower, item_dict["arabic_text"].lower())
                if score > best_score:
                    best_score = score
            
            if best_score >= MIN_FUZZY_SCORE:
                scored.append((item_dict, best_score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored[:limit]]
    
    def search_nahj_advanced(self, query: str, limit: int = 100) -> List[Dict]:
        """جستجوی پیشرفته نهج‌البلاغه - بدون محدودیت"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        like = f"%{query}%"
        
        rows = conn.execute("""
            SELECT * FROM nahj_balagha 
            WHERE title LIKE ? 
            OR arabic_text LIKE ?
            OR translation_text LIKE ?
            OR tafsir_text LIKE ?
            OR category LIKE ?
            ORDER BY id
            LIMIT ?
        """, (like, like, like, like, like, limit)).fetchall()
        
        results = [dict(row) for row in rows]
        conn.close()
        
        if len(results) < 10:
            fuzzy_results = self._fuzzy_search_nahj(query)
            existing_ids = {r["id"] for r in results}
            for item in fuzzy_results:
                if item["id"] not in existing_ids:
                    results.append(item)
                    if len(results) >= limit:
                        break
        
        return results
    
    def _fuzzy_search_nahj(self, query: str, limit: int = 100) -> List[Dict]:
        """جستجوی فازی در نهج‌البلاغه"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        all_items = conn.execute("SELECT * FROM nahj_balagha").fetchall()
        conn.close()
        
        query_lower = query.lower()
        scored = []
        
        for item in all_items:
            item_dict = dict(item)
            best_score = 0
            
            if item_dict.get("title"):
                score = fuzz.partial_ratio(query_lower, item_dict["title"].lower())
                if score > best_score:
                    best_score = score
            
            if item_dict.get("translation_text"):
                score = fuzz.partial_ratio(query_lower, item_dict["translation_text"].lower())
                if score > best_score:
                    best_score = score
            
            if item_dict.get("arabic_text"):
                score = fuzz.partial_ratio(query_lower, item_dict["arabic_text"].lower())
                if score > best_score:
                    best_score = score
            
            if best_score >= MIN_FUZZY_SCORE:
                scored.append((item_dict, best_score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored[:limit]]
    
    def search_all(self, query: str, limit_per_category: int = 100) -> Dict[str, List]:
        """جستجو در همه بخش‌ها - بدون محدودیت"""
        return {
            "hadiths": self.search_hadiths_advanced(query, limit=limit_per_category),
            "mafatih": self.search_mafatih_advanced(query, limit=limit_per_category),
            "nahj": self.search_nahj_advanced(query, limit=limit_per_category),
        }


_search_engine = None

def get_search_engine() -> SmartSearch:
    global _search_engine
    if _search_engine is None:
        _search_engine = SmartSearch()
    return _search_engine


def get_category_emoji(category: str) -> str:
    emojis = {
        "hadiths": "📿",
        "mafatih": "📗",
        "nahj": "🕌",
        "khutbah": "📜",
        "letter": "✉️",
        "hekmat": "💎",
    }
    return emojis.get(category, "🔍")


def format_search_result(item: Dict, category: str) -> str:
    """فرمت‌بندی نتیجه جستجو - بدون امتیاز تطابق"""
    emoji = get_category_emoji(category)
    
    if category == "hadiths":
        text = f"{emoji} **حدیث**\n"
        text += f"📖 {item.get('arabic_text', '')[:300]}\n\n"
        text += f"🔹 ترجمه: {item.get('translation_text', '')[:300]}"
        if item.get("narrator"):
            text += f"\n👤 راوی: {item['narrator']}"
        if item.get("source_book"):
            text += f"\n📚 منبع: {item['source_book']}"
        text += f"\n🆔 شناسه: {item['id']}"
        
    elif category == "mafatih":
        text = f"{emoji} **{item.get('title', 'دعا')}**\n"
        if item.get("arabic_text"):
            text += f"\n🌿 {item['arabic_text'][:300]}"
        if item.get("translation_text"):
            text += f"\n\n🔹 ترجمه: {item['translation_text'][:300]}"
        if item.get("category"):
            cat_names = {
                "daily": "اعمال روزانه",
                "weekly": "اعمال هفتگی",
                "monthly": "اعمال ماهانه",
                "ziyarat": "زیارات",
                "munajat": "مناجات",
                "special": "اعمال ویژه"
            }
            text += f"\n📂 دسته: {cat_names.get(item['category'], item['category'])}"
        
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
            text += f"\n\n🌿 {item['arabic_text'][:300]}"
        if item.get("translation_text"):
            text += f"\n\n🔹 ترجمه: {item['translation_text'][:300]}"
    
    return text


def get_search_keyboard(results: Dict, query: str, page: int = 0) -> InlineKeyboardMarkup:
    buttons = []
    
    for category, items in results.items():
        if items:
            label = {
                "hadiths": f"📿 احادیث ({len(items)})",
                "mafatih": f"📗 مفاتیح ({len(items)})",
                "nahj": f"🕌 نهج‌البلاغه ({len(items)})",
            }.get(category, category)
            
            buttons.append([
                InlineKeyboardButton(
                    label,
                    callback_data=f"search_cat_{category}_{query[:50]}_{page}"
                )
            ])
    
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
    if query is None:
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
    
    # جستجوی پیشرفته - بدون محدودیت
    engine = get_search_engine()
    results = engine.search_all(query, limit_per_category=200)  # افزایش به ۲۰۰
    
    total_results = sum(len(items) for items in results.values())
    if total_results == 0:
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
                "لطفاً عبارت دیگری را امتحان کنید.",
                parse_mode="Markdown"
            )
        return
    
    context.user_data["search_results"] = results
    context.user_data["search_query"] = query
    
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
    query = update.callback_query
    await query.answer()
    
    data = query.data
    parts = data.split("_")
    
    if len(parts) < 3:
        return
    
    action = parts[1]
    
    if action == "cat":
        category = parts[2]
        search_query = "_".join(parts[3:-1])
        page = int(parts[-1])
        
        results = context.user_data.get("search_results", {})
        items = results.get(category, [])
        
        if not items:
            await query.edit_message_text("نتیجه‌ای برای این دسته پیدا نشد.")
            return
        
        start = page * SEARCH_RESULTS_PER_PAGE
        end = start + SEARCH_RESULTS_PER_PAGE
        page_items = items[start:end]
        
        text = f"🔍 **نتایج {get_category_emoji(category)}**\n\n"
        for item in page_items:
            text += format_search_result(item, category) + "\n\n"
            text += "─" * 30 + "\n\n"
        
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
        search_query = "_".join(parts[2:])
        results = context.user_data.get("search_results", {})
        await query.edit_message_text(
            f"🔍 **نتایج جستجوی «{search_query}»**\n\n"
            f"📊 **{sum(len(items) for items in results.values())}** نتیجه یافت شد:\n\n",
            reply_markup=get_search_keyboard(results, search_query),
            parse_mode="Markdown"
        )


async def get_suggestion(query: str) -> str:
    common_words = [
        "صبر", "توحید", "اخلاق", "نماز", "روزه", "حج", "زکات", "جهاد",
        "توبه", "استغفار", "توکل", "ایمان", "اسلام", "قرآن", "حدیث",
        "امام", "علی", "حسین", "فاطمه", "محمد", "نبوت", "معاد", "عدل",
        "دعا", "زیارت", "مناجات", "مفاتیح", "نهج", "بلاغه", "نماز", "شب"
    ]
    
    best_match = process.extractOne(query, common_words, scorer=fuzz.partial_ratio)
    if best_match and best_match[1] > 50:
        return best_match[0]
    
    return None


async def enhanced_text_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    if update.effective_chat.type != "private":
        engine = get_search_engine()
        results = engine.search_hadiths_advanced(text, limit=50)
        
        if not results:
            all_results = engine.search_all(text, limit_per_category=50)
            total = sum(len(items) for items in all_results.values())
            
            if total == 0:
                await update.message.reply_text(
                    f"🔍 نتیجه‌ای برای «{text}» پیدا نشد."
                )
                return
            
            text_msg = f"🔍 **نتایج جستجوی «{text}»**\n\n"
            for cat, items in all_results.items():
                if items:
                    label = {
                        "hadiths": "📿 احادیث",
                        "mafatih": "📗 مفاتیح",
                        "nahj": "🕌 نهج‌البلاغه",
                    }.get(cat, cat)
                    text_msg += f"• {label}: {len(items)} مورد\n"
            
            buttons = [[
                InlineKeyboardButton(
                    "📚 مشاهده همه نتایج",
                    callback_data=f"search_back_{text[:50]}"
                )
            ]]
            
            context.user_data["search_results"] = all_results
            context.user_data["search_query"] = text
            
            await update.message.reply_text(
                text_msg,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown"
            )
            return
        
        first_result = results[0]
        text_msg = format_search_result(first_result, "hadiths")
        
        buttons = [[
            InlineKeyboardButton(
                f"📚 {len(results)} نتیجه یافت شد - مشاهده همه",
                callback_data=f"search_cat_hadiths_{text[:50]}_0"
            )
        ]]
        
        context.user_data["search_results"] = {"hadiths": results}
        context.user_data["search_query"] = text
        
        await update.message.reply_text(
            text_msg,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
        return
    
    await search_command(update, context, text)