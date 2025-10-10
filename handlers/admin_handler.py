# -*- coding: utf-8 -*-
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from services.admin_notifications import admin_notifications
from data.user_data import user_data

logger = logging.getLogger(__name__)

# ===============================
# Главное меню администратора
# ===============================
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображение админ-панели"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return

    keyboard = [
        [
            InlineKeyboardButton("📢 Рассылка", callback_data="admin:broadcast"),
            InlineKeyboardButton("📊 Статистика", callback_data="admin:stats")
        ],
        [
            InlineKeyboardButton("👥 Пользователи", callback_data="admin:users"),
            InlineKeyboardButton("🎮 Игры", callback_data="admin:games")
        ],
        [
            InlineKeyboardButton("⚙️ Настройки", callback_data="admin:settings"),
            InlineKeyboardButton("🔄 Автопост", callback_data="admin:autopost")
        ],
        [
            InlineKeyboardButton("📝 Логи", callback_data="admin:logs"),
            InlineKeyboardButton("ℹ️ Помощь", callback_data="admin:help")
        ]
    ]

    text = (
        "🔧 **АДМИН-ПАНЕЛЬ**\n\n"
        "Выберите раздел для управления:"
    )

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


# ===============================
# Обработка callback'ов админ-панели
# ===============================
async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для админ-панели"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    
    if action == "broadcast":
        await show_broadcast_info(query, context)
    
    elif action == "stats":
        await show_stats(query, context)
    
    elif action == "users":
        await show_users_info(query, context)
    
    elif action == "games":
        await show_games_info(query, context)
    
    elif action == "settings":
        await show_settings(query, context)
    
    elif action == "autopost":
        await show_autopost_info(query, context)
    
    elif action == "logs":
        await show_logs(query, context)
    
    elif action == "help":
        await show_admin_help(query, context)
    
    elif action == "confirm_broadcast":
        await execute_broadcast(update, context)
    
    elif action == "cancel_broadcast":
        await query.edit_message_text("❌ Рассылка отменена")
    
    elif action == "back":
        await show_main_admin_menu(query, context)


# ===============================
# Показ главного меню (для callback)
# ===============================
async def show_main_admin_menu(query, context):
    """Показывает главное меню админки через callback"""
    keyboard = [
        [
            InlineKeyboardButton("📢 Рассылка", callback_data="admin:broadcast"),
            InlineKeyboardButton("📊 Статистика", callback_data="admin:stats")
        ],
        [
            InlineKeyboardButton("👥 Пользователи", callback_data="admin:users"),
            InlineKeyboardButton("🎮 Игры", callback_data="admin:games")
        ],
        [
            InlineKeyboardButton("⚙️ Настройки", callback_data="admin:settings"),
            InlineKeyboardButton("🔄 Автопост", callback_data="admin:autopost")
        ],
        [
            InlineKeyboardButton("📝 Логи", callback_data="admin:logs"),
            InlineKeyboardButton("ℹ️ Помощь", callback_data="admin:help")
        ]
    ]

    text = (
        "🔧 **АДМИН-ПАНЕЛЬ**\n\n"
        "Выберите раздел для управления:"
    )

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


