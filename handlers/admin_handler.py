# -*- coding: utf-8 -*-
"""
Admin Handler v2.0 - Полностью переработанный
Prefix: adm_ (admin)
Изменения:
- /broadcast обновлен
- /say удален
- /talkto @username (text) или /talkto id (text) добавлен
- /stats полностью переработан с инлайн кнопками
- /id перенесен сюда
- /report перенесен сюда с cooldown 1 час
- /silence добавлен
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from services.admin_notifications import admin_notifications
from services.cooldown import cooldown_service
from services.channel_stats import channel_stats
from data.user_data import user_data, update_user_activity, is_user_banned
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ============= CALLBACK PREFIX: adm_ =============
ADMIN_CALLBACKS = {
    'broadcast': 'adm_brc',
    'stats_trixbot': 'adm_st_tb',
    'stats_channels': 'adm_st_ch',
    'users': 'adm_usr',
    'settings': 'adm_set',
    'help': 'adm_hlp',
    'back': 'adm_bk',
    'confirm_broadcast': 'adm_cbc',
    'cancel_broadcast': 'adm_cnbc',
    'stats_day': 'adm_st_d',
    'stats_week': 'adm_st_w',
    'stats_month': 'adm_st_m',
}

# ============= SILENCE LIST =============
silenced_users = set()  # Пользователи в silence режиме

# ============= ID COMMAND =============

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать ID пользователя или чата"""
    user = update.effective_user
    chat = update.effective_chat
    
    text = f"🆔 **Информация об ID:**\n\n👤 Ваш ID: `{user.id}`"
    
    if chat.type != 'private':
        text += f"\n💬 ID чата: `{chat.id}`\n📝 Тип чата: {chat.type}"
        if chat.title:
            text += f"\n🏷️ Название: {chat.title}"
    
    update_user_activity(user.id, user.username)
    await update.message.reply_text(text, parse_mode='Markdown')

