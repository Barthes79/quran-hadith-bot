import logging
from datetime import time as dtime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, InlineQueryHandler, filters, ContextTypes,
)
from telegram.request import HTTPXRequest

from config import BOT_TOKEN, PROXY_URL
from database import init_db, ensure_search_index

from handlers.start import start_command, menu_callback, set_translation_callback, clear_keyboard_command
from handlers.ownership import ownership_guard_callback
from handlers.quran import (
    surah_page_callback, surah_selected_callback, ayah_nav_callback,
    fav_ayah_callback, tafsir_callback, ayah_direct_lookup, add_quran_tafsir_command,
    audio_callback, ayah_list_page_callback, surah_name_ayah_lookup,
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
from handlers.mafatih import (
    mafatih_category_callback, mafatih_subcategory_callback, mafatih_menu_callback, 
    mafatih_item_callback, fav_mafatih_callback, add_mafatih_command,
    mafatih_menu_text_callback, mafatih_text_page_callback, mafatih_audio_callback,
)
from handlers.admin import (
    group_settings_command, group_settings_router,
    daily_post_job, set_welcome_command, member_update_handler, link_guard_handler,
    set_mafatih_audio_command, mafatih_audio_upload_handler,
)
from handlers.quiz import (
    quiz_command, quiz_menu_callback, quiz_category_callback, quiz_answer_callback,
    leaderboard_command, global_leaderboard_command, my_quiz_stats_command,
    add_quiz_command, quiz_settings_command, quiz_time_command,
    quiz_buzzer_command, quiz_next_delay_command, start_rapid_quiz,
    start_normal_quiz, 
)
from handlers.help import help_command, help_callback
from handlers.prayer import (
    prayer_command, prayer_city_callback, prayer_city_list_callback,
    prayer_page_callback, prayer_refresh_callback, prayer_location_callback,
    prayer_location_handler, prayer_back_callback, prayer_all_cities_callback,
    prayer_reminder_callback, prayer_reminder_toggle_callback,
    prayer_reminder_setmin_callback, prayer_reminder_minutes_text_handler,
    schedule_daily_prayer_reminders,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def general_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    فرمت‌های صریح آیه («2:255» یا «بقره 25») هم در چت خصوصی و هم در گروه‌ها
    کار می‌کنند.

    جستجوی آزاد حدیث (هر متن دلخواه) فقط وقتی فعال است که کاربر از منوی
    اصلی دکمه‌ی «🔍 جستجو» را زده باشد (پرچم context.user_data["search_mode"]).
    قبلاً هر پیام متنی در پیوی که آیه هم نبود، خودکار سرچ می‌شد؛ که باعث
    می‌شد پیام‌های معمولی/گفتگوی عادی کاربر هم به‌اشتباه جستجو بشن.

    نکته: بررسی «آیا این پیام همون عددیه که برای تنظیم یادآور اذان منتظرش
    بودیم» باید همین‌جا و قبل از هر چیز دیگه انجام بشه (نه در یک
    MessageHandler جدا)، وگرنه وقتی search_mode روشن باشه، همون عدد هم به
    غلط به‌عنوان عبارت جستجو فرستاده می‌شه.
    """
    text = update.message.text.strip()
    is_private = update.effective_chat.type == "private"

    consumed_by_reminder = await prayer_reminder_minutes_text_handler(update, context)
    if consumed_by_reminder:
        return

    search_mode = context.user_data.get("search_mode", False)

    handled = await ayah_direct_lookup(update, context, text)
    if not handled:
        handled = await surah_name_ayah_lookup(update, context, text)

    if not handled and is_private and search_mode:
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
    ensure_search_index()

    builder = Application.builder().token(BOT_TOKEN)

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

    app.add_handler(CallbackQueryHandler(ownership_guard_callback), group=-10)

    # ==========================================
    # دستورات
    # ==========================================
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
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
    app.add_handler(CommandHandler("quizrank", global_leaderboard_command))
    app.add_handler(CommandHandler("mystats", my_quiz_stats_command))
    app.add_handler(CommandHandler("addquiz", add_quiz_command))
    app.add_handler(CommandHandler("quizsettings", quiz_settings_command))
    app.add_handler(CommandHandler("quiztime", quiz_time_command))
    app.add_handler(CommandHandler("quizbuzzer", quiz_buzzer_command))
    app.add_handler(CommandHandler("quiznextdelay", quiz_next_delay_command))
    app.add_handler(CommandHandler("addqtafsir", add_quran_tafsir_command))
    app.add_handler(CallbackQueryHandler(quiz_answer_callback, pattern="^quizans_"))
    app.add_handler(CallbackQueryHandler(quiz_category_callback, pattern="^quizcat_"))
    app.add_handler(CallbackQueryHandler(quiz_menu_callback, pattern="^quizmenu$"))
    app.add_handler(CommandHandler("groupsettings", group_settings_command))
    app.add_handler(CommandHandler("setwelcome", set_welcome_command))
    app.add_handler(CommandHandler("setmafaudio", set_mafatih_audio_command))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, mafatih_audio_upload_handler))

    # ==========================================
# دستورات اوقات شرعی
# ==========================================
# دستور لاتین
    app.add_handler(CommandHandler("prayer", prayer_command))

# پاسخ به پیام "اذان" در چت خصوصی (بدون اسلش)
    app.add_handler(MessageHandler(
    filters.Regex("^(اذان|وقت نماز|اوقات شرعی)$") & filters.ChatType.PRIVATE, 
    prayer_command
))

    # ==========================================
    # هندلر مسابقه سرعتی و معمولی
    # ==========================================
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"^مسابقه سرعتی \d+$") & filters.ChatType.GROUPS,
        start_rapid_quiz
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"^مسابقه \d+$") & filters.ChatType.GROUPS,
        start_normal_quiz
    ))
    
    # ==========================================
    # کالبک‌های منو
    # ==========================================
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))
    app.add_handler(CallbackQueryHandler(set_translation_callback, pattern="^set_translation_"))

    # ==========================================
    # کالبک‌های قرآن
    # ==========================================
    app.add_handler(CallbackQueryHandler(surah_page_callback, pattern="^surah_page_"))
    app.add_handler(CallbackQueryHandler(surah_selected_callback, pattern="^surah_\\d+$"))
    app.add_handler(CallbackQueryHandler(ayah_list_page_callback, pattern="^ayahlist_\\d+_\\d+$"))
    app.add_handler(CallbackQueryHandler(ayah_nav_callback, pattern="^ayah_\\d+_\\d+$"))
    app.add_handler(CallbackQueryHandler(fav_ayah_callback, pattern="^fav_ayah_"))
    app.add_handler(CallbackQueryHandler(audio_callback, pattern="^audio_"))

    # ==========================================
    # کالبک‌های احادیث
    # ==========================================
    app.add_handler(CallbackQueryHandler(topic_selected_callback, pattern="^topic_"))
    app.add_handler(CallbackQueryHandler(topic_nav_callback, pattern="^topicnav_"))
    app.add_handler(CallbackQueryHandler(noop_callback, pattern="^noop$"))
    app.add_handler(CallbackQueryHandler(random_hadith_callback, pattern="^hadith_random$"))
    app.add_handler(CallbackQueryHandler(fav_hadith_callback, pattern="^fav_hadith_"))
    app.add_handler(CallbackQueryHandler(hadith_view_callback, pattern="^hadithview_"))

    # ==========================================
    # کالبک‌های نهج‌البلاغه
    # ==========================================
    app.add_handler(CallbackQueryHandler(nahj_menu_callback, pattern="^nahjmenu$"))
    app.add_handler(CallbackQueryHandler(nahj_category_callback, pattern="^nahjcat_"))
    app.add_handler(CallbackQueryHandler(nahj_page_callback, pattern="^nahjpage_"))
    app.add_handler(CallbackQueryHandler(nahj_item_callback, pattern="^nahjitem_"))
    app.add_handler(CallbackQueryHandler(nahj_text_page_callback, pattern="^nahjtxt_"))
    app.add_handler(CallbackQueryHandler(fav_nahj_callback, pattern="^favnahj_"))

    # ==========================================
    # کالبک‌های مفاتیح‌الجنان
    # ==========================================
    app.add_handler(CallbackQueryHandler(mafatih_menu_callback, pattern="^mafmenu$"))
    app.add_handler(CallbackQueryHandler(mafatih_category_callback, pattern="^mafcat_"))
    app.add_handler(CallbackQueryHandler(mafatih_subcategory_callback, pattern="^mafsub_"))
    app.add_handler(CallbackQueryHandler(mafatih_item_callback, pattern="^mafitem_"))
    app.add_handler(CallbackQueryHandler(mafatih_text_page_callback, pattern="^maftxt_"))
    app.add_handler(CallbackQueryHandler(mafatih_audio_callback, pattern="^mafaudio_"))
    app.add_handler(CallbackQueryHandler(fav_mafatih_callback, pattern="^favmaf_"))

    # ==========================================
    # کالبک‌های اوقات شرعی
    # ==========================================
    app.add_handler(CallbackQueryHandler(prayer_city_callback, pattern="^prayer_city_\\d+_\\d+$"))
    app.add_handler(CallbackQueryHandler(prayer_city_list_callback, pattern="^prayer_city_list_\\d+$"))
    app.add_handler(CallbackQueryHandler(prayer_page_callback, pattern="^prayer_page_(prev|next)_\\d+$"))
    app.add_handler(CallbackQueryHandler(prayer_refresh_callback, pattern="^prayer_refresh_\\d+_\\d+$"))
    app.add_handler(CallbackQueryHandler(prayer_location_callback, pattern="^prayer_location_\\d+$"))
    app.add_handler(CallbackQueryHandler(prayer_back_callback, pattern="^prayer_back_\\d+$"))
    app.add_handler(CallbackQueryHandler(prayer_all_cities_callback, pattern="^prayer_all_cities_\\d+$"))
    app.add_handler(CallbackQueryHandler(prayer_reminder_callback, pattern="^prayer_reminder_\\d+$"))
    app.add_handler(CallbackQueryHandler(prayer_reminder_toggle_callback, pattern="^prayer_remind_toggle_(fajr|noon|maghrib)_\\d+$"))
    app.add_handler(CallbackQueryHandler(prayer_reminder_setmin_callback, pattern="^prayer_remind_setmin_\\d+$"))
    # ==========================================
    # کالبک‌های تنظیمات گروه
    # ==========================================
    app.add_handler(CallbackQueryHandler(group_settings_router, pattern="^gset_"))

    # ==========================================
    # کالبک‌های راهنما
    # ==========================================
    app.add_handler(CallbackQueryHandler(help_callback, pattern="^help_"))

    # ==========================================
    # Inline mode
    # ==========================================
    app.add_handler(InlineQueryHandler(inline_query_handler))

    # ==========================================
    # عضویت/خروج اعضا
    # ==========================================
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER,
        member_update_handler,
    ))

    # ==========================================
    # ضداسپم لینک
    # ==========================================
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, link_guard_handler),
        group=1,
    )

    # ==========================================
    # هندلر موقعیت مکانی برای اوقات شرعی
    # ==========================================
    app.add_handler(MessageHandler(filters.LOCATION, prayer_location_handler))

    # ==========================================
    # هندلر پیام‌های متنی
    # ==========================================
    app.add_handler(MessageHandler(filters.Regex("^(مفاتیح الجنان|مفاتیح|📿 مفاتیح الجنان)$"), mafatih_menu_text_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, general_text_handler))

    # ==========================================
    # جاب پست روزانه
    # ==========================================
    if app.job_queue:
        app.job_queue.run_repeating(daily_post_job, interval=3600, first=10)
        # هر روز ساعت ۰۰:۰۵ به وقت تهران، اوقات شرعی امروز رو برای کاربرهایی
        # که یادآور فعال دارن می‌گیره و جاب‌های اون روز رو زمان‌بندی می‌کنه
        app.job_queue.run_daily(
            schedule_daily_prayer_reminders,
            time=dtime(hour=0, minute=5, tzinfo=ZoneInfo("Asia/Tehran")),
        )

    logger.info("Bot started polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()