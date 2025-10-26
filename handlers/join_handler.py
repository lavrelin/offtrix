import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import Config
from services.join_stats_db import (
    register_join_user, has_user_joined, get_all_unique_counts
)

logger = logging.getLogger(__name__)

GROUPS = {
    "chat": {
        "link": "tgchatxxx",
        "title": "🙅‍♀️ Будапешт - чат",
        "id": -1002919380244,
    },
    "public": {
        "link": "snghu",
        "title": "🙅‍♂️ Будапешт",
        "id": -1002743668534,
    },
    "catalog": {
        "link": "catalogtrix",
        "title": "🙅 Каталог услуг Будапешт",
        "id": -1002601716810,
    },
    "marketplace": {
        "link": "hungarytrade",
        "title": "🕵🏻‍♀️ Будапешт Куплю/Отдам/Продам",
        "id": -1003033694255,
    },
    "citytoppeople": {
        "link": "socialuck",
        "title": "🏆 Top Budapest 📱 Social 👩🏼‍❤️‍👨🏻 Люди Будапешт",
        "id": -1003088023508,
    },
    "citypartners": {
        "link": "budapestpartners",
        "title": "Budapest 📳 Partners",
        "id": -1003033694255,
    },
    "budapesocial": {
        "link": "budapesocial",
        "title": "BudaPes🦄",
        "id": -1003114019170,
    },
}

def _get_btn(text, url):
    return [InlineKeyboardButton(text, url=url)]

# ====== Одиночные хендлеры для каждой группы (без описания) ======
async def chat_join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    group = GROUPS["chat"]
    link = f"https://t.me/{group['link']}?start={user_id}_chat"
    keyboard = InlineKeyboardMarkup([_get_btn("🔗 Войти в чат", link)])
    await update.effective_message.reply_text(
        f"{group['title']}",
        reply_markup=keyboard
    )

async def public_join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    group = GROUPS["public"]
    link = f"https://t.me/{group['link']}?start={user_id}_public"
    keyboard = InlineKeyboardMarkup([_get_btn("🔗 Войти в канал", link)])
    await update.effective_message.reply_text(
        f"{group['title']}",
        reply_markup=keyboard
    )

async def catalog_join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    group = GROUPS["catalog"]
    link = f"https://t.me/{group['link']}?start={user_id}_catalog"
    keyboard = InlineKeyboardMarkup([_get_btn("🔗 Каталог услуг", link)])
    await update.effective_message.reply_text(
        f"{group['title']}",
        reply_markup=keyboard
    )

async def marketplace_join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    group = GROUPS["marketplace"]
    link = f"https://t.me/{group['link']}?start={user_id}_marketplace"
    keyboard = InlineKeyboardMarkup([_get_btn("🔗 Маркетплейс", link)])
    await update.effective_message.reply_text(
        f"{group['title']}",
        reply_markup=keyboard
    )

async def join_citytoppeople_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    group = GROUPS["citytoppeople"]
    link = f"https://t.me/{group['link']}?start={user_id}_citytoppeople"
    keyboard = InlineKeyboardMarkup([_get_btn("🔗 Войти в топ-людей", link)])
    await update.effective_message.reply_text(
        f"{group['title']}",
        reply_markup=keyboard
    )

async def join_citypartners_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    group = GROUPS["citypartners"]
    link = f"https://t.me/{group['link']}?start={user_id}_citypartners"
    keyboard = InlineKeyboardMarkup([_get_btn("🔗 Войти в партнеры", link)])
    await update.effective_message.reply_text(
        f"{group['title']}",
        reply_markup=keyboard
    )

async def join_budapesocial_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    group = GROUPS["budapesocial"]
    link = f"https://t.me/{group['link']}?start={user_id}_budapesocial"
    keyboard = InlineKeyboardMarkup([_get_btn("🔗 Войти в Budapesocial", link)])
    await update.effective_message.reply_text(
        f"{group['title']}",
        reply_markup=keyboard
    )

# ====== Менюшка /join без описаний ======
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
        keyboard.append([join_btn])
    markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text(
        text,
        reply_markup=markup,
        parse_mode="HTML"
    )

# ====== /start с параметром для учёта перехода ======
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
                return
        except Exception:
            pass
    await update.effective_message.reply_text("Добро пожаловать! Используйте /join для выбора группы.")

# ====== /groupstats для админов ======
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

# ====== CALLBACK HANDLER ДЛЯ ПОДТВЕРЖДЕНИЯ ВСТУПЛЕНИЯ ======
async def handle_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для подтверждения вступления в группы"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Простая заглушка
        await query.edit_message_text("✅ Спасибо за подтверждение вступления!")
    except Exception as e:
        logger.error(f"Error in handle_join_callback: {e}")
        await query.edit_message_text("❌ Произошла ошибка при обработке подтверждения")
