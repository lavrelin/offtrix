# -*- coding: utf-8 -*-
"""
Optimized Admin Handler
Prefix: adc_ (admin callback)
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from services.admin_notifications import admin_notifications
from data.user_data import user_data
import logging

logger = logging.getLogger(__name__)

# ============= CALLBACK PREFIX: adc_ =============
ADMIN_CALLBACKS = {
    'broadcast': 'adc_brc', 'stats': 'adc_st', 'users': 'adc_usr',
    'games': 'adc_gm', 'settings': 'adc_set', 'autopost': 'adc_ap',
    'logs': 'adc_log', 'help': 'adc_hlp', 'back': 'adc_bk',
    'confirm_broadcast': 'adc_cbc', 'cancel_broadcast': 'adc_cnbc'
}

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав")
        return

    keyboard = [
        [
            InlineKeyboardButton("📢 Рассылка", callback_data=ADMIN_CALLBACKS['broadcast']),
            InlineKeyboardButton("📊 Статистика", callback_data=ADMIN_CALLBACKS['stats'])
        ],
        [
            InlineKeyboardButton("👥 Пользователи", callback_data=ADMIN_CALLBACKS['users']),
            InlineKeyboardButton("🎮 Игры", callback_data=ADMIN_CALLBACKS['games'])
        ],
        [
            InlineKeyboardButton("⚙️ Настройки", callback_data=ADMIN_CALLBACKS['settings']),
            InlineKeyboardButton("ℹ️ Помощь", callback_data=ADMIN_CALLBACKS['help'])
        ]
    ]

    await update.message.reply_text(
        "🔧 **АДМИН-ПАНЕЛЬ**\n\nВыберите раздел:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin callback handler"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    handlers = {
        ADMIN_CALLBACKS['broadcast']: show_broadcast_info,
        ADMIN_CALLBACKS['stats']: show_stats,
        ADMIN_CALLBACKS['users']: show_users_info,
        ADMIN_CALLBACKS['games']: show_games_info,
        ADMIN_CALLBACKS['settings']: show_settings,
        ADMIN_CALLBACKS['help']: show_admin_help,
        ADMIN_CALLBACKS['back']: show_main_admin_menu,
        ADMIN_CALLBACKS['confirm_broadcast']: execute_broadcast,
        ADMIN_CALLBACKS['cancel_broadcast']: lambda q, c: q.edit_message_text("❌ Отменено")
    }
    
    handler = handlers.get(action)
    if handler:
        await handler(query, context)

async def show_broadcast_info(query, context):
    """Broadcast info"""
    text = (
        f"📢 **РАССЫЛКА**\n\n"
        f"👥 Пользователей: {len(user_data)}\n\n"
        "Используйте:\n`/broadcast текст`"
    )
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=ADMIN_CALLBACKS['back'])]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_stats(query, context):
    """Show statistics"""
    from data.games_data import word_games, roll_games
    from datetime import datetime, timedelta
    
    stats = {
        'total': len(user_data),
        'active_24h': sum(1 for d in user_data.values() if datetime.now() - d['last_activity'] <= timedelta(days=1)),
        'messages': sum(d['message_count'] for d in user_data.values()),
        'banned': sum(1 for d in user_data.values() if d.get('banned'))
    }
    
    text = (
        f"📊 **СТАТИСТИКА**\n\n"
        f"👥 Пользователей: {stats['total']}\n"
        f"🟢 Активных 24ч: {stats['active_24h']}\n"
        f"💬 Сообщений: {stats['messages']}\n"
        f"🚫 Забанено: {stats['banned']}"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data=ADMIN_CALLBACKS['stats'])],
        [InlineKeyboardButton("◀️ Назад", callback_data=ADMIN_CALLBACKS['back'])]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_users_info(query, context):
    """Users info"""
    from data.user_data import get_top_users
    
    top = get_top_users(5)
    top_text = "\n".join([f"{i+1}. @{u['username']} - {u['message_count']}" for i, u in enumerate(top)])
    
    text = f"👥 **ПОЛЬЗОВАТЕЛИ**\n\n🏆 **Топ-5:**\n{top_text}"
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=ADMIN_CALLBACKS['back'])]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_games_info(query, context):
    """Games info"""
    from data.games_data import word_games, roll_games
    
    text = "🎮 **ИГРЫ**\n\n"
    for v in ['need', 'try', 'more']:
        status = "🟢" if word_games[v]['active'] else "🔴"
        text += f"**{v.upper()}:** {status} | Слов: {len(word_games[v]['words'])}\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=ADMIN_CALLBACKS['back'])]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_settings(query, context):
    """Settings"""
    text = (
        f"⚙️ **НАСТРОЙКИ**\n\n"
        f"📢 Канал: {Config.TARGET_CHANNEL_ID}\n"
        f"👮 Модерация: {Config.MODERATION_GROUP_ID}\n"
        f"👑 Админов: {len(Config.ADMIN_IDS)}\n"
        f"⏱️ Кулдаун: {Config.COOLDOWN_SECONDS // 3600}ч"
    )
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=ADMIN_CALLBACKS['back'])]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_admin_help(query, context):
    """Admin help"""
    text = (
        "ℹ️ **СПРАВКА**\n\n"
        "**Рассылка:**\n"
        "`/broadcast текст`\n"
        "`/say USER_ID текст`\n\n"
        "**Статистика:**\n"
        "`/stats`, `/sendstats`, `/top`"
    )
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=ADMIN_CALLBACKS['back'])]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_main_admin_menu(query, context):
    """Main admin menu"""
    keyboard = [
        [
            InlineKeyboardButton("📢 Рассылка", callback_data=ADMIN_CALLBACKS['broadcast']),
            InlineKeyboardButton("📊 Статистика", callback_data=ADMIN_CALLBACKS['stats'])
        ],
        [
            InlineKeyboardButton("👥 Пользователи", callback_data=ADMIN_CALLBACKS['users']),
            InlineKeyboardButton("ℹ️ Помощь", callback_data=ADMIN_CALLBACKS['help'])
        ]
    ]
    await query.edit_message_text(
        "🔧 **АДМИН-ПАНЕЛЬ**\n\nВыберите раздел:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def execute_broadcast(query, context):
    """Execute broadcast"""
    text = context.user_data.get('broadcast_text')
    if not text:
        await query.edit_message_text("❌ Текст не найден")
        return

    await query.edit_message_text("📢 Начинаю рассылку...")

    sent, failed = 0, 0
    for uid in user_data.keys():
        try:
            await context.bot.send_message(uid, text)
            sent += 1
        except:
            failed += 1

    await admin_notifications.notify_broadcast(
        sent=sent, failed=failed,
        moderator=query.from_user.username or str(query.from_user.id)
    )

    await query.edit_message_text(f"✅ **Завершено**\n\n📤 Отправлено: {sent}\n❌ Не удалось: {failed}", parse_mode='Markdown')
    context.user_data.pop('broadcast_text', None)

async def say_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Say command - optimized"""
    if not Config.is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "📝 **Использование:**\n\n"
            "**Reply:** `/say текст`\n"
            "**По ID:** `/say 123456789 текст`\n\n"
            "⚠️ Username НЕ РАБОТАЕТ",
            parse_mode='Markdown'
        )
        return
    
    target_id, msg_text = None, None
    
    # Reply variant
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        msg_text = ' '.join(context.args)
    # ID variant
    elif context.args[0].isdigit():
        target_id = int(context.args[0])
        msg_text = ' '.join(context.args[1:])
    else:
        await update.message.reply_text("❌ Неверный формат")
        return
    
    if not msg_text:
        await update.message.reply_text("❌ Нет текста")
        return
    
    # Delete command
    if update.effective_chat.type != 'private':
        try:
            await update.message.delete()
        except:
            pass
    
    # Send message
    try:
        await context.bot.send_message(target_id, f"📨 **Сообщение от администрации:**\n\n{msg_text}", parse_mode='Markdown')
        await context.bot.send_message(update.effective_user.id, f"✅ Доставлено!\n👤 ID: `{target_id}`", parse_mode='Markdown')
    except Exception as e:
        error_msg = "блокировал бота" if "blocked" in str(e).lower() else "не найден"
        await context.bot.send_message(update.effective_user.id, f"❌ Не удалось: {error_msg}")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast command"""
    if not Config.is_admin(update.effective_user.id):
        return
    
    if not context.args:
        await update.message.reply_text("📝 `/broadcast текст`", parse_mode='Markdown')
        return
    
    msg_text = ' '.join(context.args)
    context.user_data['broadcast_text'] = msg_text
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=ADMIN_CALLBACKS['confirm_broadcast']),
            InlineKeyboardButton("❌ Отменить", callback_data=ADMIN_CALLBACKS['cancel_broadcast'])
        ]
    ]
    
    await update.message.reply_text(
        f"📢 **Подтверждение**\n\n{msg_text}\n\n👥 Получателей: {len(user_data)}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def sendstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send stats"""
    if not Config.is_admin(update.effective_user.id):
        return
    
    await update.message.reply_text("📊 Отправляю статистику...")
    try:
        await admin_notifications.send_statistics()
        await update.message.reply_text("✅ Отправлено!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

__all__ = [
    'admin_command', 'handle_admin_callback', 'say_command',
    'broadcast_command', 'sendstats_command', 'ADMIN_CALLBACKS'
]
