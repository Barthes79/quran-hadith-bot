import hashlib
import sqlite3
import re
from typing import List, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import DATABASE_PATH


class SmartSearch:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
    
    def _highlight_text(self, text: str, keyword: str) -> str:
        if not text or not keyword:
            return text
        
        keywords = keyword.split()
        result = text
        for kw in keywords:
            if len(kw) < 2:
                continue
            pattern = re.compile(re.escape(kw), re.IGNORECASE)
            result = pattern.sub(lambda m: f"**{m.group(0)}**", result)
        
        return result
    
    def _get_snippet(self, text: str, keyword: str, length: int = 150) -> str:
        if not text:
            return ""
        
        keyword_lower = keyword.lower()
        text_lower = text.lower()
        
        pos = text_lower.find(keyword_lower)
        if pos == -1:
            snippet = text[:length]
            if len(text) > length:
                snippet += "..."
            return self._highlight_text(snippet, keyword)
        
        start = max(0, pos - 50)
        end = min(len(text), pos + len(keyword) + 50)
        
        while start > 0 and text[start] not in ".،\n":
            start -= 1
        if start > 0:
            start += 1
        
        while end < len(text) and text[end] not in ".،\n":
            end += 1
        
        snippet = text[start:end].strip()
        if len(snippet) < len(text):
            snippet += "..."
        
        return self._highlight_text(snippet, keyword)
    
    def search_hadiths(self, q: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        like = f"%{q}%"
        
        rows = conn.execute("""
            SELECT * FROM hadiths 
            WHERE translation_text LIKE ? 
            OR arabic_text LIKE ? 
            ORDER BY id
        """, (like, like)).fetchall()
        
        results = []
        for row in rows:
            item = dict(row)
            if item.get("translation_text"):
                item["snippet"] = self._get_snippet(item["translation_text"], q)
            elif item.get("arabic_text"):
                item["snippet"] = self._get_snippet(item["arabic_text"], q)
            else:
                item["snippet"] = "متن موجود نیست"
            
            addr = ""
            if item.get("source_book"):
                addr += f"📚 {item['source_book']}"
            if item.get("narrator"):
                addr += f" 👤 {item['narrator']}"
            item["address"] = addr or "حدیث"
            results.append(item)
        
        conn.close()
        return results
    
    def search_mafatih(self, q: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        like = f"%{q}%"
        
        rows = conn.execute("""
            SELECT * FROM mafatih 
            WHERE title LIKE ? 
            OR translation_text LIKE ? 
            ORDER BY id
        """, (like, like)).fetchall()
        
        results = []
        for row in rows:
            item = dict(row)
            if item.get("translation_text"):
                item["snippet"] = self._get_snippet(item["translation_text"], q)
            elif item.get("title"):
                item["snippet"] = self._highlight_text(item["title"], q)
            else:
                item["snippet"] = "متن موجود نیست"
            
            cat_names = {
                "daily": "اعمال روزانه",
                "weekly": "اعمال هفتگی", 
                "monthly": "اعمال ماهانه",
                "ziyarat": "زیارات",
                "munajat": "مناجات",
                "special": "اعمال ویژه"
            }
            category = cat_names.get(item.get("category", ""), item.get("category", ""))
            item["address"] = f"📂 {category}"
            results.append(item)
        
        conn.close()
        return results
    
    def search_nahj(self, q: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        like = f"%{q}%"
        
        rows = conn.execute("""
            SELECT * FROM nahj_balagha 
            WHERE translation_text LIKE ? 
            ORDER BY category, number
        """, (like,)).fetchall()
        
        results = []
        for row in rows:
            item = dict(row)
            if item.get("translation_text"):
                item["snippet"] = self._get_snippet(item["translation_text"], q)
            else:
                item["snippet"] = "متن موجود نیست"
            
            cat_name = {
                "khutbah": "خطبه",
                "letter": "نامه",
                "hekmat": "حکمت"
            }.get(item.get("category", ""), "")
            item["address"] = f"🕌 {cat_name} {item.get('number', '')}"
            results.append(item)
        
        conn.close()
        return results
    
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


def format_summary(item: Dict, cat: str, idx: int) -> str:
    emojis = {"hadiths": "📿", "mafatih": "📗", "nahj": "🕌"}
    emoji = emojis.get(cat, "🔍")
    
    if cat == "hadiths":
        text = f"{emoji} **حدیث {idx}**\n"
        if item.get("snippet"):
            text += f"📝 {item['snippet']}\n"
        if item.get("address"):
            text += f"📍 {item['address']}"
        return text
    
    elif cat == "mafatih":
        title = item.get("title", "دعا")
        text = f"{emoji} **{title}**\n"
        if item.get("snippet"):
            text += f"📝 {item['snippet']}\n"
        if item.get("address"):
            text += f"📍 {item['address']}"
        return text
    
    else:
        text = f"{emoji} **{item.get('address', 'نهج‌البلاغه')}**\n"
        if item.get("snippet"):
            text += f"📝 {item['snippet']}"
        return text


def format_full(item: Dict, cat: str) -> str:
    if cat == "hadiths":
        text = "📿 **متن کامل حدیث**\n\n"
        if item.get("arabic_text"):
            text += f"🌿 {item['arabic_text']}\n\n"
        if item.get("translation_text"):
            text += f"🔹 {item['translation_text']}\n"
        if item.get("address"):
            text += f"\n📍 {item['address']}"
        return text
    
    elif cat == "mafatih":
        text = f"📗 **{item.get('title', 'دعا')}**\n\n"
        if item.get("arabic_text"):
            text += f"🌿 {item['arabic_text']}\n\n"
        if item.get("translation_text"):
            text += f"🔹 {item['translation_text']}\n"
        if item.get("address"):
            text += f"\n📍 {item['address']}"
        return text
    
    else:
        cat_name = {
            "khutbah": "خطبه",
            "letter": "نامه",
            "hekmat": "حکمت"
        }.get(item.get("category", ""), "")
        text = f"🕌 **{cat_name} {item.get('number', '')}**\n\n"
        if item.get("arabic_text"):
            text += f"🌿 {item['arabic_text']}\n\n"
        if item.get("translation_text"):
            text += f"🔹 {item['translation_text']}\n"
        return text


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str = None):
    if query is None:
        await update.message.reply_text(
            "🔍 **جستجو**\n\nعبارت مورد نظر را وارد کنید.\nمثال: `خدا` یا `توحید`"
        )
        return
    
    engine = get_engine()
    results = engine.search_all(query)
    
    total = sum(len(x) for x in results.values())
    if total == 0:
        await update.message.reply_text(f"🔍 نتیجه‌ای برای «{query}» پیدا نشد.")
        return
    
    sid = make_id(query)
    context.user_data["search_results"] = results
    
    text = f"🔍 **نتایج «{query}»**  ({total} مورد)\n\n"
    buttons = []
    
    for cat, items in results.items():
        if items:
            label = {"hadiths": "📿 احادیث", "mafatih": "📗 مفاتیح", "nahj": "🕌 نهج‌البلاغه"}.get(cat, cat)
            text += f"• {label}: {len(items)} مورد\n"
            buttons.append([InlineKeyboardButton(
                f"{label} ({len(items)})",
                callback_data=f"s_{sid}_{cat}_0"
            )])
    
    buttons.append([InlineKeyboardButton("🏠 منو", callback_data="menu_back")])
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    parts = q.data.split("_")
    if len(parts) < 4:
        return
    
    sid, cat, page = parts[1], parts[2], int(parts[3])
    
    results = context.user_data.get("search_results")
    if not results:
        await q.edit_message_text("🔍 نتایج منقضی شد. دوباره جستجو کنید.")
        return
    
    items = results.get(cat, [])
    if not items:
        await q.edit_message_text("موردی یافت نشد.")
        return
    
    per_page = 5
    start = page * per_page
    page_items = items[start:start + per_page]
    total_pages = (len(items) + per_page - 1) // per_page
    
    label = {"hadiths": "احادیث", "mafatih": "مفاتیح", "nahj": "نهج‌البلاغه"}.get(cat, cat)
    text = f"🔍 **{label}** (صفحه {page+1} از {total_pages})\n\n"
    
    buttons = []
    for i, item in enumerate(page_items, 1):
        idx = start + i - 1
        item_key = f"{sid}_{cat}_{idx}"
        context.user_data[f"item_{item_key}"] = {"item": item, "cat": cat}
        
        text += format_summary(item, cat, i) + "\n"
        text += "─" * 25 + "\n"
        buttons.append([
            InlineKeyboardButton(
                f"📖 مشاهده کامل {i}",
                callback_data=f"view_{item_key}"
            )
        ])
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"s_{sid}_{cat}_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"s_{sid}_{cat}_{page+1}"))
    if nav:
        buttons.append(nav)
    
    buttons.append([InlineKeyboardButton("🔙 برگشت", callback_data=f"sb_{sid}")])
    buttons.append([InlineKeyboardButton("🏠 منو", callback_data="menu_back")])
    
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def view_full_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    item_key = q.data.replace("view_", "")
    cached = context.user_data.get(f"item_{item_key}")
    
    if not cached:
        await q.message.reply_text("🔍 این مورد منقضی شده است.")
        return
    
    item = cached["item"]
    cat = cached["cat"]
    
    full_text = format_full(item, cat)
    
    sid = item_key.split("_")[0]
    buttons = [[
        InlineKeyboardButton("🔙 بازگشت", callback_data=f"sb_{sid}")
    ]]
    
    await q.message.reply_text(full_text, reply_markup=InlineKeyboardMarkup(buttons))


async def back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    sid = q.data.split("_")[1]
    results = context.user_data.get("search_results")
    
    if not results:
        await q.edit_message_text("🔍 نتایج منقضی شد.")
        return
    
    total = sum(len(x) for x in results.values())
    text = f"🔍 **نتایج جستجو**  ({total} مورد)\n\n"
    buttons = []
    
    for cat, items in results.items():
        if items:
            label = {"hadiths": "📿 احادیث", "mafatih": "📗 مفاتیح", "nahj": "🕌 نهج‌البلاغه"}.get(cat, cat)
            text += f"• {label}: {len(items)} مورد\n"
            buttons.append([InlineKeyboardButton(
                f"{label} ({len(items)})",
                callback_data=f"s_{sid}_{cat}_0"
            )])
    
    buttons.append([InlineKeyboardButton("🏠 منو", callback_data="menu_back")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def enhanced_text_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """فقط برای چت خصوصی"""
    await search_command(update, context, text)