import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from config import Config
from services.join_stats_db import (
    register_join_user, has_user_joined, get_join_count, get_all_unique_counts
)

logger = logging.getLogger(__name__)

# Короткие имена групп! Только username чата/канала без https://t.me/
GROUPS = {
    "chat": {
        "link": "tgchatxxx",
        "title": "🙅‍♀️ Будапешт - чат",
        "desc": "Главный чат русскоязычной Будапешт-комьюнити.",
        "id": -1002919380244,
    },
    "public": {
        "link": "snghu",
        "title": "🙅‍♂️ Будапешт",
        "desc": "Публикационный канал новостей и объявлений.",
        "id": -1002743668534,
    },
    "catalog": {
        "link": "catalogtrix",
        "title": "🙅 Каталог услуг Будапешт",
        "desc": "Каталог услуг, мастеров, специалистов.",
        "id": -1002601716810,
    },
    "marketplace": {
        "link": "hungarytrade",
        "title": "🕵🏻‍♀️ Будапешт Куплю/Отдам/Продам",
        "desc": "Маркетплейс венгерской комьюнити.",
        "id": -1003033694255,
    },
    "citytoppeople": {
        "link": "socialuck",
        "title": "🏆 Top Budapest 📱 Social 👩🏼‍❤️‍👨🏻 Люди Будапешт",
        "desc": "Лучшие люди и знакомства города!",
        "id": -1003088023508,
    },
    "citypartners": {
        "link": "budapestpartners",
        "title": "Budapest 📳 Partners",
        "desc": "Партнеры и бизнес-связи.",
        "id": -1003033694255,
    },
    "budapesocial": {
        "link": "budapesocial",
        "title": "BudaPes🦄",
        "desc": "Социальный чат и обмен опытом.",
        "id": -1003114019170,
    },
}

def _is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and Config.is_admin(user.id))

# ============ КРАСИВОЕ МЕНЮ /join ============
async def join_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = await get_all_unique_counts()
    text = "💬 Выберите группу для вступления:\n\n"
    for key, group in GROUPS.items():
        count = stats.get(key, 0)
        text += f"• <b>{group['title']}</b> — <i>{count} уникальных участников</i>\n"
    keyboard = []
    for key, group in GROUPS.items():
        join_btn = InlineKeyboardButton(
            f"🔗 Войти", url=f"https://t.me/{group['link']}?start={user_id}_{key}"
        )
        desc_btn = InlineKeyboardButton(
            "ℹ️ Описание", callback_data=f"join_desc:{key}"
        )
        keyboard.append([join_btn, desc_btn])
    markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text(
        text,
        reply_markup=markup,
        parse_mode="HTML"
    )

# ============ Описание группы ============
async def handle_desc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data.startswith("join_desc:"):
        return
    key = query.data.split(":", 1)[1]
    group = GROUPS.get(key)
    if not group:
        await query.answer("❌ Группа не найдена", show_alert=True)
        return
    await query.answer()
    desc = group.get("desc", "Нет описания.")
    text = (
        f"<b>{group['title']}</b>\n"
        f"{desc}\n\n"
        f"Ссылка: <a href='https://t.me/{group['link']}?start={query.from_user.id}_{key}'>Войти в группу</a>"
    )
    await query.edit_message_text(
        text, parse_mode="HTML", disable_web_page_preview=True
    )

# ============ /join_chat ============
async def join_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    group = GROUPS["chat"]
    link = f"https://t.me/{group['link']}?start={user_id}_chat"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Войти в чат", url=link)],
        [InlineKeyboardButton("ℹ️ Описание", callback_data="join_desc:chat")]
    ])
    await update.effective_message.reply_text(
        f"{group['title']}\n\n{group['desc']}\n\nПереход автоматически засчитывается в статистике (уникально).",
        reply_markup=keyboard
    )

# ============ /start с параметром ============
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args and "_" in args[0]:
        try:
            user_id, key = args[0].split("_", 1)
            user_id = int(user_id)
            if key in GROUPS and update.effective_user.id == user_id:
                already = await has_user_joined(key, user_id)
                if already:
                    await update.effective_message.reply_text("✅ Ваш переход уже учтен!")
                else:
                    ok = await register_join_user(key, user_id)
                    if ok:
                        await update.effective_message.reply_text("Спасибо, ваш переход засчитан! 🎉")
                    else:
                        await update.effective_message.reply_text("✅ Переход уже был учтен ранее!")
                # Можно показать меню или приветствие
                return
        except Exception:
            pass
    await update.effective_message.reply_text("Добро пожаловать! Используйте /join для выбора группы.")

# ============ /groupstats для админов ============
async def groupstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not (user and Config.is_admin(user.id)):
        await update.effective_message.reply_text("❌ Только для администраторов")
        return
    stats = await get_all_unique_counts()
    text = "📊 Статистика переходов:\n\n"
    for key, group in GROUPS.items():
        count = stats.get(key, 0)
        text += f"{group['title']}: {count} уникальных переход(ов)\n"
    await update.effective_message.reply_text(text)
