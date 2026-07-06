import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, InlineQueryHandler, filters, ContextTypes,
)

from config import BOT_TOKEN, PROXY_URL
from database import init_db

from handlers.start import start_command, menu_callback, set_translation_callback
from handlers.quran import (
    surah_page_callback, surah_selected_callback, ayah_nav_callback,
    fav_ayah_callback, tafsir_callback, ayah_direct_lookup,
)
from handlers.hadith import (
    topic_selected_callback, random_hadith_callback, fav_hadith_callback,
    add_hadith_command, text_search_handler,
)
from handlers.inline import inline_query_handler
from handlers.admin import (
    group_settings_command, toggle_daily_post_callback,
    group_send_now_callback, daily_post_job,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی ربات به یک گروه جدید اضافه می‌شود، پیام معرفی بفرستد."""
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            await update.message.reply_text(
                "سلام 🌙\n"
                "از اضافه کردن من به این گروه خوشحالم!\n\n"
                "برای دیدن قابلیت‌های گروهی از دستور /groupsettings استفاده کنید "
                "(فقط ادمین‌ها).\n"
                "برای جستجوی سریع، کافیست بنویسید:\n"
                "`@نام_ربات صبر` یا `@نام_ربات 2:255`\n\n"
                "همچنین می‌توانید در چت خصوصی من /start را بزنید تا از منوی کامل استفاده کنید.",
                parse_mode="Markdown",
            )


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


def main():
    init_db()

    builder = Application.builder().token(BOT_TOKEN)

    if PROXY_URL:
        # برای هاست‌های ایرانی که به تلگرام دسترسی مستقیم ندارند.
        # هم درخواست‌های عادی و هم دریافت آپدیت‌ها (polling) باید از پروکسی رد شوند.
        builder = builder.proxy(PROXY_URL).get_updates_proxy(PROXY_URL)
        logger.info("در حال استفاده از پروکسی: %s", PROXY_URL)

    app = builder.build()

    # دستورات
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("addhadith", add_hadith_command))
    app.add_handler(CommandHandler("groupsettings", group_settings_command))

    # کالبک‌های منو
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))
    app.add_handler(CallbackQueryHandler(set_translation_callback, pattern="^set_translation_"))

    # کالبک‌های قرآن
    app.add_handler(CallbackQueryHandler(surah_page_callback, pattern="^surah_page_"))
    app.add_handler(CallbackQueryHandler(surah_selected_callback, pattern="^surah_\\d+$"))
    app.add_handler(CallbackQueryHandler(ayah_nav_callback, pattern="^ayah_\\d+_\\d+$"))
    app.add_handler(CallbackQueryHandler(fav_ayah_callback, pattern="^fav_ayah_"))
    app.add_handler(CallbackQueryHandler(tafsir_callback, pattern="^tafsir_"))

    # کالبک‌های احادیث
    app.add_handler(CallbackQueryHandler(topic_selected_callback, pattern="^topic_"))
    app.add_handler(CallbackQueryHandler(random_hadith_callback, pattern="^hadith_random$"))
    app.add_handler(CallbackQueryHandler(fav_hadith_callback, pattern="^fav_hadith_"))

    # کالبک‌های تنظیمات گروه
    app.add_handler(CallbackQueryHandler(toggle_daily_post_callback, pattern="^toggle_daily_post$"))
    app.add_handler(CallbackQueryHandler(group_send_now_callback, pattern="^group_send_now$"))

    # inline mode
    app.add_handler(InlineQueryHandler(inline_query_handler))

    # عضویت ربات در گروه جدید
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))

    # پیام‌های متنی عادی (فقط چت خصوصی)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, general_text_handler))

    # جاب پست روزانه - هر ساعت یکبار چک می‌کند
    if app.job_queue:
        app.job_queue.run_repeating(daily_post_job, interval=3600, first=10)

    logger.info("Bot started polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
