import logging
from datetime import time as dtime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, InlineQueryHandler, ChatMemberHandler, TypeHandler,
    filters, ContextTypes,
)
from telegram.request import HTTPXRequest

from config import BOT_TOKEN, PROXY_URL, ADMIN_IDS
from database import init_db, ensure_search_index

from handlers.start import start_command, menu_callback, set_translation_callback, clear_keyboard_command
from handlers.ownership import ownership_guard_callback
from handlers.quran import (
    surah_page_callback, surah_selected_callback, ayah_nav_callback,
    fav_ayah_callback, tafsir_callback, ayah_direct_lookup, add_quran_tafsir_command,
    audio_callback, ayah_list_page_callback, surah_name_ayah_lookup,
    quran_search_info_callback,
)
from handlers.hadith import (
    show_categories,
    category_selected_callback,
    category_nav_callback,
    category_menu_callback,
    topic_selected_callback, random_hadith_callback, fav_hadith_callback,
    topic_nav_callback, noop_callback,
    add_hadith_command, text_search_handler, add_tafsir_command,
    find_hadith_command, edit_hadith_command, del_hadith_command,
    hadith_view_callback,
    search_exit_callback, search_back_callback, search_start_callback,
    id_search_callback, id_search_handler, clear_favorites_callback,
    show_favorites, copy_hadith_callback, filter_source_callback,
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
    bot_chat_member_update_handler, bot_stats_command, track_user_activity,
)
from handlers.quiz import (
    quiz_command, quiz_menu_callback, quiz_category_callback, quiz_answer_callback,
    leaderboard_command, global_leaderboard_command, my_quiz_stats_command,
    add_quiz_command, quiz_settings_command, quiz_time_command,
    quiz_buzzer_command, quiz_next_delay_command, start_rapid_quiz,
    start_normal_quiz, 
)
from handlers.help import help_command, help_callback
from handlers.gamification import (
    missions_command, missions_callback,
    achievements_command, achievements_callback,
    leaderboard_gamification_command, leaderboard_gamification_callback,
)
from gamification.admin_commands import (
    gami_xp_command, gami_top_command,
    gami_missions_list_command, gami_mission_new_command, gami_mission_toggle_command,
    gami_achievements_list_command, gami_achievement_new_command, gami_achievement_toggle_command,
)
from handlers.prayer import (
    prayer_command, prayer_city_callback, prayer_city_list_callback,
    prayer_page_callback, prayer_refresh_callback, prayer_location_callback,
    prayer_location_handler, prayer_back_callback, prayer_all_cities_callback,
    prayer_reminder_callback, prayer_reminder_toggle_callback,
    prayer_reminder_setmin_callback, prayer_reminder_minutes_text_handler,
    schedule_daily_prayer_reminders, prayer_test_reminder_command,
)
from handlers.azan_announce import (
    azan_setup_router, set_azan_audio_command, azan_audio_upload_handler,
    azan_audio_pending_filter, schedule_daily_azan_announcements,
    handle_incoming_azan_panel_message,
)
from handlers.madahi import (
    madahi_command, madahi_type_callback, madahi_back_types_callback,
    madahi_category_callback, madahi_occasion_callback, madahi_page_callback,
    madahi_play_callback,
    add_madahi_command, delete_madahi_command, madahi_stats_command,
    madahi_add_start_callback, madahi_add_text_handler, madahi_add_audio_handler,
    madahi_pending_text_filter, madahi_pending_audio_filter,
)
from handlers.salavat import (
    salavat_text_handler,
    salavat_stats_command,
    salavat_top_command,
    salavat_goal_command,
    salavat_goal_pick_callback,
    salavat_delete_command,
    salavat_delete_pick_callback,
    salavat_global_command,
    salavat_count_command,
    salavat_home_callback,
)
from handlers.pigeon import pigeon_text_handler, pigeon_harvest_callback, pigeon_levelup_callback

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
    # پیام‌های ویرایش‌شده (edited_message) و بعضی آپدیت‌های خاص، update.message
    # ندارن (None هست)؛ بدون این گارد، خط بعدی با AttributeError کرش می‌کنه.
    if not update.message or not update.message.text:
        return

    # پیام inline «اعلام اذان» که تازه وارد یه گروه شده: باید پاک و با یه
    # پیام واقعیِ ربات جایگزین بشه، وگرنه دکمه‌هاش کار نمی‌کنن (پیام‌های
    # inline از دید تلگرام chat_id مشخصی روی callback نمی‌ذارن). این چک
    # باید همین اول (قبل از هر پردازش دیگه) انجام بشه.
    if await handle_incoming_azan_panel_message(update, context):
        return

    text = update.message.text.strip()
    is_private = update.effective_chat.type == "private"

    # «جستجو با شناسه حدیث»: وقتی کاربر در حالت id_search_mode باشه، پیام بعدیش
    # باید اینجا گرفته بشه. این چک باید قبل از صلوات/آیه/سرچ باشه، چون هندلر
    # ثبت‌شده‌ی id_search_handler (هم‌فیلتر با general_text_handler) هرگز
    # اجرا نمی‌شه — PTB بعد از اولین هندلرِ match شده متوقف می‌شه.
    if is_private and context.user_data.get("id_search_mode"):
        await id_search_handler(update, context)
        return

    # صلوات‌شمار گروهی: مستقل از بقیه‌ی جریان‌ها، چون با آیه/سرچ تداخلی نداره.
    # توی try/except چون اگه اینجا یه خطای پیش‌بینی‌نشده بیفته (مثلاً توی
    # فرستادن پیام تبریک رکورد)، نباید جلوی رسیدن به بخش یادآور/سرچ رو بگیره.
    try:
        await salavat_text_handler(update, context)
    except Exception as e:
        logger.error(f"خطای مدیریت‌نشده در صلوات‌شمار: {e}")

    # شخصیت همراه (کبوتر): صلوات/نذری/کبوترم -- «نذری» و «کبوترم» هم تو
    # پیوی هم تو گروه کار می‌کنن. «صلوات» رو خودِ pigeon_text_handler فقط
    # تو پیوی award می‌کنه؛ تو گروه، صلوات‌شمار بالا (salavat_text_handler)
    # خودش هم award کرده هم کارت رو فرستاده، پس اینجا برای «صلوات» تو
    # گروه کاری انجام نمی‌شه (داخل خود تابع این تفکیک انجام می‌شه).
    try:
        if await pigeon_text_handler(update, context, text):
            return
    except Exception as e:
        logger.error(f"خطای مدیریت‌نشده در کبوتر: {e}")

    consumed_by_reminder = await prayer_reminder_minutes_text_handler(update, context)
    if consumed_by_reminder:
        return

    search_mode = context.user_data.get("search_mode", False)

    handled = await ayah_direct_lookup(update, context, text)
    if not handled:
        handled = await surah_name_ayah_lookup(update, context, text)

    if not handled and is_private and search_mode:
        await text_search_handler(update, context, text)


