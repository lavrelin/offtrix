# -*- coding: utf-8 -*-
"""
Giveaway Handler - OPTIMIZED v5.2
- Уникальные префиксы callback_data: gwc_
- Сокращенные функции
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ============= CALLBACK PREFIXES =============
GIVEAWAY_CALLBACKS = {
    'daily': 'gwc_daily',
    'weekly': 'gwc_weekly',
    'monthly': 'gwc_monthly',
    'tasks': 'gwc_tasks',
    'stats': 'gwc_stats',
    'back': 'gwc_back',
}

# ============= DATA STORAGE =============
giveaway_data = {
    'daypost': [], 'daycomment': [], 'daytag': [], 'weeklyroll': [],
    'needtrymore': [], 'topweek': [], '7tt': [], 'member': [],
    'trixticket': [], 'active': [], 'ref': [], 'raidtrix': [],
}

def create_record(date: str, winner: str, prize: str, status: str = "Выплачено"):
    return {'date': date, 'winner': winner, 'prize': prize, 'status': status}

# ============= MAIN COMMAND =============

async def giveaway_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main giveaway menu"""
    keyboard = [
        [
            InlineKeyboardButton("✨24h", callback_data=GIVEAWAY_CALLBACKS['daily']),
            InlineKeyboardButton("💫7d", callback_data=GIVEAWAY_CALLBACKS['weekly'])
        ],
        [
            InlineKeyboardButton("🌟22th", callback_data=GIVEAWAY_CALLBACKS['monthly']),
            InlineKeyboardButton("⚡️Задания", callback_data=GIVEAWAY_CALLBACKS['tasks'])
        ],
        [InlineKeyboardButton("↩️ Назад", callback_data="mnc_back")]
    ]
    
    text = (
        "🥳**GiveAway by BudapestTrix**\n\n"
        "⚡️ **Daily**, **Weekly**, **Monthly**\n\n"
        "ℹ️**Информация:**\n"
        "🪬 Один приз в сутки\n"
        "📛 Фейки не получают награды\n"
        "💥 Результаты с задержкой\n"
        "🧬 Победитель получает уведомление\n\n"
        "🐦‍🔥**DAILY** — 15$/день\n"
        "🐦‍🔥**WEEKLY** — 55$/неделя\n"
        "🐦‍🔥**MONTHLY** — 220$+/месяц\n\n"
        "💳 Выплата: до 24ч\n"
        "👄Анонсы: [Budapest Partners](https://t.me/budapestpartners)"
    )
    
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Error in giveaway_command: {e}")

# ============= MENU FUNCTIONS =============

async def show_daily_menu(query, context):
    """Daily contests"""
    keyboard = [
        [InlineKeyboardButton("🔲 TopDayPost", callback_data=f"{GIVEAWAY_CALLBACKS['stats']}:daypost")],
        [InlineKeyboardButton("🔳 TopDayComment", callback_data=f"{GIVEAWAY_CALLBACKS['stats']}:daycomment")],
        [InlineKeyboardButton("🌀 TopDayTager", callback_data=f"{GIVEAWAY_CALLBACKS['stats']}:daytag")],
        [InlineKeyboardButton("🏎️ Назад", callback_data=GIVEAWAY_CALLBACKS['back'])]
    ]
    
    text = (
        "🏆 **ЕЖЕДНЕВНЫЕ**\n\n"
        "🔲 **TopDayPost** — 5$\n"
        "♥️ Лучший пост дня\n"
        "💁‍♀️ /start для предложения\n\n"
        "🔳 **TopDayComment** — 5$\n"
        "♦️ Лучший комментарий\n\n"
        "🌀 **TopDayTager** — 5$\n"
        "♠️ Лучший пост с упоминанием Трикс\n"
        "💁 /social для ссылок"
    )
    
    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

