# handlers/join_handler.py
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from config import Config
from services.join_stats_db import increment, get, get_all

logger = logging.getLogger(__name__)

# Описание групп/каналов
GROUPS = {
    "chat": {
        "link": "https://t.me/tgchatxxx",
        "title": "🙅‍♀️ Будапешт - чат",
        "id": -1002919380244,
    },
    "public": {
        "link": "https://t.me/snghu",
        "title": "🙅‍♂️ Будапешт",
        "id": -1002743668534,
    },
    "catalog": {
        "link": "https://t.me/catalogtrix",
        "title": "🙅 Каталог услуг Будапешт",
        "id": -1002601716810,
    },
    "marketplace": {
        "link": "https://t.me/hungarytrade",
        "title": "🕵🏻‍♀️ Будапешт Куплю / Отдам / Продам",
        "id": -1003033694255,
    },
    "citytoppeople": {
        "link": "https://t.me/socialuck",
        "title": "🏆 Top Budapest 📱 Social 👩🏼‍❤️‍👨🏻 Люди Будапешт",
        "id": -1003088023508,
    },
    "citypartners": {
        "link": "https://t.me/budapestpartners",
        "title": "Budapest 📳 Partners",
        "id": -1003033694255,
    },
    "budapesocial": {
        "link": "https://t.me/budapesocial",
        "title": "BudapeSocial",
        "id": -1003114019170,
    },
}

def _is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and Config.is_admin(user.id))

async def _send_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    if not _is_admin(update):
        try:
            await update.effective_message.reply_text("❌ Только для администраторов")
        except:
            pass
        return

    group = GROUPS.get(key)
    if not group:
        await update.effective_message.reply_text("❌ Группа не найдена")
        return

    text = f"{group['title']}\nСсылка: {group['link']}\nId: {group['id']}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Перейти в группу", url=group['link'])],
        [InlineKeyboardButton("✅ Я перешёл", callback_data=f"join_ack:{key}")]
    ])

    await update.effective_message.reply_text(text, reply_markup=keyboard)

# Команды
async def chat_join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_group_message(update, context, "chat")

async def public_join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_group_message(update, context, "public")

async def catalog_join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_group_message(update, context, "catalog")

async def marketplace_join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_group_message(update, context, "marketplace")

async def join_citytoppeople_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_group_message(update, context, "citytoppeople")

async def join_citypartners_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_group_message(update, context, "citypartners")

async def join_budapesocial_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_group_message(update, context, "budapesocial")


# Callback для кнопки "Я перешёл"
async def handle_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return

    if not query.data.startswith("join_ack:"):
        return

    key = query.data.split(":", 1)[1]
    if key not in GROUPS:
        await query.answer("❌ Неверная группа", show_alert=True)
        return

    # Подсчёт переходов через БД сервис
    try:
        new_value = await increment(key)
        await query.answer(f"Спасибо! Отмечено: {new_value}", show_alert=False)
    except Exception as e:
        logger.error(f"Error incrementing join stats: {e}", exc_info=True)
        await query.answer("❌ Ошибка при сохранении статистики", show_alert=True)


# Админская статистика переходов
async def groupstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        try:
            await update.effective_message.reply_text("❌ Только для администраторов")
        except:
            pass
        return

    data = await get_all()
    # Убедимся, что все ключи присутствуют
    lines = []
    for key, meta in GROUPS.items():
        cnt = data.get(key, 0)
        lines.append(f"{meta['title']}: {cnt} переход(ов)")
    text = "📊 Статистика переходов по ссылкам:\n\n" + "\n".join(lines)
    await update.effective_message.reply_text(text)
