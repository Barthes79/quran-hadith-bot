import httpx
import logging
from config import QURAN_API_BASE, DEFAULT_TRANSLATIONS, DEFAULT_TRANSLATION_KEY, PROXY_URL
from database import get_connection, quran_ayah_count, store_quran_dump

logger = logging.getLogger(__name__)

TOTAL_AYAHS = 6236


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
    global_number = _get_cached(surah, ayah, "global_number")

    if arabic and translation and global_number:
        return {"arabic": arabic, "translation": translation, "number": int(global_number)}

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
    ayah_global_number = None
    for ed in editions_data:
        if ed["edition"]["identifier"] == "quran-uthmani":
            arabic_text = ed["text"]
            ayah_global_number = ed.get("number")
        elif ed["edition"]["identifier"] == edition_code:
            translation_text = ed["text"]

    if arabic_text:
        _set_cached(surah, ayah, "arabic", arabic_text)
    if translation_text:
        _set_cached(surah, ayah, edition_code, translation_text)
    if ayah_global_number:
        _set_cached(surah, ayah, "global_number", str(ayah_global_number))

    return {
        "arabic": arabic_text,
        "translation": translation_text,
        "number": ayah_global_number,
    }


def get_audio_url(global_number: int, reciter: str = "ar.alafasy", bitrate: int = 128) -> str:
    """
    ساخت آدرس مستقیم فایل صوتی تلاوت یک آیه از CDN رسمی alquran.cloud.
    reciter پیش‌فرض: مشاری راشد العفاسی (یکی از معروف‌ترین قاریان).
    """
    return f"https://cdn.islamic.network/quran/audio/{bitrate}/{reciter}/{global_number}.mp3"


async def ensure_quran_data() -> bool:
    """
    اگر متن کامل قرآن هنوز در دیتابیس نیست، یک‌بار (دو درخواست: عربی + ترجمه)
    از alquran.cloud دانلود و برای جستجوی inline ایندکس می‌کند. بعد از اولین
    موفقیت دیگر هیچ درخواستی نمی‌زند. خروجی: آیا داده آماده است یا نه.
    """
    if quran_ayah_count() >= TOTAL_AYAHS:
        return True

    edition = DEFAULT_TRANSLATIONS[DEFAULT_TRANSLATION_KEY]
    try:
        async with _http_client(timeout=120) as client:
            ar_resp = await client.get(f"{QURAN_API_BASE}/quran/quran-uthmani")
            fa_resp = await client.get(f"{QURAN_API_BASE}/quran/{edition}")
        ar_data = ar_resp.json()
        fa_data = fa_resp.json()
        if ar_data.get("code") != 200 or fa_data.get("code") != 200:
            raise RuntimeError("پاسخ نامعتبر از API قرآن")

        translations = {}
        for surah in fa_data["data"]["surahs"]:
            for a in surah["ayahs"]:
                translations[(surah["number"], a["numberInSurah"])] = a["text"]

        rows = []
        for surah in ar_data["data"]["surahs"]:
            for a in surah["ayahs"]:
                rows.append({
                    "surah": surah["number"],
                    "ayah": a["numberInSurah"],
                    "global_number": a["number"],
                    "surah_name": surah["name"],
                    "arabic": a["text"],
                    "translation": translations.get((surah["number"], a["numberInSurah"]), ""),
                })

        if len(rows) != TOTAL_AYAHS:
            raise RuntimeError(f"تعداد آیات دریافتی {len(rows)} است، نه {TOTAL_AYAHS}")

        store_quran_dump(rows, edition)
        logger.info("✅ متن کامل قرآن (%d آیه) برای جستجوی inline ایندکس شد.", len(rows))
        return True
    except Exception:
        logger.exception("دانلود متن قرآن برای جستجو ناموفق بود؛ بعداً دوباره تلاش می‌شود.")
        return False
