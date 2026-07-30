import sqlite3
from config import DATABASE_PATH
from text_utils import normalize_for_search


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(cur, table: str, column: str, definition: str):
    """اگر ستون در جدول وجود نداشت، آن را اضافه می‌کند (برای دیتابیس‌های قدیمی)."""
    existing = {row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # کش آیات و ترجمه‌ها (برای اینکه هر بار به API بیرونی نزنیم)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quran_cache (
            surah INTEGER,
            ayah INTEGER,
            edition TEXT,
            text TEXT,
            PRIMARY KEY (surah, ayah, edition)
        )
    """)

    # جدول احادیث
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hadiths (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arabic_text TEXT NOT NULL,
            translation_text TEXT NOT NULL,
            tafsir_text TEXT,
            narrator TEXT,
            source_book TEXT,
            chapter TEXT,
            hadith_number TEXT
        )
    """)

    # موضوعات هر حدیث
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hadith_topics (
            hadith_id INTEGER,
            topic_name TEXT,
            FOREIGN KEY (hadith_id) REFERENCES hadiths(id)
        )
    """)

    # تنظیمات کاربران
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            preferred_translation TEXT DEFAULT 'makarem'
        )
    """)

    # علاقه‌مندی‌های کاربر
    cur.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER,
            item_type TEXT,
            item_ref TEXT,
            PRIMARY KEY (user_id, item_type, item_ref)
        )
    """)

    # تنظیمات گروه‌ها
    cur.execute("""
        CREATE TABLE IF NOT EXISTS group_settings (
            chat_id INTEGER PRIMARY KEY,
            daily_post_enabled INTEGER DEFAULT 0,
            daily_post_hour INTEGER DEFAULT 8,
            post_interval_hours INTEGER DEFAULT 1,
            preferred_translation TEXT DEFAULT 'makarem',
            content_hadith INTEGER DEFAULT 1,
            content_ayah INTEGER DEFAULT 1,
            content_nahj INTEGER DEFAULT 0,
            content_mafatih INTEGER DEFAULT 0,
            quiet_start_hour INTEGER DEFAULT -1,
            quiet_end_hour INTEGER DEFAULT -1,
            welcome_enabled INTEGER DEFAULT 0,
            welcome_text TEXT,
            delete_service_messages INTEGER DEFAULT 0,
            block_links INTEGER DEFAULT 0,
            multi_goal_enabled INTEGER DEFAULT 1
        )
    """)

    # سوالات مسابقه
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            difficulty TEXT DEFAULT 'medium'
        )
    """)
    _ensure_column(cur, "quiz_questions", "category", "TEXT DEFAULT 'general'")
    _ensure_column(cur, "quiz_questions", "difficulty", "TEXT DEFAULT 'medium'")

    # امتیاز کاربران در هر گروه
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quiz_scores (
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT,
            score INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )
    """)

    # آمار کلی هر کاربر
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quiz_user_stats (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            total_points INTEGER DEFAULT 0,
            total_correct INTEGER DEFAULT 0,
            total_answered INTEGER DEFAULT 0,
            current_streak INTEGER DEFAULT 0,
            best_streak INTEGER DEFAULT 0
        )
    """)

    # آمار عملکرد هر کاربر به تفکیک دسته‌بندی
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quiz_category_stats (
            user_id INTEGER,
            category TEXT,
            correct_count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, category)
        )
    """)

    # نشان‌های کسب‌شده‌ی کاربران
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quiz_badges (
            user_id INTEGER,
            badge_key TEXT,
            awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, badge_key)
        )
    """)

    # تفسیر آیات قرآن
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quran_tafsir (
            surah INTEGER,
            ayah INTEGER,
            tafsir_text TEXT NOT NULL,
            source TEXT,
            PRIMARY KEY (surah, ayah)
        )
    """)

    # نهج‌البلاغه
    cur.execute("""
        CREATE TABLE IF NOT EXISTS nahj_balagha (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            number INTEGER NOT NULL,
            title TEXT,
            arabic_text TEXT NOT NULL,
            translation_text TEXT NOT NULL,
            tafsir_text TEXT,
            UNIQUE(category, number)
        )
    """)

    # مفاتیح‌الجنان
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mafatih (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            arabic_text TEXT NOT NULL,
            translation_text TEXT,
            tafsir_text TEXT,
            image_path TEXT,
            slug TEXT,
            audio_file_id TEXT
        )
    """)

    # یادآور اذان
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prayer_reminders (
            user_id INTEGER PRIMARY KEY,
            city_code INTEGER DEFAULT 1,
            minutes_before INTEGER DEFAULT 10,
            remind_fajr INTEGER DEFAULT 0,
            remind_noon INTEGER DEFAULT 0,
            remind_maghrib INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 0,
            group_chat_id INTEGER,
            user_name TEXT
        )
    """)
    _ensure_column(cur, "prayer_reminders", "group_chat_id", "INTEGER")
    _ensure_column(cur, "prayer_reminders", "user_name", "TEXT")

    # صلوات‌شمار: تعداد صلواتِ هر کاربر در هر گروه
    cur.execute("""
        CREATE TABLE IF NOT EXISTS salavat_stats (
            chat_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )
    """)

    # ============================================================
    # جداول جدید برای ختم‌های چندگانه صلوات
    # ============================================================

    # جدول ختم‌های صلوات (چندین ختم همزمان)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS salavat_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            goal_count INTEGER NOT NULL,
            title TEXT NOT NULL,
            start_total INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            announced INTEGER DEFAULT 0,
            completed_at TIMESTAMP
        )
    """)

    # جدول مشارکت کاربران در ختم‌ها
    cur.execute("""
        CREATE TABLE IF NOT EXISTS salavat_contributions (
            goal_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            amount INTEGER DEFAULT 0,
            PRIMARY KEY (goal_id, user_id),
            FOREIGN KEY (goal_id) REFERENCES salavat_goals(id)
        )
    """)

    # جدول وضعیت پیام‌های تعاملی (برای حذف پنل‌ها)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS interactive_messages (
            chat_id INTEGER,
            message_id INTEGER,
            user_id INTEGER,
            goal_id INTEGER,
            message_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, message_id)
        )
    """)

    # ستون multi_goal_enabled برای گروه‌ها
    try:
        cur.execute("ALTER TABLE group_settings ADD COLUMN multi_goal_enabled INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    # ستون‌های قبلی برای سازگاری
    for _col_def in [
        "content_hadith INTEGER DEFAULT 1",
        "content_ayah INTEGER DEFAULT 1",
        "content_nahj INTEGER DEFAULT 0",
        "content_mafatih INTEGER DEFAULT 0",
        "quiet_start_hour INTEGER DEFAULT -1",
        "quiet_end_hour INTEGER DEFAULT -1",
        "welcome_enabled INTEGER DEFAULT 0",
        "welcome_text TEXT",
        "delete_service_messages INTEGER DEFAULT 0",
        "block_links INTEGER DEFAULT 0",
        "quiz_custom_time INTEGER",
        "quiz_buzzer_mode INTEGER DEFAULT 0",
        "quiz_buzzer_next_delay INTEGER DEFAULT 5",
    ]:
        try:
            cur.execute(f"ALTER TABLE group_settings ADD COLUMN {_col_def}")
        except sqlite3.OperationalError:
            pass

    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_mafatih_slug ON mafatih(slug)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_salavat_goals_chat_title ON salavat_goals(chat_id, title)")

    # موتور جستجوی یکپارچه
    cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
            source_type UNINDEXED,
            source_id UNINDEXED,
            content
        )
    """)

    conn.commit()
    conn.close()