async def debug_custom_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تابع کمکی موقت برای استخراج custom_emoji_id از پیام‌های ادمین.
    فقط برای ADMIN_IDS کار می‌کنه تا کاربرهای عادی چیزی نبینن. توی یه
    group مستقل (-5) ثبت شده، پس مستقل از بقیه‌ی هندلرها اجرا می‌شه.
    از parse_entities استفاده می‌کنیم (نه اسلایس دستی روی update.message.text)
    چون آفست/طول entities بر اساس UTF-16 حساب می‌شه و اسلایس دستی پایتون
    وقتی چند ایموجی سفارشی پشت‌سرهم باشن، غلط از آب درمیاد.
    کار تمام شد؟ کافیه دو خط ثبتش (پایین‌تر در main()) رو کامنت/حذف کنی."""
    if not update.message or update.effective_user.id not in ADMIN_IDS:
        return

    entities = update.message.parse_entities(types=["custom_emoji"])
    if not entities:
        return

    lines = []
    for entity, emoji_slice in entities.items():
        lines.append(f"{emoji_slice} → `{entity.custom_emoji_id}`")

    await update.message.reply_text(
        "🔎 *custom_emoji_id پیدا شده:*\n" + "\n".join(lines),
        parse_mode="Markdown",
    )


async def get_file_id_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تابع کمکی برای دیباگ و استخراج راحتِ file_id فایل‌های صوتی، صوتی شخصی، ویدیو و اسناد.
    فقط برای ادمین‌ها کار می‌کنه تا file_id فایل‌ها به کاربرهای عادی لو نره."""
    if not update.message:
        return
    if update.effective_user.id not in ADMIN_IDS:
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

    from gamification.missions import seed_default_missions
    from gamification.achievements import seed_default_achievements
    from gamification.leaderboard import ensure_xp_index
    seed_default_missions()
    seed_default_achievements()
    ensure_xp_index()

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
        # آدرس کامل پروکسی لاگ نمی‌شود چون ممکن است شامل user:pass باشد؛
        # روی سرور مشترک این می‌تواند در فایل لاگ لو برود.
        logger.info("پروکسی برای اتصال به تلگرام فعال است.")

    app = builder.build()

    async def _global_error_handler(update, context):
        logger.exception("خطای مدیریت‌نشده در پردازش آپدیت", exc_info=context.error)

    app.add_error_handler(_global_error_handler)

    app.add_handler(CallbackQueryHandler(ownership_guard_callback), group=-10)

    # هندلر موقت دیباگ: پیدا کردن custom_emoji_id برای ایموجی‌های سفارشی
    # (فقط برای ادمین‌ها جواب می‌ده). توی group=-5 مستقل از بقیه‌ی
    # هندلرهای متنی ثبت شده تا هیچ تداخلی با general_text_handler و بقیه
    # نداشته باشه. بعد از اینکه آی‌دی‌های لازم رو گرفتی، این خط رو حذف کن.
    app.add_handler(MessageHandler(filters.ALL, debug_custom_emoji), group=-5)

    # ==========================================
    # دستورات
    # ==========================================
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("botstats", bot_stats_command))
    app.add_handler(CommandHandler("missions", missions_command))
    app.add_handler(CommandHandler("achievements", achievements_command))
    app.add_handler(CommandHandler("rank", leaderboard_gamification_command))
    app.add_handler(CallbackQueryHandler(missions_callback, pattern="^gami_missions$"))
    app.add_handler(CallbackQueryHandler(achievements_callback, pattern="^gami_achievements$"))
    app.add_handler(CallbackQueryHandler(leaderboard_gamification_callback, pattern="^gami_leaderboard$"))

    # پنل ادمین گیمیفیکیشن (فقط ADMIN_IDS؛ هر کدام از دستورها خودشان چک می‌کنند)
    app.add_handler(CommandHandler("gamixp", gami_xp_command))
    app.add_handler(CommandHandler("gamitop", gami_top_command))
    app.add_handler(CommandHandler("gamimissions", gami_missions_list_command))
    app.add_handler(CommandHandler("gamimission_new", gami_mission_new_command))
    app.add_handler(CommandHandler("gamimission_toggle", gami_mission_toggle_command))
    app.add_handler(CommandHandler("gamiachievements", gami_achievements_list_command))
    app.add_handler(CommandHandler("gamiachievement_new", gami_achievement_new_command))
    app.add_handler(CommandHandler("gamiachievement_toggle", gami_achievement_toggle_command))
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
    # باید قبل از هندلر عمومی زیر ثبت بشه: توی PTB اولین هندلرِ هم‌گروهی که
    # فیلترش match کنه انتخاب می‌شه، پس وقتی ادمینی وسط ویزارد افزودن مداحی
    # و منتظر فایل صوتیه، این یکی جلوی mafatih_audio_upload_handler رو
    # می‌گیره؛ در غیر این صورت (فیلترش False باشه) هندلر بعدی طبق روال قبل کار می‌کنه.
    app.add_handler(MessageHandler((filters.AUDIO | filters.VOICE) & madahi_pending_audio_filter, madahi_add_audio_handler))
    app.add_handler(MessageHandler((filters.AUDIO | filters.VOICE) & azan_audio_pending_filter, azan_audio_upload_handler))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, mafatih_audio_upload_handler))

    # ثبت توی یه group جدا (group=1) تا با هندلر بالا (که برای آپلود صوت
    # مفاتیح‌الجنانه) تداخل نکنه؛ توی PTB هر group مستقل از بقیه پردازش
    # می‌شه، پس همون فایل هم به مافاتیح می‌ره هم دیباگش (فقط برای ادمین) چاپ می‌شه.
    app.add_handler(
        MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.ALL | filters.VIDEO, get_file_id_debug),
        group=1,
    )

    # ==========================================
    # دستورات اوقات شرعی
    # ==========================================
    app.add_handler(CommandHandler("prayer", prayer_command))
    app.add_handler(CommandHandler("prayer_test_reminder", prayer_test_reminder_command))
    app.add_handler(CommandHandler("setazanaudio", set_azan_audio_command))

    # ==========================================
    # دستورات مداحی و مولودی
    # ==========================================
    app.add_handler(CommandHandler("madahi", madahi_command))
    app.add_handler(CommandHandler("addmadahi", add_madahi_command))
    app.add_handler(CommandHandler("delmadahi", delete_madahi_command))
    app.add_handler(CommandHandler("madahistats", madahi_stats_command))

    # ویزارد افزودن سریع مداحی از توی خودِ منو (دکمه‌ی «➕ افزودن مداحی به
    # این مناسبت»). هندلر متنی‌اش پایین‌تر، کنار general_text_handler ثبت شده.
    app.add_handler(CallbackQueryHandler(madahi_add_start_callback, pattern="^madahi_addstart_"))

    # پاسخ به پیام "مداحی"/"مولودی" در چت خصوصی (بدون اسلش)
    app.add_handler(MessageHandler(
        filters.Regex("^(مداحی|مولودی|🎙 مداحی و مولودی)$") & filters.ChatType.PRIVATE,
        madahi_command
    ))

    # پاسخ به پیام "اذان" در چت خصوصی (بدون اسلش)
    app.add_handler(MessageHandler(
        filters.Regex("^(اذان|وقت نماز|اوقات شرعی)$") & filters.ChatType.PRIVATE, 
        prayer_command
    ))

    # ==========================================
    # دستورات صلوات‌شمار گروهی
    # ==========================================
    app.add_handler(CommandHandler("salavat", salavat_stats_command))
    app.add_handler(CommandHandler("salavat_top", salavat_top_command))
    app.add_handler(CommandHandler("salavat_goal", salavat_goal_command))
    app.add_handler(CommandHandler("salavat_delete", salavat_delete_command))
    app.add_handler(CommandHandler("salavat_global", salavat_global_command))
    app.add_handler(CommandHandler("salavat_count", salavat_count_command))
    app.add_handler(CallbackQueryHandler(salavat_goal_pick_callback, pattern="^(salgoal_|salskip_)"))
    app.add_handler(CallbackQueryHandler(salavat_delete_pick_callback, pattern="^salrm"))
    app.add_handler(CallbackQueryHandler(salavat_home_callback, pattern="^salhome_"))

    # ==========================================
    # شخصیت همراه (کبوتر)
    # ==========================================
    app.add_handler(CallbackQueryHandler(pigeon_harvest_callback, pattern=r"^pigeon_harvest:\d+$"))
    app.add_handler(CallbackQueryHandler(pigeon_levelup_callback, pattern=r"^pigeon_levelup:\d+$"))

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
    app.add_handler(CallbackQueryHandler(quran_search_info_callback, pattern="^quran_search_info$"))

    # ==========================================
    # کالبکهای احادیث - سیستم جدید دسته‌بندی
    # ==========================================
    app.add_handler(CallbackQueryHandler(show_categories, pattern="^menu_hadith_categories$"))
    app.add_handler(CallbackQueryHandler(category_selected_callback, pattern="^category_[a-f0-9]{12}$"))
    app.add_handler(CallbackQueryHandler(category_nav_callback, pattern="^catnav_"))
    app.add_handler(CallbackQueryHandler(category_menu_callback, pattern="^cat_menu_"))

    # ==========================================
    # کالبکهای احادیث - سیستم قدیمی (سازگاری)
    # ==========================================
    app.add_handler(CallbackQueryHandler(topic_selected_callback, pattern="^topic_[a-f0-9]{12}$"))
    app.add_handler(CallbackQueryHandler(topic_nav_callback, pattern="^topicnav_"))
    app.add_handler(CallbackQueryHandler(noop_callback, pattern="^noop$"))
    app.add_handler(CallbackQueryHandler(random_hadith_callback, pattern="^hadith_random$"))
    app.add_handler(CallbackQueryHandler(fav_hadith_callback, pattern="^fav_hadith_"))
    app.add_handler(CallbackQueryHandler(hadith_view_callback, pattern="^hadithview_"))
    app.add_handler(CallbackQueryHandler(search_exit_callback, pattern="^search_exit$"))
    app.add_handler(CallbackQueryHandler(search_back_callback, pattern="^search_back$"))
    app.add_handler(CallbackQueryHandler(search_start_callback, pattern="^search_start_"))
    app.add_handler(CallbackQueryHandler(id_search_callback, pattern="^id_search_hadith$"))
    app.add_handler(CallbackQueryHandler(clear_favorites_callback, pattern="^clear_favorites$"))
    app.add_handler(CallbackQueryHandler(show_favorites, pattern="^show_favorites$"))
    app.add_handler(CallbackQueryHandler(copy_hadith_callback, pattern="^copy_hadith_"))
    app.add_handler(CallbackQueryHandler(filter_source_callback, pattern="^filter_source_"))

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
    # کالبک‌های اعلام اذان در گروه
    # ==========================================
    app.add_handler(CallbackQueryHandler(azan_setup_router, pattern="^azangrp_"))

    # ==========================================
    # کالبک‌های مداحی و مولودی
    # ==========================================
    app.add_handler(CallbackQueryHandler(madahi_type_callback, pattern="^madahi_type_(madahi|molodi)$"))
    app.add_handler(CallbackQueryHandler(madahi_back_types_callback, pattern="^madahi_back_types$"))
    app.add_handler(CallbackQueryHandler(madahi_category_callback, pattern="^madahi_cat_(madahi|molodi)_\\d+(-\\d+)*$"))
    app.add_handler(CallbackQueryHandler(madahi_occasion_callback, pattern="^madahi_occ_(madahi|molodi)_\\d+(-\\d+)*$"))
    app.add_handler(CallbackQueryHandler(madahi_page_callback, pattern="^madahi_page_(madahi|molodi)_\\d+(-\\d+)*_\\d+$"))
    app.add_handler(CallbackQueryHandler(madahi_play_callback, pattern="^madahi_play_\\d+$"))

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

    # ردیابی مطمئنِ اضافه/حذف شدن خودِ ربات از هر چت (گروه/سوپرگروه/کانال)؛
    # پایه‌ی دستور ادمین /botstats. برخلاف هندلر بالا (که فقط پیام سرویسِ
    # داخل گروه رو می‌بینه)، my_chat_member رو تلگرام همیشه و مستقیم برای
    # خودِ ربات می‌فرسته، حتی اگه اضافه/حذف شدن از طریق لینک یا بلاک باشه.
    app.add_handler(ChatMemberHandler(bot_chat_member_update_handler, ChatMemberHandler.MY_CHAT_MEMBER))

    # ثبت خاموشِ کاربرهای واقعی (برای شمارش «چند نفر از ربات استفاده
    # می‌کنن» در /botstats). group=-1 یعنی مستقل و قبل از بقیه‌ی هندلرها
    # اجرا می‌شه و جلوی هیچ‌کدوم از هندلرهای دیگه رو نمی‌گیره.
    app.add_handler(TypeHandler(Update, track_user_activity), group=-1)

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
    # هندلر پیامهای متنی
    # ==========================================
    # باید قبل از general_text_handler ثبت بشه؛ فیلترش فقط وقتی True میشه که
    # فرستنده وسط ویزارد افزودن مداحی باشه (مرحلهی عنوان یا اسم مداح)، پس
    # برای بقیهی کاربران هیچ تغییری توی رفتار general_text_handler ایجاد نمیشه.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & madahi_pending_text_filter, madahi_add_text_handler))
    app.add_handler(MessageHandler(filters.Regex("^(مفاتیح الجنان|مفاتیح|📿 مفاتیح الجنان)$"), mafatih_menu_text_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, general_text_handler))
    # هندلر جستجو با شناسه حدیث
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, id_search_handler))

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
        # جاب‌های یادآور اذان (run_once) فقط توی حافظه‌ی همین پروسه نگه داشته
        # می‌شن، نه توی دیتابیس. یعنی هر بار که پروسه ری‌استارت بشه (مثلاً
        # redeploy یا کرش روی هاست)، هر جابی که قبلاً برای امروز زمان‌بندی
        # شده بود از بین می‌ره و تا ساعت ۰۰:۰۵ فردا شب دوباره ساخته نمی‌شه.
        # برای همین همین لحظه‌ی استارت‌آپ هم یه بار زمان‌بندیِ باقی‌مونده‌ی
        # امروز رو از نو می‌سازیم تا این وسط چیزی از دست نره.
        app.job_queue.run_once(schedule_daily_prayer_reminders, when=5)

        # اعلام اذان گروهی: هر روز ساعت ۰۰:۱۰ به وقت تهران، زمان‌بندی امروز رو
        # برای همه‌ی گروه‌هایی که این قابلیت را فعال کرده‌اند می‌سازد؛ و یک بار
        # هم موقع استارت‌آپ (برای جبران ری‌استارت وسط روز)، شبیه یادآور اذان.
        app.job_queue.run_daily(
            schedule_daily_azan_announcements,
            time=dtime(hour=0, minute=10, tzinfo=ZoneInfo("Asia/Tehran")),
        )
        app.job_queue.run_once(schedule_daily_azan_announcements, when=8)
    else:
        logger.error(
            "⚠️ app.job_queue خالیه! پست روزانه و یادآور اذان هرگز اجرا نمی‌شن. "
            "این یعنی پکیج job-queue نصب نیست -- روی سرور بزن: "
            "pip install \"python-telegram-bot[job-queue]\" و ربات رو ری‌استارت کن."
        )

    logger.info("Bot started polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()