# ============= REPORT COMMAND (с cooldown 1 час) =============

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить жалобу модераторам (cooldown 1 час)"""
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID_{user_id}"
    
    update_user_activity(user_id, update.effective_user.username)
    
    if is_user_banned(user_id):
        await update.message.reply_text("❌ Вы заблокированы и не можете отправлять жалобы")
        return
    
    # Проверяем кулдаун
    can_report, remaining = await cooldown_service.check_cooldown(
        user_id, 'report', 3600  # 1 час
    )
    
    if not can_report:
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await update.message.reply_text(
            f"⏳ Следующую жалобу можно отправить через {hours}ч {minutes}м"
        )
        return
    
    if not context.args:
        await update.message.reply_text(
            "📝 **Использование:**\n\n"
            "`/report @username причина` - жалоба на пользователя\n"
            "`/report причина` - общая жалоба\n\n"
            "Можно прикрепить ссылку или медиа (reply на сообщение)\n\n"
            "**Примеры:**\n"
            "• `/report @baduser Спам в личные сообщения`\n"
            "• `/report Неприемлемый контент в канале`",
            parse_mode='Markdown'
        )
        return
    
    # Проверяем, указан ли пользователь
    target = "Общая жалоба"
    reason = ' '.join(context.args)
    
    if context.args[0].startswith('@'):
        target = context.args[0]
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "Не указана"
    
    # Проверяем длину причины
    if len(reason) < 10:
        await update.message.reply_text(
            "❌ Причина жалобы слишком короткая.\n"
            "Пожалуйста, опишите проблему подробнее (минимум 10 символов)"
        )
        return
    
    # Получаем медиа или ссылку
    media_info = None
    link = None
    
    if update.message.reply_to_message:
        replied = update.message.reply_to_message
        if replied.photo:
            media_info = "photo"
        elif replied.video:
            media_info = "video"
        elif replied.document:
            media_info = "document"
        
        if replied.text and ('http://' in replied.text or 'https://' in replied.text):
            link = replied.text
    
    # Отправляем уведомление в админскую группу
    try:
        report_text = (
            f"🚨 **НОВАЯ ЖАЛОБА**\n\n"
            f"👤 От: @{username} (ID: `{user_id}`)\n"
            f"🎯 На: {target}\n"
            f"📝 Причина: {reason}"
        )
        
        if media_info:
            report_text += f"\n📎 Медиа: {media_info}"
        if link:
            report_text += f"\n🔗 Ссылка: {link}"
        
        await context.bot.send_message(
            Config.ADMIN_GROUP_ID,
            report_text,
            parse_mode='Markdown'
        )
        
        # Устанавливаем кулдаун
        await cooldown_service.set_cooldown(user_id, 'report', 3600)
        
        # Подтверждение пользователю
        await update.message.reply_text(
            "✅ **Ваша жалоба отправлена модераторам**\n\n"
            "Спасибо за бдительность! Мы рассмотрим вашу жалобу в ближайшее время.\n\n"
            "⚠️ Ложные жалобы могут привести к блокировке.\n"
            "⏰ Следующую жалобу можно отправить через 1 час."
        )
        
        logger.info(f"Report from {username} (ID: {user_id}) about {target}: {reason}")
        
    except Exception as e:
        logger.error(f"Error sending report notification: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при отправке жалобы. Попробуйте позже."
        )

# ============= SILENCE COMMAND =============

async def silence_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Заставить бота игнорировать пользователя"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📝 **Использование:**\n\n"
            "`/silence @username` - добавить в silence\n"
            "`/silence id` - добавить в silence\n"
            "`/silence list` - список\n"
            "`/silence remove @username` - убрать",
            parse_mode='Markdown'
        )
        return
    
    if context.args[0] == 'list':
        if not silenced_users:
            await update.message.reply_text("📊 Список silence пуст")
            return
        
        text = "🔇 **SILENCE LIST:**\n\n"
        for uid in silenced_users:
            text += f"• ID: `{uid}`\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
        return
    
    if context.args[0] == 'remove':
        if len(context.args) < 2:
            await update.message.reply_text("❌ Укажите пользователя")
            return
        
        target = context.args[1]
        user_id = None
        
        if target.startswith('@'):
            from data.user_data import get_user_by_username
            user_info = get_user_by_username(target[1:])
            if user_info:
                user_id = user_info['id']
        elif target.isdigit():
            user_id = int(target)
        
        if user_id and user_id in silenced_users:
            silenced_users.remove(user_id)
            await update.message.reply_text(f"✅ Пользователь {target} убран из silence")
            logger.info(f"User {user_id} removed from silence by admin {update.effective_user.id}")
        else:
            await update.message.reply_text("❌ Пользователь не найден в silence")
        
        return
    
    # Добавляем в silence
    target = context.args[0]
    user_id = None
    
    if target.startswith('@'):
        from data.user_data import get_user_by_username
        user_info = get_user_by_username(target[1:])
        if user_info:
            user_id = user_info['id']
    elif target.isdigit():
        user_id = int(target)
    
    if user_id:
        silenced_users.add(user_id)
        await update.message.reply_text(
            f"🔇 Пользователь {target} добавлен в silence\n\n"
            "Бот будет игнорировать все команды, ответы и сообщения от него"
        )
        logger.info(f"User {user_id} silenced by admin {update.effective_user.id}")
    else:
        await update.message.reply_text("❌ Пользователь не найден")

def is_user_silenced(user_id: int) -> bool:
    """Проверка, находится ли пользователь в silence"""
    return user_id in silenced_users

# ============= ADMIN PANEL =============

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав")
        return

    keyboard = [
        [
            InlineKeyboardButton("📢 Рассылка", callback_data=ADMIN_CALLBACKS['broadcast']),
            InlineKeyboardButton("📊 Статистика", callback_data=ADMIN_CALLBACKS['stats_trixbot'])
        ],
        [
            InlineKeyboardButton("👥 Пользователи", callback_data=ADMIN_CALLBACKS['users']),
            InlineKeyboardButton("⚙️ Настройки", callback_data=ADMIN_CALLBACKS['settings'])
        ],
        [
            InlineKeyboardButton("ℹ️ Помощь", callback_data=ADMIN_CALLBACKS['help'])
        ]
    ]

    await update.message.reply_text(
        "🔧 **АДМИН-ПАНЕЛЬ**\n\nВыберите раздел:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============= ADMIN CALLBACKS =============

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin callback handler"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    handlers = {
        ADMIN_CALLBACKS['broadcast']: show_broadcast_info,
        ADMIN_CALLBACKS['stats_trixbot']: show_trixbot_stats,
        ADMIN_CALLBACKS['stats_channels']: show_channels_stats,
        ADMIN_CALLBACKS['users']: show_users_info,
        ADMIN_CALLBACKS['settings']: show_settings,
        ADMIN_CALLBACKS['help']: show_admin_help,
        ADMIN_CALLBACKS['back']: show_main_admin_menu,
        ADMIN_CALLBACKS['confirm_broadcast']: execute_broadcast,
        ADMIN_CALLBACKS['cancel_broadcast']: lambda q, c: q.edit_message_text("❌ Отменено"),
        ADMIN_CALLBACKS['stats_day']: lambda q, c: show_period_stats(q, c, 'day'),
        ADMIN_CALLBACKS['stats_week']: lambda q, c: show_period_stats(q, c, 'week'),
        ADMIN_CALLBACKS['stats_month']: lambda q, c: show_period_stats(q, c, 'month'),
    }
    
    handler = handlers.get(action)
    if handler:
        await handler(query, context)

# ============= STATS FUNCTIONS =============

async def show_trixbot_stats(query, context):
    """Статистика TrixBot с кнопками периодов"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Каналы", callback_data=ADMIN_CALLBACKS['stats_channels']),
        ],
        [
            InlineKeyboardButton("📅 День", callback_data=ADMIN_CALLBACKS['stats_day']),
            InlineKeyboardButton("📅 Неделя", callback_data=ADMIN_CALLBACKS['stats_week']),
            InlineKeyboardButton("📅 Месяц", callback_data=ADMIN_CALLBACKS['stats_month']),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data=ADMIN_CALLBACKS['back'])]
    ]
    
    from data.user_data import get_top_commands
    
    # Базовая статистика
    total_users = len(user_data)
    active_24h = sum(
        1 for d in user_data.values() 
        if datetime.now() - d['last_activity'] <= timedelta(days=1)
    )
    total_commands = sum(d.get('command_count', 0) for d in user_data.values())
    
    # Топ команд
    top_commands = get_top_commands(5)
    top_text = "\n".join([
        f"{i+1}. /{cmd} — {count} раз" 
        for i, (cmd, count) in enumerate(top_commands)
    ])
    
    text = (
        f"⚙️ **СТАТИСТИКА TRIXBOT**\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🟢 Активных 24ч: {active_24h}\n"
        f"⌨️ Всего команд: {total_commands}\n\n"
        f"🔝 **Топ-5 команд:**\n{top_text}"
    )
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_channels_stats(query, context):
    """Статистика каналов"""
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data=ADMIN_CALLBACKS['stats_channels'])],
        [InlineKeyboardButton("◀️ Назад", callback_data=ADMIN_CALLBACKS['stats_trixbot'])]
    ]
    
    # Получаем статистику каналов
    stats = await channel_stats.get_all_stats()
    
    if 'error' in stats:
        text = f"❌ Ошибка: {stats['error']}"
    else:
        text = channel_stats.format_stats_message(stats)
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_period_stats(query, context, period: str):
    """Статистика за период"""
    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data=ADMIN_CALLBACKS['stats_trixbot'])]
    ]
    
    # Определяем период
    if period == 'day':
        cutoff = datetime.now() - timedelta(days=1)
        title = "День"
    elif period == 'week':
        cutoff = datetime.now() - timedelta(days=7)
        title = "Неделя"
    else:  # month
        cutoff = datetime.now() - timedelta(days=30)
        title = "Месяц"
    
    # Считаем пользователей
    active_users = sum(
        1 for d in user_data.values() 
        if d['last_activity'] >= cutoff
    )
    
    text = (
        f"📊 **СТАТИСТИКА ЗА {title.upper()}**\n\n"
        f"👥 Уникальные пользователи: {active_users}\n"
        f"📅 Период: с {cutoff.strftime('%d.%m.%Y %H:%M')}"
    )
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_broadcast_info(query, context):
    """Broadcast info"""
    text = (
        f"📢 **РАССЫЛКА**\n\n"
        f"👥 Пользователей: {len(user_data)}\n\n"
        "Используйте:\n`/broadcast текст`"
    )
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=ADMIN_CALLBACKS['back'])]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_users_info(query, context):
    """Users info"""
    from data.user_data import get_top_users
    
    top = get_top_users(5)
    top_text = "\n".join([f"{i+1}. @{u['username']} - {u['message_count']}" for i, u in enumerate(top)])
    
    text = f"👥 **ПОЛЬЗОВАТЕЛИ**\n\n🏆 **Топ-5:**\n{top_text}"
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
        "`/broadcast текст`\n\n"
        "**Сообщения:**\n"
        "`/talkto @username текст`\n"
        "`/talkto id текст`\n\n"
        "**Статистика:**\n"
        "`/stats`\n\n"
        "**Silence:**\n"
        "`/silence @username`"
    )
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=ADMIN_CALLBACKS['back'])]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_main_admin_menu(query, context):
    """Main admin menu"""
    keyboard = [
        [
            InlineKeyboardButton("📢 Рассылка", callback_data=ADMIN_CALLBACKS['broadcast']),
            InlineKeyboardButton("📊 Статистика", callback_data=ADMIN_CALLBACKS['stats_trixbot'])
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

    await query.edit_message_text(
        f"✅ **Завершено**\n\n📤 Отправлено: {sent}\n❌ Не удалось: {failed}",
        parse_mode='Markdown'
    )
    context.user_data.pop('broadcast_text', None)

# ============= TALKTO COMMAND =============

async def talkto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить сообщение пользователю (замена /say)"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет прав")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "📝 **Использование:**\n\n"
            "`/talkto @username текст сообщения`\n"
            "`/talkto id текст сообщения`\n\n"
            "**Примеры:**\n"
            "• `/talkto @user Привет!`\n"
            "• `/talkto 123456789 Здравствуйте!`",
            parse_mode='Markdown'
        )
        return
    
    target = context.args[0]
    message_text = ' '.join(context.args[1:])
    
    # Определяем ID пользователя
    user_id = None
    
    if target.startswith('@'):
        from data.user_data import get_user_by_username
        user_info = get_user_by_username(target[1:])
        if user_info:
            user_id = user_info['id']
    elif target.isdigit():
        user_id = int(target)
    
    if not user_id:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    # Удаляем команду в группах
    if update.effective_chat.type != 'private':
        try:
            await update.message.delete()
        except:
            pass
    
    # Отправляем сообщение
    try:
        await context.bot.send_message(
            user_id,
            f"📨 **Сообщение от администрации:**\n\n{message_text}",
            parse_mode='Markdown'
        )
        
        await context.bot.send_message(
            update.effective_user.id,
            f"✅ Доставлено!\n👤 Получатель: {target}\n📝 Текст: {message_text[:100]}...",
            parse_mode='Markdown'
        )
        
        logger.info(f"Talkto from admin {update.effective_user.id} to {user_id}: {message_text[:50]}")
        
    except Exception as e:
        error_msg = "блокировал бота" if "blocked" in str(e).lower() else "не найден"
        await context.bot.send_message(
            update.effective_user.id,
            f"❌ Не удалось доставить: {error_msg}"
        )

# ============= BROADCAST COMMAND =============

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
    'admin_command', 'handle_admin_callback', 'talkto_command',
    'broadcast_command', 'sendstats_command', 'ADMIN_CALLBACKS',
    'id_command', 'report_command', 'silence_command', 'is_user_silenced'
]