# =====================================================================
# توابع مربوط به صلوات‌شمار با پشتیبانی از ختم‌های متعدد
# =====================================================================

def increment_salavat(chat_id: int, user_id: int, user_name: str, amount: int = 1):
    """
    `amount` واحد به صلوات‌های این کاربر در این گروه اضافه می‌کند
    و (تعداد شخصی کاربر، مجموع کل گروه) را برمی‌گرداند.
    """
    conn = get_connection()
    conn.execute(
        """INSERT INTO salavat_stats (chat_id, user_id, user_name, count)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(chat_id, user_id)
           DO UPDATE SET count = count + excluded.count, user_name = excluded.user_name""",
        (chat_id, user_id, user_name, amount),
    )
    conn.commit()

    user_count = conn.execute(
        "SELECT count FROM salavat_stats WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id),
    ).fetchone()["count"]

    chat_total = conn.execute(
        "SELECT COALESCE(SUM(count), 0) t FROM salavat_stats WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()["t"]

    conn.close()
    return user_count, chat_total


def get_salavat_chat_total(chat_id: int) -> int:
    conn = get_connection()
    total = conn.execute(
        "SELECT COALESCE(SUM(count), 0) t FROM salavat_stats WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()["t"]
    conn.close()
    return total


def get_salavat_top(chat_id: int, limit: int = 10):
    conn = get_connection()
    rows = conn.execute(
        """SELECT user_id, user_name, count FROM salavat_stats
           WHERE chat_id = ? ORDER BY count DESC LIMIT ?""",
        (chat_id, limit),
    ).fetchall()
    conn.close()
    return rows


# ============ توابع جدید برای ختم‌های چندگانه ============

def create_salavat_goal(chat_id: int, goal_count: int, title: str, created_by: int = None) -> int:
    """ایجاد ختم جدید."""
    start_total = get_salavat_chat_total(chat_id)
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO salavat_goals (chat_id, goal_count, title, start_total, created_by)
           VALUES (?, ?, ?, ?, ?)""",
        (chat_id, goal_count, title, start_total, created_by),
    )
    goal_id = cur.lastrowid
    conn.commit()
    conn.close()
    return goal_id


def get_active_goals(chat_id: int) -> list:
    """دریافت لیست ختم‌های فعال یک گروه."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT g.*, 
                   COALESCE(SUM(c.amount), 0) as total_contributions,
                   COUNT(DISTINCT c.user_id) as participants_count
           FROM salavat_goals g
           LEFT JOIN salavat_contributions c ON g.id = c.goal_id
           WHERE g.chat_id = ? AND g.completed = 0
           GROUP BY g.id
           ORDER BY g.created_at DESC""",
        (chat_id,)
    ).fetchall()
    conn.close()
    return rows


def get_goal_by_id(goal_id: int):
    """دریافت اطلاعات یک ختم با شناسه."""
    conn = get_connection()
    row = conn.execute(
        """SELECT g.*, 
                   COALESCE(SUM(c.amount), 0) as total_contributions,
                   COUNT(DISTINCT c.user_id) as participants_count
           FROM salavat_goals g
           LEFT JOIN salavat_contributions c ON g.id = c.goal_id
           WHERE g.id = ?
           GROUP BY g.id""",
        (goal_id,)
    ).fetchone()
    conn.close()
    return row


def get_completed_goals(chat_id: int, limit: int = 5):
    """دریافت ختم‌های تکمیل‌شده اخیر."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT g.*, 
                   COALESCE(SUM(c.amount), 0) as total_contributions
           FROM salavat_goals g
           LEFT JOIN salavat_contributions c ON g.id = c.goal_id
           WHERE g.chat_id = ? AND g.completed = 1
           GROUP BY g.id
           ORDER BY g.completed_at DESC LIMIT ?""",
        (chat_id, limit)
    ).fetchall()
    conn.close()
    return rows


def get_goal_by_slug(chat_id: int, title: str):
    """دریافت ختم بر اساس عنوان."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM salavat_goals WHERE chat_id = ? AND title LIKE ?",
        (chat_id, f"%{title}%")
    ).fetchone()
    conn.close()
    return row


def contribute_to_goal(goal_id: int, user_id: int, user_name: str, amount: int) -> dict:
    """
    ثبت مشارکت کاربر در یک ختم.
    برمی‌گرداند: {goal_id, total_contributions, remaining, user_contribution, completed, goal}
    """
    conn = get_connection()
    
    # ثبت مشارکت کاربر
    conn.execute(
        """INSERT INTO salavat_contributions (goal_id, user_id, user_name, amount)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(goal_id, user_id) DO UPDATE SET
               amount = amount + excluded.amount,
               user_name = excluded.user_name""",
        (goal_id, user_id, user_name, amount),
    )
    
    # محاسبه مجموع مشارکت‌ها
    total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM salavat_contributions WHERE goal_id = ?",
        (goal_id,)
    ).fetchone()["total"]
    
    # دریافت اطلاعات ختم
    goal = conn.execute(
        "SELECT * FROM salavat_goals WHERE id = ?", (goal_id,)
    ).fetchone()
    
    # بررسی تکمیل شدن ختم
    if goal and not goal["completed"] and total >= goal["goal_count"]:
        conn.execute(
            "UPDATE salavat_goals SET completed = 1, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (goal_id,)
        )
        conn.commit()
        
        # دریافت مجدد اطلاعات به‌روز
        goal = conn.execute(
            "SELECT * FROM salavat_goals WHERE id = ?", (goal_id,)
        ).fetchone()
        
        conn.close()
        return {
            "goal_id": goal_id,
            "total_contributions": total,
            "remaining": 0,
            "completed": True,
            "goal": goal,
            "user_contribution": 0,
        }
    
    # مشارکت کاربر
    user_contrib = conn.execute(
        "SELECT amount FROM salavat_contributions WHERE goal_id = ? AND user_id = ?",
        (goal_id, user_id)
    ).fetchone()
    
    conn.commit()
    conn.close()
    
    return {
        "goal_id": goal_id,
        "total_contributions": total,
        "remaining": max(0, goal["goal_count"] - total if goal else 0),
        "completed": False,
        "user_contribution": user_contrib["amount"] if user_contrib else 0,
        "goal": goal,
    }