async def show_weekly_menu(query, context):
    """Weekly contests"""
    keyboard = [
        [InlineKeyboardButton("🎲 WeeklyRoll", callback_data=f"{GIVEAWAY_CALLBACKS['stats']}:weeklyroll")],
        [InlineKeyboardButton("🎳 NeedTryMore", callback_data=f"{GIVEAWAY_CALLBACKS['stats']}:needtrymore")],
        [InlineKeyboardButton("🪪 TopWeek", callback_data=f"{GIVEAWAY_CALLBACKS['stats']}:topweek")],
        [InlineKeyboardButton("🎫 7TT", callback_data=f"{GIVEAWAY_CALLBACKS['stats']}:7tt")],
        [InlineKeyboardButton("🚂 Назад", callback_data=GIVEAWAY_CALLBACKS['back'])]
    ]
    
    text = (
        "📋 **ЕЖЕНЕДЕЛЬНЫЕ**\n\n"
        "🎲 **WeeklyRoll** — 15$ (3 победителя)\n"
        "🫧 Рандомный розыгрыш\n\n"
        "🎳 **NeedTryMore** — 30$ (3 победителя)\n"
        "🧑‍🧑‍🧒 Угадай слово по подсказкам\n\n"
        "🎩**TopWeek** — 10$\n"
        "👚Лучшая публикация недели\n\n"
        "🎫 **7TT** — Раздача 7 билетов"
    )
    
    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

async def show_monthly_menu(query, context):
    """Monthly contests"""
    keyboard = [
        [InlineKeyboardButton("🤺 Member", callback_data=f"{GIVEAWAY_CALLBACKS['stats']}:member")],
        [InlineKeyboardButton("🎫 TrixTicket", callback_data=f"{GIVEAWAY_CALLBACKS['stats']}:trixticket")],
        [InlineKeyboardButton("🚐 Назад", callback_data=GIVEAWAY_CALLBACKS['back'])]
    ]
    
    text = (
        "🗽 **ЕЖЕМЕСЯЧНЫЕ**\n\n"
        "🤺 **Member** — 100$\n"
        "🎢 10 категорий — 2 победителя\n"
        "Все подписчики участвуют\n\n"
        "🎫 **TrixTicket** — Уникальные награды\n"
        "3 победителя из владельцев билетов\n\n"
        "💳 Выплата: в течении суток"
    )
    
    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

async def show_tasks_menu(query, context):
    """Tasks menu"""
    keyboard = [
        [InlineKeyboardButton("📁 Active3x", callback_data=f"{GIVEAWAY_CALLBACKS['stats']}:active")],
        [InlineKeyboardButton("🗄️ RaidTrix", callback_data=f"{GIVEAWAY_CALLBACKS['stats']}:raidtrix")],
        [InlineKeyboardButton("🔏 Рефералы", callback_data=f"{GIVEAWAY_CALLBACKS['stats']}:ref")],
        [InlineKeyboardButton("↩️ Назад", callback_data=GIVEAWAY_CALLBACKS['back'])]
    ]
    
    text = (
        "🗃️ **ЗАДАНИЯ**\n\n"
        "🧨 **Active3x** — 3$\n"
        "🔥 FB, Instagram, Threads\n"
        "1 repost + 10 like + 3 comments\n"
        "Выплата через 3 дня\n\n"
        "💣 **Trix Raid**\n"
        "Отправляй рекламу Трикс\n"
        "• 26 сообщений — 2$\n"
        "• 50 сообщений — 6$ + TrixTicket\n\n"
        "🔗 **Рефералы** — 5-10$ + TT\n"
        "Binance: 5$\n"
        "STAKE: 5$ + TrixTicket\n\n"
        "📨 Заявки: @trixilvebot"
    )
    
    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

