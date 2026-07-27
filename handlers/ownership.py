"""
ابزار سبک برای محدود کردن دسترسی به دکمه‌های زیرِ پیام‌هایی که در یک گروه،
به درخواست یک کاربر خاص ساخته شده‌اند (مثلاً وقتی کسی در گروه می‌نویسد
«بقره 5» و ربات آیه را با دکمه‌های ناوبری برایش می‌فرستد).

فقط همان کاربر باید بتواند دکمه‌های آن پیام (آیه بعد/قبل، لیست آیات، لیست
سوره‌ها، حتی اگر تا منوی اصلی ربات هم جلو برود) را بزند؛ نه بقیه‌ی اعضای
گروه، حتی ادمین‌ها.

پیاده‌سازی: یک دیکشنری در حافظه که (chat_id, message_id) را به user_id
صاحب آن پیام نگاشت می‌کند، به‌علاوه یک CallbackQueryHandler عمومی که با
بالاترین اولویت (group=-10) روی همه‌ی callback ها اجرا می‌شود و اگر پیام
صاحب داشته باشد ولی کلیک‌کننده صاحبش نباشد، ادامه‌ی پردازش را متوقف می‌کند.

این دیکشنری در حافظه است (نه دیتابیس) چون فقط برای طول عمر یک session
تعامل لازم است؛ با ری‌استارت ربات پاک می‌شود که مشکلی ایجاد نمی‌کند.
"""

from collections import OrderedDict
from telegram.ext import ApplicationHandlerStop

# (chat_id, message_id) -> user_id
_OWNERS: "OrderedDict[tuple, int]" = OrderedDict()
MAX_TRACKED = 5000

GROUP_CHAT_TYPES = ("group", "supergroup")


def register_owner(chat_id: int, message_id: int, user_id: int):
    """ثبت اینکه این پیام مخصوص کدام کاربر است."""
    key = (chat_id, message_id)
    _OWNERS[key] = user_id
    _OWNERS.move_to_end(key)
    if len(_OWNERS) > MAX_TRACKED:
        _OWNERS.popitem(last=False)  # قدیمی‌ترین را حذف کن تا حافظه نترکد


def get_owner(chat_id: int, message_id: int):
    return _OWNERS.get((chat_id, message_id))


async def ownership_guard_callback(update, context):
    """
    اولین هندلری که برای هر callback query اجرا می‌شود (group=-10).
    اگر پیام مربوطه صاحب ثبت‌شده‌ای دارد و کاربر کلیک‌کننده همان صاحب نیست،
    با یک هشدار کوتاه جلوی ادامه‌ی پردازش (رفتن به هندلرهای دیگر) را می‌گیرد.
    """
    query = update.callback_query
    if not query or not query.message:
        return  # پیام‌های ارسال‌شده از نتایج اینلاین، chat/message_id مشخصی ندارند

    chat = update.effective_chat
    if not chat or chat.type not in GROUP_CHAT_TYPES:
        return  # این محدودیت فقط داخل گروه‌ها معنا دارد

    owner_id = get_owner(chat.id, query.message.message_id)
    if owner_id is None:
        return  # این پیام اصلاً جزو پیام‌های «مخصوص یک کاربر» نیست

    if query.from_user.id != owner_id:
        await query.answer(
            "⛔ این فقط برای کسی است که این مطلب را درخواست داده. "
            "خودتان می‌توانید مثلاً بنویسید «بقره 5» تا برایتان باز شود.",
            show_alert=True,
        )
        raise ApplicationHandlerStop
