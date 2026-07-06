import httpx
from config import QURAN_API_BASE, DEFAULT_TRANSLATIONS, PROXY_URL
from database import get_connection


def _http_client(timeout=15):
    """
    ساخت کلاینت httpx با در نظر گرفتن پروکسی (برای هاست‌های ایرانی
    که به APIهای خارجی مثل alquran.cloud دسترسی مستقیم ندارند).
    """
    if PROXY_URL:
        return httpx.AsyncClient(timeout=timeout, proxy=PROXY_URL)
    return httpx.AsyncClient(timeout=timeout)

# لیست سوره‌ها (نام + تعداد آیات) - این ثابت است و نیازی به API ندارد
SURAH_LIST = None  # هنگام اجرا از API پر می‌شود و کش می‌شود در حافظه


async def get_surah_list():
    """گرفتن لیست ۱۱۴ سوره (نام عربی، فارسی، تعداد آیات)."""
    global SURAH_LIST
    if SURAH_LIST:
        return SURAH_LIST
    async with _http_client() as client:
        resp = await client.get(f"{QURAN_API_BASE}/surah")
        data = resp.json()
        SURAH_LIST = data["data"]  # لیست دیکشنری‌ها با کلیدهای number, name, englishName, numberOfAyahs
    return SURAH_LIST


def _get_cached(surah: int, ayah: int, edition: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT text FROM quran_cache WHERE surah=? AND ayah=? AND edition=?",
        (surah, ayah, edition),
    ).fetchone()
    conn.close()
    return row["text"] if row else None


def _set_cached(surah: int, ayah: int, edition: str, text: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO quran_cache (surah, ayah, edition, text) VALUES (?, ?, ?, ?)",
        (surah, ayah, edition, text),
    )
    conn.commit()
    conn.close()


async def get_ayah(surah: int, ayah: int, translation_key: str = "makarem"):
    """
    گرفتن متن عربی + ترجمه‌ی یک آیه.
    ابتدا از کش محلی می‌خواند، اگر نبود از API می‌گیرد و کش می‌کند.
    """
    edition_code = DEFAULT_TRANSLATIONS.get(translation_key, "fa.makarem")

    arabic = _get_cached(surah, ayah, "arabic")
    translation = _get_cached(surah, ayah, edition_code)

    if arabic and translation:
        return {"arabic": arabic, "translation": translation}

    ref = f"{surah}:{ayah}"
    async with _http_client() as client:
        # درخواست هم‌زمان متن عربی و ترجمه با ادیشن‌های ترکیبی
        resp = await client.get(f"{QURAN_API_BASE}/ayah/{ref}/editions/quran-uthmani,{edition_code}")
        data = resp.json()

    if data.get("code") != 200:
        return None

    editions_data = data["data"]
    arabic_text = None
    translation_text = None
    for ed in editions_data:
        if ed["edition"]["identifier"] == "quran-uthmani":
            arabic_text = ed["text"]
        elif ed["edition"]["identifier"] == edition_code:
            translation_text = ed["text"]

    if arabic_text:
        _set_cached(surah, ayah, "arabic", arabic_text)
    if translation_text:
        _set_cached(surah, ayah, edition_code, translation_text)

    return {"arabic": arabic_text, "translation": translation_text}