# ===============================
# Рассылка сообщений
# ===============================
async def execute_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполнить рассылку (через CallbackQuery)"""
    query = update.callback_query
    await query.answer()

    broadcast_text = context.user_data.get('broadcast_text')
    if not broadcast_text:
        await query.edit_message_text("❌ Текст рассылки не найден. Попробуйте снова.")
        return

    await query.edit_message_text("📢 Начинаю рассылку...")

    sent_count = 0
    failed_count = 0

    for user_id in user_data.keys():
        try:
            await context.bot.send_message(chat_id=user_id, text=broadcast_text)
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
            failed_count += 1

    await admin_notifications.notify_broadcast(
        sent=sent_count,
        failed=failed_count,
        moderator=query.from_user.username or str(query.from_user.id)
    )

    result_text = (
        f"✅ **Рассылка завершена!**\n\n"
        f"📤 Отправлено: {sent_count}\n"
        f"❌ Не удалось: {failed_count}"
    )

    await query.edit_message_text(result_text, parse_mode='Markdown')
    context.user_data.pop('broadcast_text', None)


# ===============================
# ИСПРАВЛЕННАЯ Команда /say
# ===============================
async def say_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка сообщения пользователю в ЛС от имени бота - ИСПРАВЛЕНО"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return

    if not context.args:
        await update.message.reply_text(
            "📝 **Использование:**\n\n"
            "**Ответом на сообщение (САМЫЙ НАДЁЖНЫЙ):**\n"
            "`/say текст` (reply)\n\n"
            "**По user ID:**\n"
            "`/say 123456789 текст`\n\n"
            "⚠️ **Username (@username) НЕ РАБОТАЕТ** - Telegram не предоставляет API для поиска по username!\n"
            "Используйте только ID или reply.",
            parse_mode='Markdown'
        )
        return
    
    target_user_id = None
    message_text = None
    target_username = "пользователь"
    
    # Вариант 1: Reply на сообщение (САМЫЙ НАДЁЖНЫЙ)
    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username or f"ID_{target_user_id}"
        message_text = ' '.join(context.args)
        
        logger.info(f"Say via reply: target={target_user_id}, username={target_username}")
    
    # Вариант 2: User ID (РАБОТАЕТ)
    elif context.args[0].isdigit():
        target_user_id = int(context.args[0])
        message_text = ' '.join(context.args[1:])
        
        if not message_text.strip():
            await update.message.reply_text("❌ Не указан текст сообщения после ID")
            return
        
        # Пытаемся найти username в локальной базе
        try:
            from data.user_data import get_user_by_id
            user_info = get_user_by_id(target_user_id)
            if user_info:
                target_username = user_info.get('username', f"ID_{target_user_id}")
            else:
                target_username = f"ID_{target_user_id}"
        except Exception as e:
            logger.warning(f"Could not find username for {target_user_id}: {e}")
            target_username = f"ID_{target_user_id}"
        
        logger.info(f"Say via ID: target={target_user_id}, username={target_username}")
    
    # Вариант 3: Username - НЕ ПОДДЕРЖИВАЕТСЯ (объясняем почему)
    elif context.args[0].startswith('@'):
        username = context.args[0][1:]
        await update.message.reply_text(
            f"❌ **Username не поддерживается**\n\n"
            f"Telegram Bot API **не предоставляет** способа найти user_id по username.\n\n"
            f"**Решения:**\n"
            f"1. **Попросите @{username} написать `/start` боту** - тогда он появится в базе\n"
            f"2. **Используйте reply** - ответьте на любое сообщение пользователя\n"
            f"3. **Узнайте его ID** - используйте `/whois` на сообщение пользователя\n\n"
            f"💡 После того как пользователь напишет `/start`, используйте `/whois @{username}` чтобы узнать его ID",
            parse_mode='Markdown'
        )
        return
    
    else:
        await update.message.reply_text(
            "❌ Неверный формат\n\n"
            "**Используйте:**\n"
            "• `/say USER_ID текст` - по ID (работает)\n"
            "• Или reply: `/say текст` - на сообщение (работает)\n\n"
            "⚠️ Username НЕ РАБОТАЕТ из-за ограничений Telegram API",
            parse_mode='Markdown'
        )
        return
    
    # Проверка текста
    if not message_text or not message_text.strip():
        await update.message.reply_text("❌ Не указан текст сообщения")
        return
    
    # Удаляем команду из группы
    if update.effective_chat.type != 'private':
        try:
            await update.message.delete()
            logger.info(f"Deleted /say command from group")
        except Exception as e:
            logger.warning(f"Could not delete say command: {e}")
    
    # Отправляем сообщение
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"📨 **Сообщение от администрации:**\n\n{message_text}",
            parse_mode='Markdown'
        )
        
        logger.info(
            f"✅ Say SUCCESS: admin {update.effective_user.id} -> user {target_user_id}"
        )
        
        # Подтверждение админу
        confirmation = (
            f"✅ **Сообщение доставлено!**\n\n"
            f"👤 Получатель: {target_username}\n"
            f"🆔 ID: `{target_user_id}`\n"
            f"📝 Текст ({len(message_text)} символов):\n"
            f"_{message_text[:100]}{'...' if len(message_text) > 100 else ''}_"
        )
        
        try:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=confirmation,
                parse_mode='Markdown'
            )
        except Exception as conf_error:
            logger.warning(f"Could not send confirmation: {conf_error}")
            if update.effective_chat.type == 'private':
                await update.message.reply_text(
                    f"✅ Сообщение отправлено пользователю {target_user_id}"
                )
            
    except Exception as e:
        logger.error(f"❌ Say FAILED: {e}", exc_info=True)
        
        error_str = str(e).lower()
        
        if "blocked" in error_str:
            reason = "Пользователь заблокировал бота"
        elif "not found" in error_str or "chat not found" in error_str:
            reason = "Пользователь не найден или не запускал бота"
        elif "deactivated" in error_str:
            reason = "Аккаунт пользователя деактивирован"
        elif "forbidden" in error_str:
            reason = "Бот не может писать этому пользователю"
        else:
            reason = str(e)[:150]
        
        error_msg = (
            f"❌ **Не удалось отправить**\n\n"
            f"👤 Получатель: {target_username}\n"
            f"🆔 ID: `{target_user_id}`\n"
            f"📝 Причина: {reason}\n\n"
            f"**Что делать:**\n"
            f"• Попросите пользователя написать `/start` боту\n"
            f"• Проверьте правильность ID\n"
            f"• Убедитесь что пользователь не заблокировал бота"
        )
        
        try:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=error_msg,
                parse_mode='Markdown'
            )
        except:
            if update.effective_chat.type == 'private':
                await update.message.reply_text(
                    f"Ошибка: не удалось отправить сообщение пользователю {target_user_id}"
                )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка сообщения всем пользователям"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📢 **РАССЫЛКА**\n\n"
            "Используйте:\n"
            "`/broadcast текст сообщения`\n\n"
            "⚠️ Сообщение будет отправлено ВСЕМ пользователям бота!",
            parse_mode='Markdown'
        )
        return
    
    message_text = ' '.join(context.args)
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"admin:confirm_broadcast"),
            InlineKeyboardButton("❌ Отменить", callback_data="admin:cancel_broadcast")
        ]
    ]
    
    context.user_data['broadcast_text'] = message_text
    
    await update.message.reply_text(
        f"📢 **Подтверждение рассылки**\n\n"
        f"Будет отправлено:\n\n{message_text}\n\n"
        f"👥 Получателей: {len(user_data)}\n\n"
        f"⚠️ Это действие нельзя отменить!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def sendstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить статистику вручную"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды")
        return
    
    await update.message.reply_text("📊 Отправляю статистику в админскую группу...")
    
    try:
        await admin_notifications.send_statistics()
        await update.message.reply_text("✅ Статистика успешно отправлена!")
    except Exception as e:
        logger.error(f"Error sending stats: {e}")
        await update.message.reply_text(f"❌ Ошибка при отправке статистики: {e}")


# ===============================
# Вспомогательные функции для показа разделов
# ===============================
async def show_broadcast_info(query, context):
    """Показать информацию о рассылке"""
    total_users = len(user_data)
    
    text = (
        "📢 **РАССЫЛКА**\n\n"
        f"👥 Всего пользователей: {total_users}\n\n"
        "Используйте команду:\n"
        "`/broadcast текст сообщения`\n\n"
        "⚠️ Сообщение будет отправлено всем пользователям!"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin:back")]]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def show_stats(query, context):
    """Показать статистику"""
    from data.games_data import word_games, roll_games
    from datetime import datetime, timedelta
    
    total_users = len(user_data)
    active_24h = sum(1 for data in user_data.values() if 
                    datetime.now() - data['last_activity'] <= timedelta(days=1))
    active_7d = sum(1 for data in user_data.values() if 
                   datetime.now() - data['last_activity'] <= timedelta(days=7))
    total_messages = sum(data['message_count'] for data in user_data.values())
    banned_count = sum(1 for data in user_data.values() if data.get('banned'))
    muted_count = sum(1 for data in user_data.values() if 
                     data.get('muted_until') and data['muted_until'] > datetime.now())
    
    games_stats = ""
    for version in ['need', 'try', 'more']:
        active = "✅" if word_games[version]['active'] else "❌"
        participants = len(roll_games[version]['participants'])
        total_words = len(word_games[version]['words'])
        
        games_stats += f"\n{version.upper()}: {active} | Слов: {total_words} | Участников: {participants}"
    
    text = (
        f"📊 **СТАТИСТИКА БОТА**\n\n"
        f"👥 **Пользователи:**\n"
        f"• Всего: {total_users}\n"
        f"• Активных за 24ч: {active_24h}\n"
        f"• Активных за 7д: {active_7d}\n\n"
        f"💬 **Сообщения:**\n"
        f"• Всего: {total_messages}\n"
        f"• Среднее на пользователя: {total_messages // total_users if total_users > 0 else 0}\n\n"
        f"🔨 **Модерация:**\n"
        f"• Забанено: {banned_count}\n"
        f"• В муте: {muted_count}\n\n"
        f"🎮 **Игры:**{games_stats}\n\n"
        f"📈 Используйте `/sendstats` для отправки в админскую группу"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin:stats")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin:back")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def show_users_info(query, context):
    """Показать информацию о пользователях"""
    from data.user_data import get_top_users
    from datetime import datetime, timedelta
    
    total_users = len(user_data)
    active_today = sum(1 for data in user_data.values() if 
                      datetime.now() - data['last_activity'] <= timedelta(hours=24))
    
    top_users = get_top_users(5)
    top_text = "\n".join([
        f"{i+1}. @{user['username']} - {user['message_count']} сообщений"
        for i, user in enumerate(top_users)
    ])
    
    text = (
        f"👥 **ПОЛЬЗОВАТЕЛИ**\n\n"
        f"📊 Всего: {total_users}\n"
        f"🟢 Активных сегодня: {active_today}\n\n"
        f"🏆 **Топ-5 активных:**\n{top_text}\n\n"
        f"Используйте:\n"
        f"• `/top` - топ пользователей\n"
        f"• `/banlist` - список забаненных"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin:users")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin:back")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def show_games_info(query, context):
    """Показать информацию об играх"""
    from data.games_data import word_games, roll_games
    
    text = "🎮 **ИГРЫ**\n\n"
    
    for version in ['need', 'try', 'more']:
        status = "🟢 Активна" if word_games[version]['active'] else "🔴 Неактивна"
        current_word = word_games[version].get('current_word', 'Не выбрано')
        total_words = len(word_games[version]['words'])
        winners = len(word_games[version].get('winners', []))
        participants = len(roll_games[version]['participants'])
        interval = word_games[version]['interval']
        
        text += (
            f"**{version.upper()}:**\n"
            f"• Статус: {status}\n"
            f"• Текущее слово: {current_word if status == '🟢 Активна' else 'N/A'}\n"
            f"• Слов в базе: {total_words}\n"
            f"• Победителей: {winners}\n"
            f"• Участников розыгрыша: {participants}\n"
            f"• Интервал попыток: {interval} мин\n\n"
        )
    
    # ИСПРАВЛЕНО: убран f-string с backslash
    commands_text = (
        "📝 **Команды:**\n"
        "• `/needguide`, `/tryguide`, `/moreguide`\n"
        "• `/needstart`, `/trystart`, `/morestart`\n"
        "• `/needrollstart N`, `/tryrollstart N`"
    )
    text += commands_text
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin:games")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin:back")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def show_settings(query, context):
    """Показать настройки"""
    text = (
        "⚙️ **НАСТРОЙКИ БОТА**\n\n"
        f"🤖 Bot Token: {'✅ Установлен' if Config.BOT_TOKEN else '❌ Не установлен'}\n"
        f"📢 Канал: {Config.TARGET_CHANNEL_ID}\n"
        f"👮 Группа модерации: {Config.MODERATION_GROUP_ID}\n"
        f"🔧 Админская группа: {Config.ADMIN_GROUP_ID}\n"
        f"👑 Админов: {len(Config.ADMIN_IDS)}\n"
        f"👮 Модераторов: {len(Config.MODERATOR_IDS)}\n"
        f"⏱️ Кулдаун: {Config.COOLDOWN_SECONDS // 3600} часов\n"
        f"🔄 Автопост: {'✅ Включен' if Config.SCHEDULER_ENABLED else '❌ Выключен'}\n"
        f"📊 Статистика: каждые {Config.STATS_INTERVAL_HOURS} часов\n\n"
        "Для изменения настроек используйте переменные окружения или .env файл"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin:back")]]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def show_autopost_info(query, context):
    """Показать информацию об автопостинге"""
    from services.autopost_service import autopost_service
    
    status_info = autopost_service.get_status()
    status = "🟢 Активен" if status_info['running'] else "🔴 Остановлен"
    
    text = (
        f"🔄 **АВТОПОСТИНГ**\n\n"
        f"Статус: {status}\n"
        f"⏱️ Интервал: {Config.SCHEDULER_MIN_INTERVAL}-{Config.SCHEDULER_MAX_INTERVAL} минут\n\n"
        "**Команды:**\n"
        "• `/autopost` - управление автопостингом\n"
        "• `/autoposttest` - тестовая публикация"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin:autopost")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin:back")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def show_logs(query, context):
    """Показать последние логи"""
    text = (
        "📝 **ЛОГИ**\n\n"
        "Последние действия системы:\n\n"
        "Для просмотра полных логов проверьте файлы на сервере или Railway logs.\n\n"
        "**Основные команды для мониторинга:**\n"
        "• `/stats` - статистика\n"
        "• `/sendstats` - отправить в админскую группу\n"
        "• `/banlist` - список забаненных\n"
        "• `/top` - топ пользователей"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin:back")]]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def show_admin_help(query, context):
    """Показать справку для админов"""
    text = (
        "ℹ️ **СПРАВКА ДЛЯ АДМИНОВ**\n\n"
        "**📢 Рассылка:**\n"
        "• `/broadcast текст` - отправить всем\n"
        "• `/say USER_ID текст` - отправить по ID\n"
        "• `/say текст` (reply) - ответить пользователю\n\n"
        "**📊 Статистика:**\n"
        "• `/stats` - общая статистика\n"
        "• `/sendstats` - в админскую группу\n"
        "• `/top` - топ пользователей\n\n"
        "**👥 Модерация:**\n"
        "• `/ban @user причина`\n"
        "• `/unban @user`\n"
        "• `/mute @user время`\n"
        "• `/unmute @user`\n"
        "• `/banlist`\n\n"
        "**🎮 Игры:**\n"
        "• `/needadd`, `/tryadd`, `/moreadd`\n"
        "• `/needstart`, `/trystart`, `/morestart`\n"
        "• `/needrollstart N`\n\n"
        "**🔄 Автопостинг:**\n"
        "• `/autopost` - управление\n"
        "• `/autoposttest` - тест\n\n"
        "**ℹ️ Информация:**\n"
        "• `/id` - узнать ID\n"
        "• `/chatinfo` - информация о чате"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin:back")]]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


# ===============================
# Экспорт функций
# ===============================
__all__ = [
    'admin_command',
    'execute_broadcast',
    'say_command',
    'broadcast_command',
    'sendstats_command',
    'handle_admin_callback'
]
