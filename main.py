import re
import logging
import hashlib
from typing import List, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from thefuzz import fuzz, process
import sqlite3

from services.quran_api import get_ayah
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

MIN_FUZZY_SCORE = 25
SEARCH_CACHE = {}


class SmartSearch:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
    
    def search_hadiths(self, query: str) -> List[Dict]:
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
            ORDER BY id
        """, (like, like, like, like, like)).fetchall()
        
        results = [dict(row) for row in rows]
        conn.close()
        
        if len(results) < 5:
            fuzzy = self._fuzzy_search_hadiths(query)
            existing = {r["id"] for r in results}
            for item in fuzzy:
                if item["id"] not in existing:
                    results.append(item)
        
        return results
    
    def _fuzzy_search_hadiths(self, query: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        all_items = conn.execute("SELECT * FROM hadiths").fetchall()
        conn.close()
        
        q = query.lower()
        scored = []
        for item in all_items:
            item = dict(item)
            best = 0
            for field in ["translation_text", "arabic_text", "narrator", "source_book"]:
                if item.get(field):
                    score = fuzz.partial_ratio(q, item[field].lower())
                    if score > best:
                        best = score
            if best >= MIN_FUZZY_SCORE:
                scored.append((item, best))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored]
    
    def search_mafatih(self, query: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        like = f"%{query}%"
        
        rows = conn.execute("""
            SELECT * FROM mafatih 
            WHERE title LIKE ? 
            OR arabic_text LIKE ?
            OR translation_text LIKE ?
            ORDER BY id
        """, (like, like, like)).fetchall()
        
        results = [dict(row) for row in rows]
        conn.close()
        
        if len(results) < 5:
            fuzzy = self._fuzzy_search_mafatih(query)
            existing = {r["id"] for r in results}
            for item in fuzzy:
                if item["id"] not in existing:
                    results.append(item)
        
        return results
    
    def _fuzzy_search_mafatih(self, query: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        all_items = conn.execute("SELECT * FROM mafatih").fetchall()
        conn.close()
        
        q = query.lower()
        scored = []
        for item in all_items:
            item = dict(item)
            best = 0
            for field in ["title", "translation_text", "arabic_text"]:
                if item.get(field):
                    score = fuzz.partial_ratio(q, item[field].lower())
                    if score > best:
                        best = score
            if best >= MIN_FUZZY_SCORE:
                scored.append((item, best))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored]
    
    def search_nahj(self, query: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        like = f"%{query}%"
        
        rows = conn.execute("""
            SELECT * FROM nahj_balagha 
            WHERE title LIKE ? 
            OR arabic_text LIKE ?
            OR translation_text LIKE ?
            ORDER BY id
        """, (like, like, like)).fetchall()
        
        results = [dict(row) for row in rows]
        conn.close()
        
        if len(results) < 5:
            fuzzy = self._fuzzy_search_nahj(query)
            existing = {r["id"] for r in results}
            for item in fuzzy:
                if item["id"] not in existing:
                    results.append(item)
        
        return results
    
    def _fuzzy_search_nahj(self, query: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        all_items = conn.execute("SELECT * FROM nahj_balagha").fetchall()
        conn.close()
        
        q = query.lower()
        scored = []
        for item in all_items:
            item = dict(item)
            best = 0
            for field in ["title", "translation_text", "arabic_text"]:
                if item.get(field):
                    score = fuzz.partial_ratio(q, item[field].lower())
                    if score > best:
                        best = score
            if best >= MIN_FUZZY_SCORE:
                scored.append((item, best))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored]
    
    def search_all(self, query: str) -> Dict:
        return {
            "hadiths": self.search_hadiths(query),
            "mafatih": self.search_mafatih(query),
            "nahj": self.search_nahj(query),
        }


_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = SmartSearch()
    return _engine


def make_id(query: str) -> str:
    return hashlib.md5(f"{query}".encode()).hexdigest()[:6]


def fmt_item(item: Dict, cat: str) -> str:
    emojis = {"hadiths": "📿", "mafatih": "📗", "nahj": "🕌"}
    emoji = emojis.get(cat, "🔍")
    
    if cat == "hadiths":
        text = f"{emoji} **حدیث**\n"
        if item.get("arabic_text"):
            text += f"📖 {item['arabic_text'][:250]}\n\n"
        if item.get("translation_text"):
            text += f"🔹 {item['translation_text'][:250]}"
        if item.get("narrator"):
            text += f"\n👤 {item['narrator']}"
        if item.get("source_book"):
            text += f"\n📚 {item['source_book']}"
        text += f"\n🆔 {item['id']}"
        return text
    
    elif cat == "mafatih":
        text = f"{emoji} **{item.get('title', 'دعا')}**\n"
        if item.get("arabic_text"):
            text += f"\n🌿 {item['arabic_text'][:250]}"
        if item.get("translation_text"):
            text += f"\n\n🔹 {item['translation_text'][:250]}"
        return text
    
    else:
        cat_name = {"khutbah": "خطبه", "letter": "نامه", "hekmat": "حکمت"}.get(
            item.get("category", ""), ""
        )
        text = f"{emoji} **{cat_name} {item.get('number', '')}**"
        if item.get("title"):
            text += f"\n📌 {item['title']}"
        if item.get("arabic_text"):
            text += f"\n\n🌿 {item['arabic_text'][:250]}"
        if item.get("translation_text"):
            text += f"\n\n🔹 {item['translation_text'][:250]}"
        return text


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str = None):
    if query is None:
        await update.message.reply_text(
            "🔍 **جستجوی هوشمند**\n\n"
            "عبارت مورد نظر را وارد کنید.\n"
            "مثال: `صبر` یا `توحید` یا `2:255`\n\n"
            "📿 احادیث\n📗 مفاتیح\n🕌 نهج‌البلاغه",
            parse_mode="Markdown"
        )
        return
    
    if ":" in query and query.replace(":", "").isdigit():
        try:
            s, a = query.split(":")
            data = await get_ayah(int(s), int(a))
            if data:
                text = f"📖 **سوره {s} - آیه {a}**\n\n{data['arabic']}\n\n🔹 {data['translation']}"
                await update.message.reply_text(text, parse_mode="Markdown")
                return
        except:
            pass
    
    engine = get_engine()
    results = engine.search_all(query)
    
    total = sum(len(x) for x in results.values())
    if total == 0:
        await update.message.reply_text(f"🔍 نتیجه‌ای برای «{query}» پیدا نشد.")
        return
    
    sid = make_id(query)
    SEARCH_CACHE[sid] = results
    
    text = f"🔍 **نتایج «{query}»**\n📊 {total} مورد:\n\n"
    for cat, items in results.items():
        if items:
            label = {"hadiths": "📿 احادیث", "mafatih": "📗 مفاتیح", "nahj": "🕌 نهج"}.get(cat, cat)
            text += f"• {label}: {len(items)}\n"
    
    buttons = []
    for cat, items in results.items():
        if items:
            label = {"hadiths": "📿 احادیث", "mafatih": "📗 مفاتیح", "nahj": "🕌 نهج"}.get(cat, cat)
            buttons.append([InlineKeyboardButton(
                f"{label} ({len(items)})",
                callback_data=f"s_{sid}_{cat}_0"
            )])
    
    buttons.append([InlineKeyboardButton("🏠 منو", callback_data="menu_back")])
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    data = q.data
    parts = data.split("_")
    
    if len(parts) < 4:
        return
    
    sid = parts[1]
    cat = parts[2]
    page = int(parts[3])
    
    results = SEARCH_CACHE.get(sid)
    if not results:
        await q.edit_message_text("🔍 نتایج منقضی شد. دوباره جستجو کنید.")
        return
    
    items = results.get(cat, [])
    if not items:
        await q.edit_message_text("موردی یافت نشد.")
        return
    
    per_page = 15
    start = page * per_page
    end = start + per_page
    page_items = items[start:end]
    
    text = f"🔍 **نتایج {cat}**\n\n"
    for item in page_items:
        text += fmt_item(item, cat) + "\n\n" + "─" * 25 + "\n\n"
    
    buttons = []
    nav = []
    total_pages = (len(items) + per_page - 1) // per_page
    
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"s_{sid}_{cat}_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"s_{sid}_{cat}_{page+1}"))
    if nav:
        buttons.append(nav)
    
    buttons.append([InlineKeyboardButton("🔙 برگشت", callback_data=f"sb_{sid}")])
    buttons.append([InlineKeyboardButton("🏠 منو", callback_data="menu_back")])
    
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    sid = q.data.split("_")[1]
    results = SEARCH_CACHE.get(sid)
    
    if not results:
        await q.edit_message_text("🔍 نتایج منقضی شد.")
        return
    
    total = sum(len(x) for x in results.values())
    text = f"🔍 **نتایج جستجو**\n📊 {total} مورد:\n\n"
    for cat, items in results.items():
        if items:
            label = {"hadiths": "📿 احادیث", "mafatih": "📗 مفاتیح", "nahj": "🕌 نهج"}.get(cat, cat)
            text += f"• {label}: {len(items)}\n"
    
    buttons = []
    for cat, items in results.items():
        if items:
            label = {"hadiths": "📿 احادیث", "mafatih": "📗 مفاتیح", "nahj": "🕌 نهج"}.get(cat, cat)
            buttons.append([InlineKeyboardButton(
                f"{label} ({len(items)})",
                callback_data=f"s_{sid}_{cat}_0"
            )])
    
    buttons.append([InlineKeyboardButton("🏠 منو", callback_data="menu_back")])
    
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def enhanced_text_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    await search_command(update, context, text)