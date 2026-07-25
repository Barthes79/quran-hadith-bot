import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, InlineQueryHandler, filters, ContextTypes,
)
from telegram.request import HTTPXRequest

from config import BOT_TOKEN, PROXY_URL
from database import init_db, ensure_search_index

from handlers.start import start_command, menu_callback, set_translation_callback, clear_keyboard_command
from handlers.quran import (
    surah_page_callback, surah_selected_callback, ayah_nav_callback,
    fav_ayah_callback, tafsir_callback, ayah_direct_lookup, add_quran_tafsir_command,
    audio_callback, ayah_list_page_callback,
)
from handlers.hadith import (
    topic_selected_callback, random_hadith_callback, fav_hadith_callback,
    topic_nav_callback, noop_callback,
    add_hadith_command, text_search_handler, add_tafsir_command,
    find_hadith_command, edit_hadith_command, del_hadith_command,
    hadith_view_callback,
)
from handlers.inline import inline_query_handler
from handlers.profile import profile_command
from handlers.favorites import (
    favorites_command,
    favorites_hadith_callback,
    favorites_quran_callback,
    favorites_nahj_callback,
    favorites_mafatih_callback,
    favorites_back_callback,
)
from handlers.nahj import (
    nahj_category_callback, nahj_page_callback, nahj_menu_callback,
    nahj_item_callback, fav_nahj_callback, add_nahj_command,
    nahj_text_page_callback,
)
# توابع مفاتیح الجنان به همراه هندلر متنی و هندلر فایل صوتی اضافه شد
from handlers.mafatih import (
    mafatih_category_callback, mafatih_subcategory_callback, mafatih_menu_callback, 
    mafatih_item_callback, fav_mafatih_callback, add_mafatih_command,
    mafatih_menu_text_callback, mafatih_text_page_callback, mafatih_audio_callback,
)
from handlers.admin import (
    group_settings_command, group_settings_router,
    daily_post_job, set_welcome_command, member_update_handler, link_guard_handler,
)
from handlers.quiz import (
    quiz_command, quiz_answer_callback, leaderboard_command, add_quiz_command,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def general_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    در چت خصوصی، هر متنی که کاربر بفرستد ابتدا به‌عنوان شماره آیه
    (مثل 2:255) و در غیر این‌صورت به‌عنوان عبارت جستجوی حدیث بررسی می‌شود.
    در گروه‌ها فقط به دستورات صریح پاسخ می‌دهیم تا اسپم نشود.
    """
    if update.effective_chat.type != "private":
        return  # در گروه فقط دستورات/inline کار می‌کند

    text = update.message.text.strip()
    handled = await ayah_direct_lookup(update, context, text)
    if not handled:
        await text_search_handler(update, context, text)

async def get_file_id_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تابع کمکی برای دیباگ و استخراج راحتِ file_id فایل‌های صوتی، صوتی شخصی، ویدیو و اسناد"""
    if not update.message:
        return

    if update.message.audio:
        await update.message.reply_text(f"🎧 *Audio file_id:*\n`{update.message.audio.file_id}`", parse_mode="Markdown")
    elif update.message.voice:
        await update.message.reply_text(f"🎤 *Voice file_id:*\n`{update.message.voice.file_id}`", parse_mode="Markdown")
    elif update.message.document:
        await update.message.reply_text(f"📄 *Document file_id:*\n`{update.message.document.file_id}`", parse_mode="Markdown")
    elif update.message.video:
        await update.message.reply_text(f"📹 *Video file_id:*\n`{update.message.video.file_id}`", parse_mode="Markdown")

def main():
    init_db()
    ensure_search_index()  # ایندکس جستجو را (فقط اولین بار) می‌سازد؛ بعد از آن خودکار هم‌گام می‌ماند

    builder = Application.builder().token(BOT_TOKEN)

    # پیش‌فرض کتابخانه برای هر درخواست فقط ۵ ثانیه فرصت می‌دهد؛ برای آپلود
    # عکس (به‌خصوص وقتی از پروکسی رد می‌شود) این زمان کم است و باعث خطای
    # TimedOut و نمایش‌نشدن گاه‌به‌گاه عکس‌ها می‌شود. این مقادیر را بالا می‌بریم.
    default_request = HTTPXRequest(
        connect_timeout=15,
        read_timeout=30,
        write_timeout=30,
        pool_timeout=15,
        proxy=PROXY_URL,
    )
    get_updates_request = HTTPXRequest(
        connect_timeout=15,
        read_timeout=40,
        write_timeout=15,
        pool_timeout=15,
        proxy=PROXY_URL,
    )
    builder = builder.request(default_request).get_updates_request(get_updates_request)

    if PROXY_URL:
        logger.info("در حال استفاده از پروکسی: %s", PROXY_URL)

    app = builder.build()

    async def _global_error_handler(update, context):
        logger.exception("خطای مدیریت‌نشده در پردازش آپدیت", exc_info=context.error)

    app.add_error_handler(_global_error_handler)

    # دستورات
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("favorites", favorites_command))
    app.add_handler(CallbackQueryHandler(favorites_hadith_callback, pattern="^favorites_hadith$"))
    app.add_handler(CallbackQueryHandler(favorites_quran_callback, pattern="^favorites_quran$"))
    app.add_handler(CallbackQueryHandler(favorites_nahj_callback, pattern="^favorites_nahj$"))
    app.add_handler(CallbackQueryHandler(favorites_mafatih_callback, pattern="^favorites_mafatih$"))
    app.add_handler(CallbackQueryHandler(favorites_back_callback, pattern="^favorites_back$"))
    app.add_handler(CommandHandler("addnahj", add_nahj_command))
    app.add_handler(CommandHandler("addmafatih", add_mafatih_command))
    app.add_handler(CommandHandler("clearkeyboard", clear_keyboard_command))
    app.add_handler(CommandHandler("addhadith", add_hadith_command))
    app.add_handler(CommandHandler("addtafsir", add_tafsir_command))
    app.add_handler(CommandHandler("findhadith", find_hadith_command))
    app.add_handler(CommandHandler("edithadith", edit_hadith_command))
    app.add_handler(CommandHandler("delhadith", del_hadith_command))
    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("addquiz", add_quiz_command))
    app.add_handler(CommandHandler("addqtafsir", add_quran_tafsir_command))
    app.add_handler(CallbackQueryHandler(quiz_answer_callback, pattern="^quizans_"))
    app.add_handler(CommandHandler("groupsettings", group_settings_command))
    app.add_handler(CommandHandler("setwelcome", set_welcome_command))

    # کالبک‌های منو
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))
    app.add_handler(CallbackQueryHandler(set_translation_callback, pattern="^set_translation_"))

    # کالبک‌های قرآن
    app.add_handler(CallbackQueryHandler(surah_page_callback, pattern="^surah_page_"))
    app.add_handler(CallbackQueryHandler(surah_selected_callback, pattern="^surah_\\d+$"))
    app.add_handler(CallbackQueryHandler(ayah_list_page_callback, pattern="^ayahlist_\\d+_\\d+$"))
    app.add_handler(CallbackQueryHandler(ayah_nav_callback, pattern="^ayah_\\d+_\\d+$"))
    app.add_handler(CallbackQueryHandler(fav_ayah_callback, pattern="^fav_ayah_"))
    app.add_handler(CallbackQueryHandler(tafsir_callback, pattern="^tafsir_"))
    app.add_handler(CallbackQueryHandler(audio_callback, pattern="^audio_"))

    # کالبک‌های احادیث
    app.add_handler(CallbackQueryHandler(topic_selected_callback, pattern="^topic_"))
    app.add_handler(CallbackQueryHandler(topic_nav_callback, pattern="^topicnav_"))
    app.add_handler(CallbackQueryHandler(noop_callback, pattern="^noop$"))
    app.add_handler(CallbackQueryHandler(random_hadith_callback, pattern="^hadith_random$"))
    app.add_handler(CallbackQueryHandler(fav_hadith_callback, pattern="^fav_hadith_"))
    app.add_handler(CallbackQueryHandler(hadith_view_callback, pattern="^hadithview_"))

    # کالبک‌های نهج‌البلاغه
    app.add_handler(CallbackQueryHandler(nahj_menu_callback, pattern="^nahjmenu$"))
    app.add_handler(CallbackQueryHandler(nahj_category_callback, pattern="^nahjcat_"))
    app.add_handler(CallbackQueryHandler(nahj_page_callback, pattern="^nahjpage_"))
    app.add_handler(CallbackQueryHandler(nahj_item_callback, pattern="^nahjitem_"))
    app.add_handler(CallbackQueryHandler(nahj_text_page_callback, pattern="^nahjtxt_"))
    app.add_handler(CallbackQueryHandler(fav_nahj_callback, pattern="^favnahj_"))

    # کالبک‌های مفاتیح‌الجنان
    app.add_handler(CallbackQueryHandler(mafatih_menu_callback, pattern="^mafmenu$"))
    app.add_handler(CallbackQueryHandler(mafatih_category_callback, pattern="^mafcat_"))
    app.add_handler(CallbackQueryHandler(mafatih_subcategory_callback, pattern="^mafsub_"))
    app.add_handler(CallbackQueryHandler(mafatih_item_callback, pattern="^mafitem_"))
    app.add_handler(CallbackQueryHandler(mafatih_text_page_callback, pattern="^maftxt_"))
    app.add_handler(CallbackQueryHandler(mafatih_audio_callback, pattern="^mafaudio_"))
    app.add_handler(CallbackQueryHandler(fav_mafatih_callback, pattern="^favmaf_"))

    # کالبک‌های تنظیمات گروه
    app.add_handler(CallbackQueryHandler(group_settings_router, pattern="^gset_"))

    # =========================================================================
    # دریافت موقت file_id فایل‌های فرستاده‌شده به ربات (پشتیبانی از صوت، داکیومنت و ویدیو)
    # =========================================================================
    app.add_handler(MessageHandler(
        filters.AUDIO | filters.VOICE | filters.Document.ALL | filters.VIDEO, 
        get_file_id_debug
    ))

    # inline mode
    app.add_handler(InlineQueryHandler(inline_query_handler))

    # عضویت ربات در گروه جدید
    # عضویت/خروج اعضا (خوش‌آمدگویی به ربات، خوش‌آمدگویی سفارشی اعضای جدید، پاک‌سازی پیام سرویس)
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER,
        member_update_handler,
    ))

    # ضداسپم ساده‌ی لینک (فقط وقتی ادمین گروه در تنظیمات فعالش کرده باشد)؛ در گروه
    # جدا اجرا می‌شود تا مستقل از هندلرهای متنی دیگر همیشه چک شود
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, link_guard_handler),
        group=1,
    )

    # ==========================================
    # هندلر پیام‌های متنی (Text Handlers)
    # ==========================================
    
    # ۱. هندلر دکمه متنی مفاتیح الجنان (حتماً باید بالاتر از general_text_handler باشد)
    app.add_handler(MessageHandler(filters.Regex("^(مفاتیح الجنان|مفاتیح|📿 مفاتیح الجنان)$"), mafatih_menu_text_callback))
    
    # ۲. پیام‌های متنی عادی (فقط چت خصوصی)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, general_text_handler))

    # جاب پست روزانه - هر ساعت یکبار چک می‌کند
    if app.job_queue:
        app.job_queue.run_repeating(daily_post_job, interval=3600, first=10)

    logger.info("Bot started polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()