import re
import logging
import json
import hashlib
from typing import List, Dict, Any, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from thefuzz import fuzz, process
import sqlite3

from database import get_connection, search_hadiths, get_nahj_item, get_mafatih_by_id
from services.quran_api import get_ayah
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

MIN_FUZZY_SCORE = 30
# دیکشنری موقت برای ذخیره نتایج جستجو (با شناسه یکتا)
SEARCH_CACHE = {}


class SmartSearch:
    """کلاس اصلی جستجوی هوشمند"""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
    
    def search_hadiths_advanced(self, query: str) -> List[Dict]:
        """جستجوی پیشرفته احادیث - بدون محدودیت"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        like = f"%{query}%"
        
        rows = conn.execute("""
            SELECT * FROM hadiths 
            WHERE translation_text LIKE ? 
            OR arabic_text LIKE ?
            OR tafsir_text LIKE ?
            OR narrator LIKE ?
            OR source_book LIKE ?
            OR chapter LIKE ?
        """, (like, like, like, like, like, like)).fetchall()
        
        results = [dict(row) for row in rows]
        conn.close()
        
        # اگر نتیجه کم بود، جستجوی فازی
        if len(results) < 5:
            fuzzy_results = self._fuzzy_search_hadiths(query)
            existing_ids = {r["id"] for r in results}
            for item in fuzzy_results:
                if item["id"] not in existing_ids:
                    results.append(item)
        
        return results
    
    def _fuzzy_search_hadiths(self, query: str) -> List[Dict]:
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
        return [item for item, _ in scored]
    
    def search_mafatih_advanced(self, query: str) -> List[Dict]:
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
        """, (like, like, like, like, like)).fetchall()
        
        results = [dict(row) for row in rows]
        conn.close()
        
        if len(results) < 5:
            fuzzy_results = self._fuzzy_search_mafatih(query)
            existing_ids = {r["id"] for r in results}
            for item in fuzzy_results:
                if item["id"] not in existing_ids:
                    results.append(item)
        
        return results
    
    def _fuzzy_search_mafatih(self, query: str) -> List[Dict]:
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
            
            if best_score >= MIN_FUZZY_SCORE:
                scored.append((item_dict, best_score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored]
    
    def search_nahj_advanced(self, query: str) -> List[Dict]:
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
        """, (like, like, like, like, like)).fetchall()
        
        results = [dict(row) for row in rows]
        conn.close()
        
        if len(results) < 5:
            fuzzy_results = self._fuzzy_search_nahj(query)
            existing_ids = {r["id"] for r in results}
            for item in fuzzy_results:
                if item["id"] not in existing_ids:
                    results.append(item)
        
        return results
    
    def _fuzzy_search_nahj(self, query: str) -> List[Dict]:
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
            
            if best_score >= MIN_FUZZY_SCORE:
                scored.append((item_dict, best_score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored]
    
    def search_all(self, query: str) -> Dict[str, List]:
        """جستجو در همه بخش‌ها - بدون محدودیت"""
        return {
            "hadiths": self.search_hadiths_advanced(query),
            "mafatih": self.search_mafatih_advanced(query),
            "nahj": self.search_nahj_advanced(query),
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
        arabic = item.get('arabic_text', '')
        if arabic:
            text += f"📖 {arabic[:300]}\n\n"
        translation = item.get('translation_text', '')
        if translation:
            text += f"🔹 ترجمه: {translation[:300]}"
        if item.get("narrator"):
            text += f"\n👤 راوی: {item['narrator']}"
        if item.get("source_book"):
            text += f"\n📚 منبع: {item['source_book']}"
        if item.get("id"):
            text += f"\n🆔 شناسه: {item['id']}"
        
    elif category == "mafatih":
        text = f"{emoji} **{item.get('title', 'دعا')}**\n"
        arabic = item.get('arabic_text', '')
        if arabic:
            text += f"\n🌿 {arabic[:300]}"
        translation = item.get('translation_text', '')
        if translation:
            text += f"\n\n🔹 ترجمه: {translation[:300]}"
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
        arabic = item.get('arabic_text', '')
        if arabic:
            text += f"\n\n🌿 {arabic[:300]}"
        translation = item.get('translation_text', '')
        if translation:
            text += f"\n\n🔹 ترجمه: {translation[:300]}"
    
    return text


def generate_search_id(query: str) -> str:
    """تولید شناسه یکتا برای هر جستجو"""
    return hashlib.md5(f"{query}_{len(SEARCH_CACHE)}".encode()).hexdigest()[:8]


def get_search_keyboard(search_id: str, results: Dict, query: str) -> InlineKeyboardMarkup:
    """ساخت کیبورد با شناسه یکتا - بدون استفاده از query در callback"""
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
                    callback_data=f"scat_{search_id}_{category}_0"
                )
            ])
    
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
    
    # جستجو
    engine = get_search_engine()
    results = engine.search_all(query)
    
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
    
    # ذخیره نتایج با شناسه یکتا
    search_id = generate_search_id(query)
    SEARCH_CACHE[search_id] = {
        "results": results,
        "query": query
    }
    
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
        reply_markup=get_search_keyboard(search_id, results, query),
        parse_mode="Markdown"
    )


async def search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای کلیک روی نتایج جستجو - با استفاده از search_id"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    parts = data.split("_")
    
    if len(parts) < 4:
        return
    
    action = parts[0]
    
    if action == "scat":
        search_id = parts[1]
        category = parts[2]
        page = int(parts[3])
        
        # دریافت نتایج از کش
        cached = SEARCH_CACHE.get(search_id)
        if not cached:
            await query.edit_message_text("🔍 نتایج جستجو منقضی شده است. لطفاً دوباره جستجو کنید.")
            return
        
        items = cached["results"].get(category, [])
        search_query = cached["query"]
        
        if not items:
            await query.edit_message_text("نتیجه‌ای برای این دسته پیدا نشد.")
            return
        
        # نمایش همه نتایج در یک پیام (بدون صفحه‌بندی)
        text = f"🔍 **نتایج {get_category_emoji(category)}**\n"
        text += f"جستجو: «{search_query}»\n\n"
        
        # نمایش حداکثر ۲۰ مورد در هر پیام (محدودیت طول پیام تلگرام)
        items_per_page = 20
        start = page * items_per_page
        end = start + items_per_page
        page_items = items[start:end]
        
        for item in page_items:
            text += format_search_result(item, category) + "\n\n"
            text += "─" * 30 + "\n\n"
        
        # دکمه‌های صفحه‌بندی
        buttons = []
        nav_row = []
        total_pages = (len(items) + items_per_page - 1) // items_per_page
        
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                "◀️ قبلی",
                callback_data=f"scat_{search_id}_{category}_{page-1}"
            ))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(
                "بعدی ▶️",
                callback_data=f"scat_{search_id}_{category}_{page+1}"
            ))
        if nav_row:
            buttons.append(nav_row)
        
        # دکمه اطلاعات تعداد کل
        buttons.append([
            InlineKeyboardButton(
                f"📊 {len(items)} نتیجه - صفحه {page+1} از {total_pages}",
                callback_data="noop"
            )
        ])
        
        buttons.append([
            InlineKeyboardButton(
                "🔙 بازگشت به نتایج اصلی",
                callback_data=f"sback_{search_id}"
            )
        ])
        buttons.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_back")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
    
    elif action == "sback":
        search_id = parts[1]
        cached = SEARCH_CACHE.get(search_id)
        
        if not cached:
            await query.edit_message_text("🔍 نتایج جستجو منقضی شده است. لطفاً دوباره جستجو کنید.")
            return
        
        results = cached["results"]
        search_query = cached["query"]
        total_results = sum(len(items) for items in results.values())
        
        text = f"🔍 **نتایج جستجوی «{search_query}»**\n\n"
        text += f"📊 **{total_results}** نتیجه یافت شد:\n\n"
        
        for category, items in results.items():
            if items:
                label = {
                    "hadiths": "📿 احادیث",
                    "mafatih": "📗 مفاتیح",
                    "nahj": "🕌 نهج‌البلاغه",
                }.get(category, category)
                text += f"• {label}: {len(items)} مورد\n"
        
        await query.edit_message_text(
            text,
            reply_markup=get_search_keyboard(search_id, results, search_query),
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
    """هندلر جستجوی پیشرفته - با قابلیت نمایش همه نتایج"""
    await search_command(update, context, text)