async def show_giveaway_stats(query, context, section: str):
    """Show stats for section"""
    if section not in giveaway_data:
        await query.answer("❌ Раздел не найден", show_alert=True)
        return
    
    records = giveaway_data[section]
    
    section_names = {
        'daypost': '🏆 TopDayPost', 'daycomment': '🗣️ TopDayComment',
        'daytag': '🌀 TopDayTager', 'weeklyroll': '🎲 WeeklyRoll',
        'needtrymore': '🎮 NeedTryMore', 'topweek': '⭐️ TopWeek',
        '7tt': '🎫 7TT', 'member': '👥 Member', 'trixticket': '🎫 TrixTicket',
        'active': '🟢 Active3x', 'ref': '🔗 Рефералы', 'raidtrix': '💬 RaidTrix',
    }
    
    title = section_names.get(section, section)
    
    if not records:
        text = f"📊 **{title}**\n\n❌ Нет записей"
    else:
        text = f"📊 **{title}** ({len(records)})\n\n"
        for record in records[-10:]:
            text += (
                f"📅 {record['date']}\n"
                f"👤 @{record['winner']}\n"
                f"🎁 {record['prize']}\n"
                f"✅ {record['status']}\n\n"
            )
    
    total_sum = sum(
        int(r['prize'].replace('$', '').strip())
        for r in records if r['prize'].replace('$', '').strip().isdigit()
    )
    
    if total_sum > 0:
        text += f"\n💰 **Всего: ${total_sum}**"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=GIVEAWAY_CALLBACKS['back'])]]
    
    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

# ============= CALLBACK HANDLER =============

async def handle_giveaway_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle giveaway callbacks"""
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split(":")
    
    # Remove prefix
    if data_parts[0].startswith('gwc_'):
        action = data_parts[0][4:]
    else:
        action = data_parts[0]
    
    section = data_parts[1] if len(data_parts) > 1 else None
    
    if action == 'daily':
        await show_daily_menu(query, context)
    elif action == 'weekly':
        await show_weekly_menu(query, context)
    elif action == 'monthly':
        await show_monthly_menu(query, context)
    elif action == 'tasks':
        await show_tasks_menu(query, context)
    elif action == 'stats':
        await show_giveaway_stats(query, context, section)
    elif action == 'back':
        await giveaway_command(update, context)

# ============= P2P COMMAND =============

async def p2p_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """P2P info"""
    text = (
        "🪬 **#P2P ПРОДАТЬ/КУПИТЬ КРИПТУ**\n\n"
        "💡 Как быстро продать крипту?\n\n"
        "🔗 Пример: Binance → Monobank\n"
        "💱 Пара: USDT / UAH 💸\n\n"
        "1️⃣ **Регистрация**\n"
        "[🌐 BINANCE](https://accounts.binance.com/en/register?ref=TRIXBONUS)\n"
        "✅ Подтверди почту\n\n"
        "2️⃣ **Верификация**\n"
        "🧾 Подтверди личность\n"
        "⏱️ 5-10 минут\n\n"
        "3️⃣ **Добавь карту**\n"
        "💳 P2P → Методы → Карта\n\n"
        "4️⃣ **Продай**\n"
        "🔁 P2P → Продать\n"
        "🪙 USDT / UAH\n\n"
        "5️⃣ **Получение**\n"
        "💰 Покупатель переведет\n"
        "✅ Подтверди получение\n\n"
        "📞 Вопросы: @trixilvebot"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data="mnc_back")]]
    
    await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

# ============= ADMIN FUNCTION =============

async def add_giveaway_record(section: str, winner: str, prize: str, status: str = "Выплачено"):
    """Add winner record"""
    if section not in giveaway_data:
        return False
    
    date = datetime.now().strftime("%d.%m.%y")
    record = create_record(date, winner, prize, status)
    giveaway_data[section].append(record)
    logger.info(f"Added giveaway: {section} - {winner} - {prize}")
    return True

__all__ = [
    'giveaway_command',
    'handle_giveaway_callback',
    'p2p_command',
    'add_giveaway_record',
    'giveaway_data',
    'GIVEAWAY_CALLBACKS',
]
