from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import os
import logging

from database import (
    get_connection,
    get_mafatih_item
)

logger = logging.getLogger(__name__)


# =========================
# منوی اصلی مفاتیح
# =========================

def get_mafatih_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📖 دعای روز شنبه",
                callback_data="mafitem_85"
            )
        ],
        [
            InlineKeyboardButton(
                "📖 دعای روز یکشنبه",
                callback_data="mafitem_86"
            )
        ],
        [
            InlineKeyboardButton(
                "📖 دعای روز دوشنبه",
                callback_data="mafitem_87"
            )
        ],
        [
            InlineKeyboardButton(
                "📖 دعای روز سه شنبه",
                callback_data="mafitem_88"
            )
        ],
        [
            InlineKeyboardButton(
                "📖 دعای روز چهارشنبه",
                callback_data="mafitem_89"
            )
        ],
        [
            InlineKeyboardButton(
                "📖 دعای روز پنجشنبه",
                callback_data="mafitem_90"
            )
        ],
        [
            InlineKeyboardButton(
                "📖 دعای روز جمعه",
                callback_data="mafitem_91"
            )
        ],
        [
            InlineKeyboardButton(
                "🏠 منوی اصلی",
                callback_data="main_menu"
            )
        ]
    ])



# =========================
# ورود به مفاتیح
# =========================

async def mafatih_menu_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        text="📖 مفاتیح الجنان\n\nدعای مورد نظر را انتخاب کنید:",
        reply_markup=get_mafatih_keyboard()
    )



# =========================
# دسته بندی مفاتیح (برای سازگاری با main.py)
# =========================

async def mafatih_category_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        text="📖 مفاتیح الجنان\n\nدعای مورد نظر را انتخاب کنید:",
        reply_markup=get_mafatih_keyboard()
    )


# =========================
# نمایش دعا
# =========================

async def mafatih_item_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    try:

        item_id = query.data.replace(
            "mafitem_",
            ""
        )


        item = get_mafatih_item(item_id)


        if not item:

            await query.edit_message_text(
                "❌ دعا پیدا نشد."
            )

            return



        text = (
            f"✨ {item['title']}\n\n"
        )


        if item["arabic_text"]:

            text += (
                f"{item['arabic_text']}\n\n"
            )


        if item["translation_text"]:

            text += (
                "📖 متن دعا:\n"
                f"{item['translation_text']}\n"
            )


        if item["tafsir_text"]:

            text += (
                "\n💡 توضیح:\n"
                f"{item['tafsir_text']}"
            )



        keyboard = InlineKeyboardMarkup([

            [
                InlineKeyboardButton(
                    "🏠 منوی اصلی مفاتیح",
                    callback_data="mafmenu"
                )
            ]

        ])



        image_path = item["image_path"]



        if image_path:

            if not image_path.startswith("/"):

                image_path = os.path.join(
                    "/app",
                    image_path
                )


            if os.path.exists(image_path):

                with open(image_path, "rb") as photo:

                    await query.message.reply_photo(
                        photo=photo,
                        caption=text[:1024],
                        reply_markup=keyboard
                    )


                return



        await query.edit_message_text(
            text=text[:4096],
            reply_markup=keyboard
        )



    except Exception as e:

        logger.exception(
            "MAFATIH ERROR"
        )


        await query.message.reply_text(
            "❌ خطایی در نمایش دعا رخ داد."
        )