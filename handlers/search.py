import hashlib
import sqlite3
import re
from typing import List, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from thefuzz import fuzz

from config import DATABASE_PATH

SEARCH_CACHE = {}
MIN_FUZZY_SCORE = 60  # افزایش آستانه فازی برای دقت بیشتر


class SmartSearch:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
    
    def _get_context(self, text: str, keyword: str, context_chars: int = 60) -> str:
        if not text:
            return ""
        
        keyword_lower = keyword.lower()
        text_lower = text.lower()
        
        # پیدا کردن موقعیت کلمه
        pos = text_lower.find(keyword_lower)
        if pos == -1:
            # اگر کلمه دقیقاً پیدا نشد، تک تک کلمات رو بررسی کن
            for word in keyword.split():
                if len(word) > 2:
                    pos = text_lower.find(word.lower())
                    if pos != -1:
                        break
        
        if pos == -1:
            # اگر هیچ‌کدام پیدا نشد، ۲۰۰ کاراکتر اول رو برگردون
            return text[:200] + "..."
        
        # پیدا کردن شروع و پایان
        start = max(0, pos - 60)
        end = min(len(text), pos + len(keyword) + 60)
        
        # پیدا کردن مرز جمله
        while start > 0 and text[start] not in ".،\n":
            start -= 1
        if start > 0:
            start += 1
        
        while end < len(text) and text[end] not in ".،\n":
            end += 1
        
        snippet = text[start:end].strip()
        return snippet
    
    def _exact_search(self, cursor, table: str, fields: List[str], keyword: str) -> List[Dict]:
        """جستجوی دقیق کلمه در فیلدها"""
        conditions = []
        params = []
        for field in fields:
            conditions.append(f"{field} LIKE ?")
            params.append(f"%{keyword}%")
        
        # همچنین جستجوی کلمات جداگانه
        words = keyword.split()
        if len(words) > 1:
            for word in words:
                if len(word) > 2:
                    for field in fields:
                        conditions.append(f"{field} LIKE ?")
                        params.append(f"%{word}%")
        
        query = f"SELECT * FROM {table} WHERE " + " OR ".join(conditions) + " ORDER BY id"
        rows = cursor.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    
    def search_hadiths(self, q: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # ۱. جستجوی دقیق
        results = self._exact_search(
            conn, "hadiths", 
            ["translation_text", "arabic_text", "tafsir_text", "narrator", "source_book"], 
            q
        )
        
        # ۲. اگر نتیجه کم بود، جستجوی فازی با آستانه بالا
        if len(results) < 3:
            fuzzy_results = self._fuzzy_search_hadiths(q)
            existing = {r["id"] for r in results}
            for item in fuzzy_results:
                if item["id"] not in existing:
                    results.append(item)
        
        conn.close()
        
        # اضافه کردن snippet و آدرس
        for item in results:
            if item.get("translation_text"):
                item["snippet"] = self._get_context(item["translation_text"], q)
            elif item.get("arabic_text"):
                item["snippet"] = self._get_context(item["arabic_text"], q)
            else:
                item["snippet"] = "متن موجود نیست"
            
            address = ""
            if item.get("source_book"):
                address += f"📚 {item['source_book']}"
            if item.get("chapter"):
                address += f" - باب {item['chapter']}"
            if item.get("hadith_number"):
                address += f" - حدیث {item['hadith_number']}"
            if item.get("narrator"):
                address += f"\n👤 راوی: {item['narrator']}"
            item["address"] = address or "حدیث"
        
        return results
    
    def _fuzzy_search_hadiths(self, q: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        all_items = conn.execute("SELECT * FROM hadiths").fetchall()
        conn.close()
        
        q_lower = q.lower()
        scored = []
        for item in all_items:
            item = dict(item)
            best = 0
            # بررسی در فیلدهای مختلف
            for field in ["translation_text", "arabic_text", "narrator", "source_book"]:
                if item.get(field):
                    score = fuzz.partial_ratio(q_lower, item[field].lower())
                    if score > best:
                        best = score
            # فقط نتایج با امتیاز بالا
            if best >= MIN_FUZZY_SCORE:
                scored.append((item, best))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored[:20]]  # حداکثر ۲۰ نتیجه فازی
    
    def search_mafatih(self, q: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        results = self._exact_search(
            conn, "mafatih",
            ["title", "arabic_text", "translation_text", "tafsir_text", "category"],
            q
        )
        
        if len(results) < 3:
            fuzzy_results = self._fuzzy_search_mafatih(q)
            existing = {r.get("id", i) for i, r in enumerate(results, 1)}
            for item in fuzzy_results:
                if item.get("id") not in existing:
                    results.append(item)
        
        conn.close()
        
        for item in results:
            snippet = ""
            if item.get("translation_text"):
                snippet = self._get_context(item["translation_text"], q)
            elif item.get("arabic_text"):
                snippet = self._get_context(item["arabic_text"], q)
            elif item.get("title"):
                snippet = f"📗 {item['title']}"
            
            if not snippet:
                snippet = item.get("title", "دعا")
            
            item["snippet"] = snippet
            
            cat_names = {
                "daily": "اعمال روزانه",
                "weekly": "اعمال هفتگی", 
                "monthly": "اعمال ماهانه",
                "ziyarat": "زیارات",
                "munajat": "مناجات",
                "special": "اعمال ویژه"
            }
            category = cat_names.get(item.get("category", ""), item.get("category", ""))
            item["address"] = f"📂 {category} - {item.get('title', 'دعا')}"
        
        return results
    
    def _fuzzy_search_mafatih(self, q: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        all_items = conn.execute("SELECT * FROM mafatih").fetchall()
        conn.close()
        
        q_lower = q.lower()
        scored = []
        for item in all_items:
            item = dict(item)
            best = 0
            for field in ["title", "translation_text", "arabic_text"]:
                if item.get(field):
                    score = fuzz.partial_ratio(q_lower, item[field].lower())
                    if score > best:
                        best = score
            if best >= MIN_FUZZY_SCORE:
                scored.append((item, best))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored[:20]]
    
    def search_nahj(self, q: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        results = self._exact_search(
            conn, "nahj_balagha",
            ["title", "arabic_text", "translation_text", "tafsir_text", "category"],
            q
        )
        
        if len(results) < 3:
            fuzzy_results = self._fuzzy_search_nahj(q)
            existing = {r["id"] for r in results}
            for item in fuzzy_results:
                if item["id"] not in existing:
                    results.append(item)
        
        conn.close()
        
        for item in results:
            snippet = ""
            if item.get("translation_text"):
                snippet = self._get_context(item["translation_text"], q)
            elif item.get("arabic_text"):
                snippet = self._get_context(item["arabic_text"], q)
            elif item.get("title"):
                snippet = f"📌 {item['title']}"
            
            if not snippet:
                snippet = "متن موجود نیست"
            
            item["snippet"] = snippet
            
            cat_name = {
                "khutbah": "خطبه",
                "letter": "نامه",
                "hekmat": "حکمت"
            }.get(item.get("category", ""), "")
            
            address = f"🕌 {cat_name} {item.get('number', '')}"
            if item.get("title"):
                address += f" - {item['title']}"
            item["address"] = address
        
        return results
    
    def _fuzzy_search_nahj(self, q: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        all_items = conn.execute("SELECT * FROM nahj_balagha").fetchall()
        conn.close()
        
        q_lower = q.lower()
        scored = []
        for item in all_items:
            item = dict(item)
            best = 0
            for field in ["title", "translation_text", "arabic_text"]:
                if item.get(field):
                    score = fuzz.partial_ratio(q_lower, item[field].lower())
                    if score > best:
                        best = score
            if best >= MIN_FUZZY_SCORE:
                scored.append((item, best))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored[:20]]
    
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


def format_result_summary(item: Dict, cat: str, index: int) -> str:
    emojis = {"hadiths": "📿", "mafatih": "📗", "nahj": "🕌"}
    emoji = emojis.get(cat, "🔍")
    
    if cat == "hadiths":
        text = f"{emoji} **حدیث {index}**\n"
        if item.get("snippet"):
            text += f"📝 {item['snippet']}\n"
        if item.get("address"):
            text += f"📍 {item['address']}\n"
        return text
    
    elif cat == "mafatih":
        text = f"{emoji} **{item.get('title', 'دعا')}**\n"
        if item.get("snippet"):
            text += f"📝 {item['snippet']}\n"
        if item.get("address"):
            text += f"📍 {item['address']}\n"
        return text
    
    else:
        text = f"{emoji} **{item.get('address', 'نهج‌البلاغه')}**\n"
        if item.get("snippet"):
            text += f"📝 {item['snippet']}\n"
        return text


def format_full_item(item: Dict, cat: str) -> str:
    if cat == "hadiths":
        text = "📿 **متن کامل حدیث**\n\n"
        if item.get("arabic_text"):
            text += f"🌿 {item['arabic_text']}\n\n"
        if item.get("translation_text"):
            text += f"🔹 {item['translation_text']}\n\n"
        if item.get("tafsir_text"):
            text += f"📝 شرح: {item['tafsir_text']}\n\n"
        if item.get("address"):
            text += f"📍 {item['address']}"
        return text
    
    elif cat == "mafatih":
        text = f"📗 **{item.get('title', 'دعا')}**\n\n"
        if item.get("arabic_text"):
            text += f"🌿 {item['arabic_text']}\n\n"
        if item.get("translation_text"):
            text += f"🔹 {item['translation_text']}\n\n"
        if item.get("tafsir_text"):
            text += f"📝 شرح: {item['tafsir_text']}\n\n"
        if item.get("address"):
            text += f"📍 {item['address']}"
        return text
    
    else:
        cat_name = {
            "khutbah": "خطبه",
            "letter": "نامه",
            "hekmat": "حکمت"
        }.get(item.get("category", ""), "")
        text = f"🕌 **{cat_name} {item.get('number', '')}**\n\n"
        if item.get("title"):
            text += f"📌 {item['title']}\n\n"
        if item.get("arabic_text"):
            text += f"🌿 {item['arabic_text']}\n\n"
        if item.get("translation_text"):
            text += f"🔹 {item['translation_text']}\n\n"
        if item.get("tafsir_text"):
            text += f"📝 شرح: {item['tafsir_text']}\n\n"
        return text


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str = None):
    if query is None:
        await update.message.reply_text(
            "🔍 **جستجوی هوشمند**\n\n"
            "عبارت مورد نظر را وارد کنید.\n"
            "مثال: `خدا` یا `توحید` یا `2:255`\n\n"
            "📿 احادیث\n📗 مفاتیح\n🕌 نهج‌البلاغه",
            parse_mode="Markdown"
        )
        return
    
    if ":" in query and query.replace(":", "").isdigit():
        try:
            from services.quran_api import get_ayah
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
    
    text = f"🔍 **نتایج جستجوی «{query}»**\n"
    text += f"📊 **{total}** نتیجه یافت شد:\n\n"
    
    buttons = []
    for cat, items in results.items():
        if items:
            label = {"hadiths": "📿 احادیث", "mafatih": "📗 مفاتیح", "nahj": "🕌 نهج‌البلاغه"}.get(cat, cat)
            text += f"• {label}: {len(items)} مورد\n"
            buttons.append([InlineKeyboardButton(
                f"{label} ({len(items)})",
                callback_data=f"s_{sid}_{cat}_0"
            )])
    
    buttons.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_back")])
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


async def search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    parts = q.data.split("_")
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
    
    per_page = 5
    start = page * per_page
    end = start + per_page
    page_items = items[start:end]
    total_pages = (len(items) + per_page - 1) // per_page
    
    label = {"hadiths": "احادیث", "mafatih": "مفاتیح", "nahj": "نهج‌البلاغه"}.get(cat, cat)
    text = f"🔍 **نتایج {label}** (صفحه {page+1} از {total_pages})\n"
    text += f"📊 {len(items)} مورد یافت شد\n\n"
    
    buttons = []
    for i, item in enumerate(page_items, 1):
        item_key = f"{sid}_{cat}_{start + i - 1}"
        SEARCH_CACHE[item_key] = {"item": item, "cat": cat}
        
        text += format_result_summary(item, cat, i) + "\n"
        buttons.append([
            InlineKeyboardButton(
                f"📖 مشاهده کامل {i}",
                callback_data=f"vi_{item_key}"
            )
        ])
        text += "─" * 30 + "\n"
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"s_{sid}_{cat}_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"s_{sid}_{cat}_{page+1}"))
    if nav:
        buttons.append(nav)
    
    buttons.append([InlineKeyboardButton("🔙 بازگشت به دسته‌ها", callback_data=f"sb_{sid}")])
    buttons.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_back")])
    
    await q.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=None
    )


async def view_full_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    item_key = q.data.replace("vi_", "")
    
    cached = SEARCH_CACHE.get(item_key)
    if not cached:
        await q.edit_message_text(
            "🔍 محتوای این مورد منقضی شده است.\nلطفاً دوباره جستجو کنید.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 جستجوی مجدد", callback_data="menu_search")
            ]]),
            parse_mode=None
        )
        return
    
    item = cached["item"]
    cat = cached["cat"]
    
    text = format_full_item(item, cat)
    
    sid = item_key.split("_")[0]
    buttons = [[
        InlineKeyboardButton("🔙 بازگشت به نتایج", callback_data=f"sb_{sid}")
    ]]
    
    if len(text) > 4000:
        parts_text = []
        current = ""
        for line in text.split("\n"):
            if len(current) + len(line) > 3500:
                parts_text.append(current)
                current = line + "\n"
            else:
                current += line + "\n"
        if current:
            parts_text.append(current)
        
        await q.edit_message_text(
            parts_text[0][:4000],
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=None
        )
        for part in parts_text[1:]:
            await q.message.reply_text(part[:4000], parse_mode=None)
    else:
        await q.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=None
        )


async def back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    sid = q.data.split("_")[1]
    results = SEARCH_CACHE.get(sid)
    
    if not results:
        await q.edit_message_text("🔍 نتایج منقضی شد. دوباره جستجو کنید.")
        return
    
    total = sum(len(x) for x in results.values())
    text = f"🔍 **نتایج جستجو**\n📊 {total} مورد:\n\n"
    buttons = []
    
    for cat, items in results.items():
        if items:
            label = {"hadiths": "📿 احادیث", "mafatih": "📗 مفاتیح", "nahj": "🕌 نهج‌البلاغه"}.get(cat, cat)
            text += f"• {label}: {len(items)}\n"
            buttons.append([InlineKeyboardButton(
                f"{label} ({len(items)})",
                callback_data=f"s_{sid}_{cat}_0"
            )])
    
    buttons.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_back")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=None)


async def enhanced_text_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    await search_command(update, context, text)