def delete_goal(goal_id: int):
    """حذف یک ختم."""
    conn = get_connection()
    conn.execute("DELETE FROM salavat_contributions WHERE goal_id = ?", (goal_id,))
    conn.execute("DELETE FROM salavat_goals WHERE id = ?", (goal_id,))
    conn.commit()
    conn.close()


def get_goal_participants(goal_id: int, limit: int = 10):
    """دریافت لیست مشارکت‌کنندگان در یک ختم."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT user_id, user_name, amount
           FROM salavat_contributions
           WHERE goal_id = ?
           ORDER BY amount DESC LIMIT ?""",
        (goal_id, limit)
    ).fetchall()
    conn.close()
    return rows


# ============ توابع مدیریت پیام‌های تعاملی ============

def save_interactive_message(chat_id: int, message_id: int, user_id: int, goal_id: int, message_type: str):
    """ذخیره پیام تعاملی برای حذف بعدی."""
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO interactive_messages (chat_id, message_id, user_id, goal_id, message_type)
           VALUES (?, ?, ?, ?, ?)""",
        (chat_id, message_id, user_id, goal_id, message_type),
    )
    conn.commit()
    conn.close()


def get_interactive_messages(chat_id: int, user_id: int = None):
    """دریافت پیام‌های تعاملی یک کاربر/گروه."""
    conn = get_connection()
    if user_id:
        rows = conn.execute(
            "SELECT * FROM interactive_messages WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM interactive_messages WHERE chat_id = ?",
            (chat_id,)
        ).fetchall()
    conn.close()
    return rows


def delete_interactive_messages(chat_id: int, user_id: int = None):
    """حذف پیام‌های تعاملی یک کاربر/گروه."""
    conn = get_connection()
    if user_id:
        conn.execute(
            "DELETE FROM interactive_messages WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id)
        )
    else:
        conn.execute(
            "DELETE FROM interactive_messages WHERE chat_id = ?",
            (chat_id,)
        )
    conn.commit()
    conn.close()


# ============ بقیه توابع دیتابیس ============

def get_user_translation(user_id: int) -> str:
    conn = get_connection()
    row = conn.execute(
        "SELECT preferred_translation FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row:
        return row["preferred_translation"]
    return "makarem"


def set_user_translation(user_id: int, translation_key: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO users (user_id, preferred_translation) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET preferred_translation = excluded.preferred_translation",
        (user_id, translation_key),
    )
    conn.commit()
    conn.close()


def add_favorite(user_id: int, item_type: str, item_ref: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO favorites (user_id, item_type, item_ref) VALUES (?, ?, ?)",
        (user_id, item_type, item_ref),
    )
    conn.commit()
    conn.close()


def get_favorites(user_id: int):
    conn = get_connection()
    rows = conn.execute(
        "SELECT item_type, item_ref FROM favorites WHERE user_id = ? ORDER BY rowid DESC", (user_id,)
    ).fetchall()
    conn.close()
    return rows


def remove_favorite(user_id: int, item_type: str, item_ref: str):
    conn = get_connection()
    conn.execute(
        "DELETE FROM favorites WHERE user_id = ? AND item_type = ? AND item_ref = ?",
        (user_id, item_type, item_ref),
    )
    conn.commit()
    conn.close()


def add_hadith(arabic_text, translation_text, narrator, source_book, chapter,
               hadith_number, tafsir_text=None, topics=None):
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO hadiths
           (arabic_text, translation_text, tafsir_text, narrator, source_book, chapter, hadith_number)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (arabic_text, translation_text, tafsir_text, narrator, source_book, chapter, hadith_number),
    )
    hadith_id = cur.lastrowid
    if topics:
        for topic in topics:
            conn.execute(
                "INSERT INTO hadith_topics (hadith_id, topic_name) VALUES (?, ?)",
                (hadith_id, topic.strip()),
            )
    conn.commit()
    conn.close()
    _reindex_hadith(hadith_id)
    return hadith_id


def get_hadith_by_id(hadith_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM hadiths WHERE id = ?", (hadith_id,)).fetchone()
    conn.close()
    return row


def get_hadith_topics(hadith_id: int):
    conn = get_connection()
    rows = conn.execute(
        "SELECT topic_name FROM hadith_topics WHERE hadith_id = ?", (hadith_id,)
    ).fetchall()
    conn.close()
    return [r["topic_name"] for r in rows]


def update_hadith_tafsir(hadith_id: int, tafsir_text: str):
    conn = get_connection()
    conn.execute(
        "UPDATE hadiths SET tafsir_text = ? WHERE id = ?", (tafsir_text, hadith_id)
    )
    conn.commit()
    conn.close()
    _reindex_hadith(hadith_id)


def update_hadith(hadith_id: int, arabic_text=None, translation_text=None,
                   tafsir_text=None, narrator=None, source_book=None,
                   chapter=None, hadith_number=None):
    fields = {
        "arabic_text": arabic_text,
        "translation_text": translation_text,
        "tafsir_text": tafsir_text,
        "narrator": narrator,
        "source_book": source_book,
        "chapter": chapter,
        "hadith_number": hadith_number,
    }
    fields = {k: v for k, v in fields.items() if v is not None}
    if not fields:
        return

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn = get_connection()
    conn.execute(
        f"UPDATE hadiths SET {set_clause} WHERE id = ?",
        (*fields.values(), hadith_id),
    )
    conn.commit()
    conn.close()
    _reindex_hadith(hadith_id)


def set_hadith_topics(hadith_id: int, topics):
    conn = get_connection()
    conn.execute("DELETE FROM hadith_topics WHERE hadith_id = ?", (hadith_id,))
    for topic in topics:
        topic = topic.strip()
        if topic:
            conn.execute(
                "INSERT INTO hadith_topics (hadith_id, topic_name) VALUES (?, ?)",
                (hadith_id, topic),
            )
    conn.commit()
    conn.close()
    _reindex_hadith(hadith_id)


def delete_hadith(hadith_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM hadith_topics WHERE hadith_id = ?", (hadith_id,))
    conn.execute(
        "DELETE FROM favorites WHERE item_type = 'hadith' AND item_ref = ?",
        (str(hadith_id),),
    )
    conn.execute("DELETE FROM hadiths WHERE id = ?", (hadith_id,))
    conn.commit()
    conn.close()
    _remove_from_index("hadith", hadith_id)


def list_hadiths(source_book: str = None, narrator: str = None,
                  topic: str = None, limit: int = 50):
    conn = get_connection()
    query = "SELECT h.* FROM hadiths h"
    conditions = []
    params = []

    if topic:
        query += " JOIN hadith_topics t ON h.id = t.hadith_id"
        conditions.append("t.topic_name = ?")
        params.append(topic)
    if source_book:
        conditions.append("h.source_book LIKE ?")
        params.append(f"%{source_book}%")
    if narrator:
        conditions.append("h.narrator LIKE ?")
        params.append(f"%{narrator}%")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY h.id LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def get_all_topics():
    conn = get_connection()
    rows = conn.execute("SELECT DISTINCT topic_name FROM hadith_topics ORDER BY topic_name").fetchall()
    conn.close()
    return [r["topic_name"] for r in rows]


def get_hadiths_by_topic(topic_name: str):
    conn = get_connection()
    rows = conn.execute(
        """SELECT h.* FROM hadiths h
           JOIN hadith_topics t ON h.id = t.hadith_id
           WHERE t.topic_name = ?""",
        (topic_name,),
    ).fetchall()
    conn.close()
    return rows


def get_random_hadith():
    conn = get_connection()
    row = conn.execute("SELECT * FROM hadiths ORDER BY RANDOM() LIMIT 1").fetchone()
    conn.close()
    return row


def get_random_nahj_item():
    conn = get_connection()
    row = conn.execute("SELECT * FROM nahj_balagha ORDER BY RANDOM() LIMIT 1").fetchone()
    conn.close()
    return row


def get_random_mafatih_item():
    conn = get_connection()
    row = conn.execute("SELECT * FROM mafatih ORDER BY RANDOM() LIMIT 1").fetchone()
    conn.close()
    return row


def search_hadiths(query: str, limit: int = 20):
    results = search_all(query, limit=limit, types=("hadith",))
    return [r["row"] for r in results]


def get_group_settings(chat_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM group_settings WHERE chat_id = ?", (chat_id,)).fetchone()
    if not row:
        conn.execute("INSERT INTO group_settings (chat_id) VALUES (?)", (chat_id,))
        conn.commit()
        row = conn.execute("SELECT * FROM group_settings WHERE chat_id = ?", (chat_id,)).fetchone()
    conn.close()
    return row


def update_group_settings(chat_id: int, **kwargs):
    conn = get_connection()
    get_group_settings(chat_id)
    for key, value in kwargs.items():
        conn.execute(f"UPDATE group_settings SET {key} = ? WHERE chat_id = ?", (value, chat_id))
    conn.commit()
    conn.close()


def get_all_active_daily_groups():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM group_settings WHERE daily_post_enabled = 1"
    ).fetchall()
    conn.close()
    return rows


# ---------------- توابع مربوط به Quiz ----------------

def add_quiz_question(question_text, option_a, option_b, option_c, option_d, correct_option,
                       category="general", difficulty="medium"):
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO quiz_questions
           (question_text, option_a, option_b, option_c, option_d, correct_option, category, difficulty)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (question_text, option_a, option_b, option_c, option_d, correct_option.lower(),
         category, difficulty),
    )
    qid = cur.lastrowid
    conn.commit()
    conn.close()
    return qid


def get_random_quiz_question(category: str = None, difficulty: str = None, exclude_ids=None):
    conn = get_connection()
    query = "SELECT * FROM quiz_questions"
    conditions = []
    params = []
    if category and category != "random":
        conditions.append("category = ?")
        params.append(category)
    if difficulty:
        conditions.append("difficulty = ?")
        params.append(difficulty)
    if exclude_ids:
        placeholders = ",".join("?" for _ in exclude_ids)
        conditions.append(f"id NOT IN ({placeholders})")
        params.extend(exclude_ids)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY RANDOM() LIMIT 1"
    row = conn.execute(query, params).fetchone()
    conn.close()
    return row


def get_quiz_question_by_id(qid: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM quiz_questions WHERE id = ?", (qid,)).fetchone()
    conn.close()
    return row


def count_quiz_questions(category: str = None) -> int:
    conn = get_connection()
    if category and category != "random":
        n = conn.execute(
            "SELECT COUNT(*) c FROM quiz_questions WHERE category = ?", (category,)
        ).fetchone()["c"]
    else:
        n = conn.execute("SELECT COUNT(*) c FROM quiz_questions").fetchone()["c"]
    conn.close()
    return n


def add_score(chat_id: int, user_id: int, username: str, points: int = 1):
    conn = get_connection()
    conn.execute(
        """INSERT INTO quiz_scores (chat_id, user_id, username, score)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(chat_id, user_id) DO UPDATE SET
               score = score + excluded.score,
               username = excluded.username""",
        (chat_id, user_id, username, points),
    )
    conn.commit()
    conn.close()


def get_leaderboard(chat_id: int, limit: int = 10):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM quiz_scores WHERE chat_id = ? ORDER BY score DESC LIMIT ?",
        (chat_id, limit),
    ).fetchall()
    conn.close()
    return rows


def get_global_leaderboard(limit: int = 10):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM quiz_user_stats ORDER BY total_points DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return rows


def record_quiz_result(chat_id: int, user_id: int, username: str, category: str,
                        is_correct: bool, points: int = 0):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO quiz_user_stats (user_id, username) VALUES (?, ?)",
        (user_id, username),
    )

    if is_correct:
        cur.execute(
            """UPDATE quiz_user_stats
               SET username = ?,
                   total_points = total_points + ?,
                   total_correct = total_correct + 1,
                   total_answered = total_answered + 1,
                   current_streak = current_streak + 1,
                   best_streak = MAX(best_streak, current_streak + 1)
               WHERE user_id = ?""",
            (username, points, user_id),
        )
        cur.execute(
            """INSERT INTO quiz_category_stats (user_id, category, correct_count)
               VALUES (?, ?, 1)
               ON CONFLICT(user_id, category) DO UPDATE SET
                   correct_count = correct_count + 1""",
            (user_id, category),
        )
    else:
        cur.execute(
            """UPDATE quiz_user_stats
               SET username = ?,
                   total_answered = total_answered + 1,
                   current_streak = 0
               WHERE user_id = ?""",
            (username, user_id),
        )

    stats = cur.execute(
        "SELECT * FROM quiz_user_stats WHERE user_id = ?", (user_id,)
    ).fetchone()
    cat_correct = cur.execute(
        "SELECT correct_count FROM quiz_category_stats WHERE user_id = ? AND category = ?",
        (user_id, category),
    ).fetchone()

    conn.commit()
    conn.close()

    result = dict(stats) if stats else {}
    result["category_correct"] = cat_correct["correct_count"] if cat_correct else 0
    return result


def get_user_quiz_stats(user_id: int):
    conn = get_connection()
    stats = conn.execute(
        "SELECT * FROM quiz_user_stats WHERE user_id = ?", (user_id,)
    ).fetchone()
    categories = conn.execute(
        "SELECT category, correct_count FROM quiz_category_stats WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    badges = conn.execute(
        "SELECT badge_key, awarded_at FROM quiz_badges WHERE user_id = ? ORDER BY awarded_at",
        (user_id,),
    ).fetchall()
    conn.close()
    return {
        "stats": stats,
        "categories": {row["category"]: row["correct_count"] for row in categories},
        "badges": [row["badge_key"] for row in badges],
    }


def award_badge(user_id: int, badge_key: str) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "INSERT OR IGNORE INTO quiz_badges (user_id, badge_key) VALUES (?, ?)",
        (user_id, badge_key),
    )
    is_new = cur.rowcount > 0
    conn.commit()
    conn.close()
    return is_new


# ---------------- توابع مربوط به تفسیر قرآن ----------------

def set_ayah_tafsir(surah: int, ayah: int, tafsir_text: str, source: str = ""):
    conn = get_connection()
    conn.execute(
        """INSERT INTO quran_tafsir (surah, ayah, tafsir_text, source)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(surah, ayah) DO UPDATE SET
               tafsir_text = excluded.tafsir_text,
               source = excluded.source""",
        (surah, ayah, tafsir_text, source),
    )
    conn.commit()
    conn.close()


def get_ayah_tafsir(surah: int, ayah: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM quran_tafsir WHERE surah = ? AND ayah = ?", (surah, ayah)
    ).fetchone()
    conn.close()
    return row


# ---------------- توابع مربوط به نهج‌البلاغه ----------------

NAHJ_CATEGORIES = ("khutbah", "letter", "hekmat")


def add_nahj_item(category: str, number: int, arabic_text: str, translation_text: str,
                   title: str = None, tafsir_text: str = None):
    conn = get_connection()
    conn.execute(
        """INSERT INTO nahj_balagha (category, number, title, arabic_text, translation_text, tafsir_text)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(category, number) DO UPDATE SET
               title = excluded.title,
               arabic_text = excluded.arabic_text,
               translation_text = excluded.translation_text,
               tafsir_text = excluded.tafsir_text""",
        (category, number, title, arabic_text, translation_text, tafsir_text),
    )
    conn.commit()
    conn.close()
    _reindex_nahj(category, number)


def get_nahj_item(category: str, number: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM nahj_balagha WHERE category = ? AND number = ?", (category, number)
    ).fetchone()
    conn.close()
    return row


def get_nahj_item_by_id(item_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM nahj_balagha WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return row


def get_nahj_numbers(category: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT number FROM nahj_balagha WHERE category = ? ORDER BY number", (category,)
    ).fetchall()
    conn.close()
    return [r["number"] for r in rows]


def update_nahj_tafsir(category: str, number: int, tafsir_text: str):
    conn = get_connection()
    conn.execute(
        "UPDATE nahj_balagha SET tafsir_text = ? WHERE category = ? AND number = ?",
        (tafsir_text, category, number),
    )
    conn.commit()
    conn.close()
    _reindex_nahj(category, number)


# ---------------- توابع مربوط به مفاتیح‌الجنان ----------------

MAFATIH_CATEGORIES = ("daily", "ziyarat", "weekly", "monthly", "munajat", "special")


def add_mafatih_item(category: str, title: str, arabic_text: str = "",
                      translation_text: str = None, tafsir_text: str = None,
                      image_path: str = None, slug: str = None, audio_file_id: str = None):
    conn = get_connection()
    if slug:
        cur = conn.execute(
            """INSERT INTO mafatih (category, title, arabic_text, translation_text, tafsir_text, image_path, slug, audio_file_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(slug) DO UPDATE SET
                   category = excluded.category,
                   title = excluded.title,
                   arabic_text = excluded.arabic_text,
                   translation_text = excluded.translation_text,
                   tafsir_text = excluded.tafsir_text,
                   image_path = excluded.image_path,
                   audio_file_id = excluded.audio_file_id""",
            (category, title, arabic_text or "", translation_text, tafsir_text, image_path, slug, audio_file_id),
        )
        conn.commit()
        row = conn.execute("SELECT id FROM mafatih WHERE slug = ?", (slug,)).fetchone()
        item_id = row["id"] if row else cur.lastrowid
    else:
        cur = conn.execute(
            """INSERT INTO mafatih (category, title, arabic_text, translation_text, tafsir_text, image_path, audio_file_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (category, title, arabic_text or "", translation_text, tafsir_text, image_path, audio_file_id),
        )
        item_id = cur.lastrowid
        conn.commit()
    conn.close()
    _reindex_mafatih(item_id)
    return item_id


def get_mafatih_by_slug(slug: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM mafatih WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    return row


def get_mafatih_item_flexible(identifier):
    identifier = str(identifier)
    if identifier.isdigit():
        row = get_mafatih_by_id(int(identifier))
        if row:
            return row
    return get_mafatih_by_slug(identifier)


def get_mafatih_by_category(category: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM mafatih WHERE category = ? ORDER BY id", (category,)
    ).fetchall()
    conn.close()
    return rows


def get_mafatih_by_id(item_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM mafatih WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return row


def get_mafatih_item(item_id: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM mafatih WHERE id = ?", (item_id,)
    ).fetchone()
    conn.close()
    return row


def update_mafatih_tafsir(item_id: int, tafsir_text: str):
    conn = get_connection()
    conn.execute(
        "UPDATE mafatih SET tafsir_text = ? WHERE id = ?", (tafsir_text, item_id)
    )
    conn.commit()
    conn.close()
    _reindex_mafatih(item_id)


def update_mafatih_image(item_id: int, image_path: str):
    conn = get_connection()
    conn.execute(
        "UPDATE mafatih SET image_path = ? WHERE id = ?", (image_path, item_id)
    )
    conn.commit()
    conn.close()


def update_mafatih_audio(item_id: int, audio_file_id: str):
    conn = get_connection()
    conn.execute(
        "UPDATE mafatih SET audio_file_id = ? WHERE id = ?", (audio_file_id, item_id)
    )
    conn.commit()
    conn.close()


def update_mafatih_translation(item_id: int, translation_text: str):
    conn = get_connection()
    conn.execute(
        "UPDATE mafatih SET translation_text = ? WHERE id = ?", (translation_text, item_id)
    )
    conn.commit()
    conn.close()
    _reindex_mafatih(item_id)


# ===== User profile helpers =====
def register_user(user_id: int, username: str = None):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, preferred_translation) VALUES (?, 'makarem')",
        (user_id,),
    )
    conn.commit()
    conn.close()


def get_user_stats(user_id: int):
    conn = get_connection()
    favorites = conn.execute(
        "SELECT COUNT(*) c FROM favorites WHERE user_id = ?", (user_id,)
    ).fetchone()["c"]
    quizzes = conn.execute(
        "SELECT COALESCE(SUM(score),0) s FROM quiz_scores WHERE user_id = ?", (user_id,)
    ).fetchone()["s"]
    conn.close()
    return {"favorites": favorites, "score": quizzes}


# ---------------- توابع مربوط به یادآور اذان ----------------

def get_prayer_reminder(user_id: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM prayer_reminders WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row


def upsert_prayer_reminder(user_id: int, **fields):
    if not fields:
        return

    conn = get_connection()
    existing = conn.execute(
        "SELECT 1 FROM prayer_reminders WHERE user_id = ?", (user_id,)
    ).fetchone()

    if existing:
        set_clause = ", ".join(f"{key} = ?" for key in fields)
        conn.execute(
            f"UPDATE prayer_reminders SET {set_clause} WHERE user_id = ?",
            (*fields.values(), user_id),
        )
    else:
        columns = ["user_id"] + list(fields.keys())
        placeholders = ", ".join("?" for _ in columns)
        conn.execute(
            f"INSERT INTO prayer_reminders ({', '.join(columns)}) VALUES ({placeholders})",
            (user_id, *fields.values()),
        )

    conn.commit()
    conn.close()


def toggle_prayer_reminder_azan(user_id: int, azan_key: str) -> int:
    column = f"remind_{azan_key}"
    existing = get_prayer_reminder(user_id)
    current = existing[column] if existing else 0
    new_value = 0 if current else 1
    upsert_prayer_reminder(user_id, **{column: new_value})
    return new_value


def set_prayer_reminder_minutes(user_id: int, minutes: int):
    upsert_prayer_reminder(user_id, minutes_before=minutes)


def get_all_enabled_prayer_reminders():
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM prayer_reminders
           WHERE enabled = 1
             AND (remind_fajr = 1 OR remind_noon = 1 OR remind_maghrib = 1)"""
    ).fetchall()
    conn.close()
    return rows


# =====================================================================
# توابع موتور جستجو
# =====================================================================

def _index_item(source_type: str, source_id: int, text_parts):
    content = normalize_for_search(" \n ".join(str(p) for p in text_parts if p))
    conn = get_connection()
    conn.execute(
        "DELETE FROM search_fts WHERE source_type = ? AND source_id = ?",
        (source_type, source_id),
    )
    if content.strip():
        conn.execute(
            "INSERT INTO search_fts (source_type, source_id, content) VALUES (?, ?, ?)",
            (source_type, source_id, content),
        )
    conn.commit()
    conn.close()


def _remove_from_index(source_type: str, source_id: int):
    conn = get_connection()
    conn.execute(
        "DELETE FROM search_fts WHERE source_type = ? AND source_id = ?",
        (source_type, source_id),
    )
    conn.commit()
    conn.close()


def _reindex_hadith(hadith_id: int):
    row = get_hadith_by_id(hadith_id)
    if not row:
        _remove_from_index("hadith", hadith_id)
        return
    topics = get_hadith_topics(hadith_id)
    _index_item(
        "hadith",
        hadith_id,
        [
            row["arabic_text"], row["translation_text"], row["tafsir_text"],
            row["narrator"], row["source_book"], row["chapter"], row["hadith_number"],
        ] + topics,
    )


def _reindex_nahj(category: str, number: int):
    row = get_nahj_item(category, number)
    if not row:
        return
    _index_item(
        "nahj",
        row["id"],
        [row["title"], row["arabic_text"], row["translation_text"], row["tafsir_text"]],
    )


def _reindex_mafatih(item_id: int):
    row = get_mafatih_by_id(item_id)
    if not row:
        _remove_from_index("mafatih", item_id)
        return
    _index_item(
        "mafatih",
        item_id,
        [row["title"], row["arabic_text"], row["translation_text"], row["tafsir_text"]],
    )


def rebuild_search_index():
    conn = get_connection()
    conn.execute("DELETE FROM search_fts")
    conn.commit()
    conn.close()

    conn = get_connection()
    hadiths = conn.execute("SELECT * FROM hadiths").fetchall()
    nahj_rows = conn.execute("SELECT * FROM nahj_balagha").fetchall()
    maf_rows = conn.execute("SELECT * FROM mafatih").fetchall()
    conn.close()

    for h in hadiths:
        topics = get_hadith_topics(h["id"])
        _index_item(
            "hadith", h["id"],
            [h["arabic_text"], h["translation_text"], h["tafsir_text"],
             h["narrator"], h["source_book"], h["chapter"], h["hadith_number"]] + topics,
        )
    for n in nahj_rows:
        _index_item("nahj", n["id"], [n["title"], n["arabic_text"], n["translation_text"], n["tafsir_text"]])
    for m in maf_rows:
        _index_item("mafatih", m["id"], [m["title"], m["arabic_text"], m["translation_text"], m["tafsir_text"]])

    print(f"✅ ایندکس جستجو بازسازی شد: {len(hadiths)} حدیث، {len(nahj_rows)} نهج‌البلاغه، {len(maf_rows)} مفاتیح.")


def ensure_search_index():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) AS c FROM search_fts").fetchone()["c"]
    conn.close()
    if count == 0:
        rebuild_search_index()


def _fts_query(match_expr: str, types=None, limit: int = 15):
    conn = get_connection()
    sql = "SELECT source_type, source_id, bm25(search_fts) AS rank FROM search_fts WHERE search_fts MATCH ?"
    params = [match_expr]
    if types:
        placeholders = ", ".join("?" for _ in types)
        sql += f" AND source_type IN ({placeholders})"
        params.extend(types)
    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return rows


def _fuzzy_fallback(norm_query: str, types=None, limit: int = 15):
    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        return []

    conn = get_connection()
    sql = "SELECT source_type, source_id, content FROM search_fts"
    params = []
    if types:
        placeholders = ", ".join("?" for _ in types)
        sql += f" WHERE source_type IN ({placeholders})"
        params.extend(types)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    if not rows:
        return []

    choices = {i: r["content"] for i, r in enumerate(rows)}
    matches = process.extract(
        norm_query, choices, scorer=fuzz.partial_ratio, limit=limit, score_cutoff=78
    )
    results = []
    for _, _score, idx in matches:
        r = rows[idx]
        results.append({"source_type": r["source_type"], "source_id": r["source_id"]})
    return results


_TYPE_TABLE = {"hadith": "hadiths", "nahj": "nahj_balagha", "mafatih": "mafatih"}


def hydrate_results(raw_results):
    if not raw_results:
        return []

    ids_by_type = {"hadith": [], "nahj": [], "mafatih": []}
    order = []
    seen = set()
    for r in raw_results:
        key = (r["source_type"], r["source_id"])
        if key in seen or r["source_type"] not in ids_by_type:
            continue
        seen.add(key)
        order.append(key)
        ids_by_type[r["source_type"]].append(r["source_id"])

    rows_by_key = {}
    conn = get_connection()
    for stype, ids in ids_by_type.items():
        if not ids:
            continue
        table = _TYPE_TABLE[stype]
        placeholders = ",".join("?" for _ in ids)
        fetched = conn.execute(
            f"SELECT * FROM {table} WHERE id IN ({placeholders})", ids
        ).fetchall()
        for row in fetched:
            rows_by_key[(stype, row["id"])] = row
    conn.close()

    hydrated = []
    for stype, sid in order:
        row = rows_by_key.get((stype, sid))
        if not row:
            continue
        if stype == "hadith":
            hydrated.append({
                "type": "hadith", "id": sid, "row": row,
                "title": row["narrator"] or "حدیث",
                "arabic": row["arabic_text"], "translation": row["translation_text"],
                "extra": row["source_book"] or "",
            })
        elif stype == "nahj":
            hydrated.append({
                "type": "nahj", "id": sid, "row": row,
                "title": row["title"] or "",
                "arabic": row["arabic_text"], "translation": row["translation_text"],
                "extra": {"category": row["category"], "number": row["number"]},
            })
        elif stype == "mafatih":
            hydrated.append({
                "type": "mafatih", "id": sid, "row": row,
                "title": row["title"] or "",
                "arabic": row["arabic_text"], "translation": row["translation_text"] or "",
                "extra": row["category"] or "",
            })
    return hydrated


def search_raw(query: str, limit: int = 15, types=None):
    norm_q = normalize_for_search(query)
    tokens = [t for t in norm_q.split() if t]
    if not tokens:
        return []

    rows = []

    if len(tokens) > 1:
        phrase = '"' + " ".join(tokens) + '"'
        rows = _fts_query(phrase, types=types, limit=limit)

    if not rows and len(tokens) > 1:
        and_expr = " AND ".join(f"{t}*" for t in tokens)
        rows = _fts_query(and_expr, types=types, limit=limit)

    if not rows:
        or_expr = " OR ".join(f"{t}*" for t in tokens)
        rows = _fts_query(or_expr, types=types, limit=limit)

    results = [{"source_type": r["source_type"], "source_id": r["source_id"]} for r in rows]

    if not results:
        results = _fuzzy_fallback(norm_q, types=types, limit=limit)

    return results


def search_all(query: str, limit: int = 15, types=None):
    return hydrate_results(search_raw(query, limit=limit, types=types))