import sqlite3
from config import DATABASE_PATH


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
            narrator TEXT,           -- معصوم (مثلاً امام علی ع)
            source_book TEXT,        -- مثلاً الکافی
            chapter TEXT,
            hadith_number TEXT
        )
    """)

    # موضوعات هر حدیث (یک حدیث می‌تواند چند موضوع داشته باشد)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hadith_topics (
            hadith_id INTEGER,
            topic_name TEXT,
            FOREIGN KEY (hadith_id) REFERENCES hadiths(id)
        )
    """)

    # تنظیمات کاربران (چت خصوصی)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            preferred_translation TEXT DEFAULT 'makarem'
        )
    """)

    # علاقه‌مندی‌های کاربر (بوکمارک)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER,
            item_type TEXT,    -- 'ayah' یا 'hadith'
            item_ref TEXT,     -- مثلاً '2:255' یا شناسه حدیث
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
            preferred_translation TEXT DEFAULT 'makarem'
        )
    """)

    # سوالات مسابقه (Quiz)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL  -- 'a', 'b', 'c' یا 'd'
        )
    """)

    # امتیاز کاربران در هر گروه (لیدربورد)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quiz_scores (
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT,
            score INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )
    """)

    # تفسیر آیات قرآن (ثبت دستی توسط ادمین، چون API رایگان تفسیر فارسی وجود ندارد)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quran_tafsir (
            surah INTEGER,
            ayah INTEGER,
            tafsir_text TEXT NOT NULL,
            source TEXT,
            PRIMARY KEY (surah, ayah)
        )
    """)

    # نهج‌البلاغه: خطبه‌ها (khutbah)، نامه‌ها (letter)، حکمت‌ها (hekmat)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS nahj_balagha (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,      -- 'khutbah' | 'letter' | 'hekmat'
            number INTEGER NOT NULL,     -- شماره‌ی متعارف (بر اساس نسخه صبحی صالح)
            title TEXT,                  -- عنوان اختیاری (مثلاً موضوع خطبه)
            arabic_text TEXT NOT NULL,
            translation_text TEXT NOT NULL,
            tafsir_text TEXT,
            UNIQUE(category, number)
        )
    """)

    # مفاتیح‌الجنان: ادعیه، زیارات، اعمال روزانه/هفتگی/ماهانه، مناجات و...
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mafatih (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,      -- daily | ziyarat | weekly | monthly | munajat | special
            title TEXT NOT NULL,         -- مثلاً 'دعای کمیل' یا 'زیارت عاشورا'
            arabic_text TEXT NOT NULL,
            translation_text TEXT,
            tafsir_text TEXT
        )
    """)

    # سازگاری با دیتابیس‌های قدیمی
    try:
        cur.execute("ALTER TABLE group_settings ADD COLUMN post_interval_hours INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


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
    return hadith_id


def get_hadith_by_id(hadith_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM hadiths WHERE id = ?", (hadith_id,)).fetchone()
    conn.close()
    return row


def update_hadith_tafsir(hadith_id: int, tafsir_text: str):
    conn = get_connection()
    conn.execute(
        "UPDATE hadiths SET tafsir_text = ? WHERE id = ?", (tafsir_text, hadith_id)
    )
    conn.commit()
    conn.close()


def update_hadith(hadith_id: int, arabic_text=None, translation_text=None,
                   tafsir_text=None, narrator=None, source_book=None,
                   chapter=None, hadith_number=None):
    """
    فقط فیلدهایی که مقدار برایشان داده شده (None نباشند) آپدیت می‌شوند.
    """
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


def set_hadith_topics(hadith_id: int, topics):
    """موضوعات قبلی حدیث را پاک و موضوعات جدید را جایگزین می‌کند."""
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


def delete_hadith(hadith_id: int):
    """یک حدیث و موضوعات/علاقه‌مندی‌های مرتبط با آن را حذف می‌کند."""
    conn = get_connection()
    conn.execute("DELETE FROM hadith_topics WHERE hadith_id = ?", (hadith_id,))
    conn.execute(
        "DELETE FROM favorites WHERE item_type = 'hadith' AND item_ref = ?",
        (str(hadith_id),),
    )
    conn.execute("DELETE FROM hadiths WHERE id = ?", (hadith_id,))
    conn.commit()
    conn.close()


def list_hadiths(source_book: str = None, narrator: str = None,
                  topic: str = None, limit: int = 50):
    """
    برای پیدا کردن شناسه (id) احادیث قبل از حذف/ادیت، با فیلتر اختیاری.
    """
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


def search_hadiths(query: str):
    conn = get_connection()
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM hadiths WHERE translation_text LIKE ? OR arabic_text LIKE ? LIMIT 20",
        (like, like),
    ).fetchall()
    conn.close()
    return rows


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
    get_group_settings(chat_id)  # اطمینان از وجود ردیف
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

def add_quiz_question(question_text, option_a, option_b, option_c, option_d, correct_option):
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO quiz_questions
           (question_text, option_a, option_b, option_c, option_d, correct_option)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (question_text, option_a, option_b, option_c, option_d, correct_option.lower()),
    )
    qid = cur.lastrowid
    conn.commit()
    conn.close()
    return qid


def get_random_quiz_question():
    conn = get_connection()
    row = conn.execute("SELECT * FROM quiz_questions ORDER BY RANDOM() LIMIT 1").fetchone()
    conn.close()
    return row


def get_quiz_question_by_id(qid: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM quiz_questions WHERE id = ?", (qid,)).fetchone()
    conn.close()
    return row


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


def get_nahj_item(category: str, number: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM nahj_balagha WHERE category = ? AND number = ?", (category, number)
    ).fetchone()
    conn.close()
    return row


def get_nahj_numbers(category: str):
    """شماره‌ی موارد ثبت‌شده‌ی یک دسته (خطبه/نامه/حکمت)، مرتب‌شده."""
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


# ---------------- توابع مربوط به مفاتیح‌الجنان ----------------

MAFATIH_CATEGORIES = ("daily", "ziyarat", "weekly", "monthly", "munajat", "special")


def add_mafatih_item(category: str, title: str, arabic_text: str,
                      translation_text: str = None, tafsir_text: str = None):
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO mafatih (category, title, arabic_text, translation_text, tafsir_text)
           VALUES (?, ?, ?, ?, ?)""",
        (category, title, arabic_text, translation_text, tafsir_text),
    )
    item_id = cur.lastrowid
    conn.commit()
    conn.close()
    return item_id


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


def update_mafatih_tafsir(item_id: int, tafsir_text: str):
    conn = get_connection()
    conn.execute(
        "UPDATE mafatih SET tafsir_text = ? WHERE id = ?", (tafsir_text, item_id)
    )
    conn.commit()
    conn.close()


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
