# -*- coding: utf-8 -*-
"""
پنل ادمین گیمیفیکیشن — دستورهای متنی برای مدیریت Mission/Achievement و
بازبینی XP کاربران، بدون نیاز به تغییر کد. همه‌ی دستورها فقط برای
ADMIN_IDS کار می‌کنند (دقیقاً طبق الگوی handlers/admin.py).

دستورها:
    /gamixp <user_id>                                — نمایش XP و ۱۰ تراکنش آخر یک کاربر
    /gamitop                                          — کاربرانی که امروز بیشترین XP گرفته‌اند
    /gamimissions                                     — لیست همه‌ی مأموریت‌ها
    /gamimission_new <code> <daily|weekly> <condition_type> <condition_value> <xp_reward> <title...>
    /gamimission_toggle <code> <on|off>
    /gamiachievements                                 — لیست همه‌ی دستاوردها
    /gamiachievement_new <code> <condition_type> <condition_value> <xp_reward> <icon> <name...>
    /gamiachievement_toggle <code> <on|off>
"""

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from text_utils import to_persian_digits
from . import admin_db
from .config import ANTI_ABUSE_RULES


def _is_admin(update: Update) -> bool:
    return update.effective_user and update.effective_user.id in ADMIN_IDS


async def gami_xp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        return
    if not context.args:
        await update.message.reply_text("استفاده: /gamixp <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("user_id باید عدد باشد.")
        return

    summary = admin_db.get_user_admin_summary(target_id)
    if not summary:
        await update.message.reply_text("این کاربر هنوز پروفایل گیمیفیکیشن ندارد.")
        return

    p = summary["profile"]
    lines = [
        f"👤 کاربر {target_id}",
        f"⭐ XP: {to_persian_digits(p['xp'])} | سطح: {to_persian_digits(p['level'])}",
        f"🔥 استمرار: {to_persian_digits(p['current_streak'])} (بهترین: {to_persian_digits(p['longest_streak'])})",
        f"📖 قرآن: {to_persian_digits(p['total_quran_read'])} | 📚 حدیث: {to_persian_digits(p['total_hadith_read'])}",
        "",
        "🧾 ۱۰ تراکنش آخر:",
    ]
    for t in summary["transactions"]:
        lines.append(f"  +{to_persian_digits(t['xp'])} — {t['event_type']} ({t['created_at']})")

    await update.message.reply_text("\n".join(lines))


async def gami_top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        return
    rows = admin_db.get_top_xp_earners_today(10)
    if not rows:
        await update.message.reply_text("امروز هنوز XP ای ثبت نشده.")
        return
    lines = ["📊 پرکارترین‌های امروز:", ""]
    for i, r in enumerate(rows, 1):
        lines.append(f"{to_persian_digits(i)}. کاربر {r['user_id']} — {to_persian_digits(r['xp_today'])} XP ({to_persian_digits(r['events_today'])} رویداد)")
    await update.message.reply_text("\n".join(lines))


async def gami_missions_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        return
    missions = admin_db.list_missions()
    if not missions:
        await update.message.reply_text("هیچ مأموریتی تعریف نشده.")
        return
    lines = ["🎯 مأموریت‌ها:", ""]
    for m in missions:
        status = "✅ فعال" if m["active"] else "⛔ غیرفعال"
        lines.append(
            f"[{m['code']}] {m['mission_type']} — {m['title']} "
            f"({m['condition_type']}≥{m['condition_value']}, +{m['xp_reward']} XP) {status}"
        )
    await update.message.reply_text("\n".join(lines))


async def gami_mission_new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        return
    args = context.args
    if len(args) < 6:
        valid_conditions = ", ".join(ANTI_ABUSE_RULES.keys())
        await update.message.reply_text(
            "استفاده:\n"
            "/gamimission_new <code> <daily|weekly> <condition_type> <condition_value> <xp_reward> <عنوان...>\n\n"
            f"condition_type های معتبر: {valid_conditions}"
        )
        return

    code, mtype, cond_type, cond_value_s, xp_s = args[0], args[1], args[2], args[3], args[4]
    title = " ".join(args[5:])
    try:
        cond_value = int(cond_value_s)
        xp = int(xp_s)
    except ValueError:
        await update.message.reply_text("condition_value و xp_reward باید عدد باشند.")
        return

    ok, msg = admin_db.create_mission(code, mtype, title, cond_type, cond_value, xp)
    await update.message.reply_text(("✅ " if ok else "❌ ") + msg)


async def gami_mission_toggle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        return
    if len(context.args) != 2 or context.args[1].lower() not in ("on", "off"):
        await update.message.reply_text("استفاده: /gamimission_toggle <code> <on|off>")
        return
    code, state = context.args[0], context.args[1].lower() == "on"
    changed = admin_db.set_mission_active(code, state)
    await update.message.reply_text("✅ انجام شد." if changed else "❌ مأموریتی با این code پیدا نشد.")


async def gami_achievements_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        return
    achievements = admin_db.list_achievements()
    if not achievements:
        await update.message.reply_text("هیچ دستاوردی تعریف نشده.")
        return
    lines = ["🏅 دستاوردها:", ""]
    for a in achievements:
        status = "✅ فعال" if a["active"] else "⛔ غیرفعال"
        secret = " 🔒مخفی" if a["is_secret"] else ""
        lines.append(
            f"[{a['code']}] {a['icon']} {a['name']} "
            f"({a['condition_type']}≥{a['condition_value']}, +{a['xp_reward']} XP) {status}{secret}"
        )
    await update.message.reply_text("\n".join(lines))


async def gami_achievement_new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        return
    args = context.args
    if len(args) < 6:
        valid_conditions = ", ".join(list(ANTI_ABUSE_RULES.keys()) + ["current_streak", "longest_streak", "quiz_correct_total"])
        await update.message.reply_text(
            "استفاده:\n"
            "/gamiachievement_new <code> <condition_type> <condition_value> <xp_reward> <icon> <نام...>\n\n"
            f"condition_type های معتبر: {valid_conditions}"
        )
        return

    code, cond_type, cond_value_s, xp_s, icon = args[0], args[1], args[2], args[3], args[4]
    name = " ".join(args[5:])
    try:
        cond_value = int(cond_value_s)
        xp = int(xp_s)
    except ValueError:
        await update.message.reply_text("condition_value و xp_reward باید عدد باشند.")
        return

    ok, msg = admin_db.create_achievement(code, name, name, icon, cond_type, cond_value, xp)
    await update.message.reply_text(("✅ " if ok else "❌ ") + msg)


async def gami_achievement_toggle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        return
    if len(context.args) != 2 or context.args[1].lower() not in ("on", "off"):
        await update.message.reply_text("استفاده: /gamiachievement_toggle <code> <on|off>")
        return
    code, state = context.args[0], context.args[1].lower() == "on"
    changed = admin_db.set_achievement_active(code, state)
    await update.message.reply_text("✅ انجام شد." if changed else "❌ دستاوردی با این code پیدا نشد.")
