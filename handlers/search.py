import hashlib
import sqlite3
from typing import List, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from thefuzz import fuzz

from config import DATABASE_PATH

SEARCH_CACHE = {}
MIN_SCORE = 25


class SmartSearch:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
    
    def search_hadiths(self, q: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        like = f"%{q}%"
        rows = conn.execute("""
            SELECT * FROM hadiths 
            WHERE translation_text LIKE ? OR arabic_text LIKE ? OR narrator LIKE ? OR source_book LIKE ?
        """, (like, like, like, like)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    
    def search_mafatih(self, q: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        like = f"%{q}%"
        rows = conn.execute("""
            SELECT * FROM mafatih 
            WHERE title LIKE ? OR arabic_text LIKE ? OR translation_text LIKE ?
        """, (like, like, like)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    
    def search_nahj(self, q: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        like = f"%{q}%"
        rows = conn.execute("""
            SELECT * FROM nahj_balagha 
            WHERE title LIKE ? OR arabic_text LIKE ? OR translation_text LIKE ?
        """, (like, like, like)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    
    def search_all(self, q: str) -> Dict:
        return {
            "hadiths": self.search_hadiths(q),
            "mafatih": self.search_mafatih(q),
            "nahj": self.search_nahj(q),
        }


_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = SmartSearch()
    return _engine


def make_id(q: str) -> str:
    return hashlib.md5(q.encode()).hexdigest()[:6]


def fmt_item(item: Dict, cat: str) -> str:
    if cat == "hadiths":
        text = "📿 **حدیث**\n"
        if item.get("arabic_text"):
            text += f"📖 {item['arabic_text'][:200]}\n\n"
        if item.get("translation_text"):
            text += f"🔹 {item['translation_text'][:200]}"
        if item.get("narrator"):
            text += f"\n👤 {item['narrator']}"
        if item.get("source_book"):
            text += f"\n📚 {item['source_book']}"
        return text
    
    elif cat == "mafatih":
        text = f"📗 **{item.get('title', 'دعا')}**\n"
        if item.get("arabic_text"):
            text += f"\n🌿 {item['arabic_text'][:200]}"
        if item.get("translation_text"):
            text += f"\n\n🔹 {item['translation_text'][:200]}"
        return text
    
    else:  # nahj
        cat_name = {"khutbah": "خطبه", "letter": "نامه", "hekmat": "حکمت"}.get(item.get("category", ""), "")
        text = f"🕌 **{cat_name} {item.get('number', '')}**"
        if item.get("title"):
            text += f"\n📌 {item['title']}"
        if item.get("arabic_text"):
            text += f"\n\n🌿 {item['arabic_text'][:200]}"
        if item.get("translation_text"):
            text += f"\n\n🔹 {item['translation_text'][:200]}"
        return text


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str = None):
    if query is None:
        await update.message.reply_text("🔍 عبارت مورد نظر را وارد کنید.")
        return
    
    engine = get_engine()
    results = engine.search_all(query)
    
    total = sum(len(x) for x in results.values())
    if total == 0:
        await update.message.reply_text(f"🔍 نتیجه‌ای برای «{query}» پیدا نشد.")
        return
    
    sid = make_id(query)
    SEARCH_CACHE[sid] = results
    
    text = f"🔍 **نتایج «{query}»**\n📊 {total} مورد:\n\n"
    buttons = []
    
    for cat, items in results.items():
        if items:
            label = {"hadiths": "📿 احادیث", "mafatih": "📗 مفاتیح", "nahj": "🕌 نهج"}.get(cat, cat)
            text += f"• {label}: {len(items)}\n"
            buttons.append([InlineKeyboardButton(
                f"{label} ({len(items)})",
                callback_data=f"s_{sid}_{cat}_0"
            )])
    
    buttons.append([InlineKeyboardButton("🏠 منو", callback_data="menu_back")])
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    parts = q.data.split("_")
    if len(parts) < 4:
        return
    
    sid, cat, page = parts[1], parts[2], int(parts[3])
    results = SEARCH_CACHE.get(sid)
    
    if not results:
        await q.edit_message_text("🔍 نتایج منقضی شد. دوباره جستجو کنید.")
        return
    
    items = results.get(cat, [])
    if not items:
        await q.edit_message_text("موردی یافت نشد.")
        return
    
    per_page = 10
    start = page * per_page
    page_items = items[start:start + per_page]
    
    text = f"🔍 **نتایج {cat}**\n\n"
    for item in page_items:
        text += fmt_item(item, cat) + "\n\n" + "─" * 20 + "\n\n"
    
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
    buttons = []
    
    for cat, items in results.items():
        if items:
            label = {"hadiths": "📿 احادیث", "mafatih": "📗 مفاتیح", "nahj": "🕌 نهج"}.get(cat, cat)
            text += f"• {label}: {len(items)}\n"
            buttons.append([InlineKeyboardButton(
                f"{label} ({len(items)})",
                callback_data=f"s_{sid}_{cat}_0"
            )])
    
    buttons.append([InlineKeyboardButton("🏠 منو", callback_data="menu_back")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def enhanced_text_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    await search_command(update, context, text)