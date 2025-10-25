# -*- coding: utf-8 -*-
"""
Games Handler - OPTIMIZED v5.2
- Уникальные префиксы callback_data: gmc_
- Сокращенные функции
- Три версии игр: NEED, TRY, MORE
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
import logging
import random
from datetime import datetime, timedelta
from data.games_data import (
    word_games, roll_games, user_attempts,
    can_attempt, record_attempt, normalize_word, get_unique_roll_number
)
from data.user_data import update_user_activity, is_user_banned, is_user_muted

logger = logging.getLogger(__name__)

# ============= CALLBACK PREFIXES =============
GAME_CALLBACKS = {
    'skip_media': 'gmc_skip_media',
    'finish': 'gmc_finish',
}

# ============= GAME VERSIONS =============
GAME_VERSIONS = {'try': 'try', 'need': 'need', 'more': 'more'}

game_waiting = {}

def get_game_version_from_command(command_text: str) -> str:
    """Extract game version from command"""
    command_lower = command_text.lower()
    for version in ['need', 'more', 'try']:
        if version in command_lower:
            return version
    return 'try'

# ============= WORD COMMANDS (ADMIN) =============

async def wordadd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add word - admin only"""
    if not Config.is_admin(update.effective_user.id):
        if update.effective_chat.type == 'private':
            await update.message.reply_text("❌ Нет прав")
        return
    
    game_version = get_game_version_from_command(update.message.text)
    
    if not context.args:
        await update.message.reply_text(
            f"🔧 **АДМИН КОМАНДЫ [{game_version.upper()}]**\n\n"
            f"🎯 Слова:\n"
            f"/{game_version}add слово\n"
            f"/{game_version}edit слово описание\n"
            f"/{game_version}start\n"
            f"/{game_version}stop\n\n"
            f"🎲 Розыгрыш:\n"
            f"/{game_version}rollstart 1-5\n"
            f"/{game_version}reroll",
            parse_mode='Markdown'
        )
        return
    
    word = context.args[0].lower()
    user_id = update.effective_user.id
    
    game_waiting[user_id] = {
        'action': 'add_word_description',
        'game_version': game_version,
        'word': word
    }
    
    word_games[game_version]['words'][word] = {
        'description': f'Угадайте слово: {word}',
        'hints': [],
        'media': []
    }
    
    keyboard = [[InlineKeyboardButton(
        "⏭️ Пропустить", 
        callback_data=f"{GAME_CALLBACKS['skip_media']}:{game_version}:{word}"
    )]]
    
    await update.message.reply_text(
        f"✅ Слово добавлено в {game_version.upper()}\n\n"
        f"🎯 Слово: {word}\n\n"
        f"📝 Отправьте описание или нажмите 'Пропустить'",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_game_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle text for games"""
    user_id = update.effective_user.id
    
    if user_id not in game_waiting:
        return False
    
    action_data = game_waiting[user_id]
    action = action_data.get('action')
    text = update.message.text
    
    if action == 'add_word_description':
        game_version = action_data['game_version']
        word = action_data['word']
        
        word_games[game_version]['words'][word]['description'] = text
        
        game_waiting[user_id] = {
            'action': 'add_word_media',
            'game_version': game_version,
            'word': word
        }
        
        keyboard = [[InlineKeyboardButton(
            "✅ Завершить", 
            callback_data=f"{GAME_CALLBACKS['finish']}:{game_version}:{word}"
        )]]
        
        await update.message.reply_text(
            f"✅ Описание сохранено [{game_version.upper()}]\n\n"
            f"📸 Теперь можете отправить фото/видео или нажмите 'Завершить'",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return True
    
    return False

async def handle_game_media_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle media for games"""
    user_id = update.effective_user.id
    
    if user_id not in game_waiting:
        return False
    
    action_data = game_waiting[user_id]
    action = action_data.get('action')
    
    if action == 'add_word_media':
        game_version = action_data['game_version']
        word = action_data['word']
        
        media_data = None
        if update.message.photo:
            media_data = {'type': 'photo', 'file_id': update.message.photo[-1].file_id}
        elif update.message.video:
            media_data = {'type': 'video', 'file_id': update.message.video.file_id}
        else:
            return False
        
        word_games[game_version]['words'][word]['media'].append(media_data)
        media_count = len(word_games[game_version]['words'][word]['media'])
        
        keyboard = [[InlineKeyboardButton(
            "✅ Завершить", 
            callback_data=f"{GAME_CALLBACKS['finish']}:{game_version}:{word}"
        )]]
        
        await update.message.reply_text(
            f"✅ Медиа добавлено ({media_count}) [{game_version.upper()}]\n\n"
            f"Можете добавить еще или нажмите 'Завершить'",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return True
    
    return False

async def wordedit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit word"""
    if not Config.is_admin(update.effective_user.id):
        if update.effective_chat.type == 'private':
            await update.message.reply_text("❌ Нет прав")
        return
    
    game_version = get_game_version_from_command(update.message.text)
    
    if len(context.args) < 2:
        await update.message.reply_text(f"📝 Использование: /{game_version}edit слово описание")
        return
    
    word = context.args[0].lower()
    new_description = ' '.join(context.args[1:])
    
    if word not in word_games[game_version]['words']:
        await update.message.reply_text(f"❌ Слово '{word}' не найдено")
        return
    
    word_games[game_version]['words'][word]['description'] = new_description
    await update.message.reply_text(f"✅ Слово обновлено в {game_version.upper()}")

async def wordon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start contest"""
    if not Config.is_admin(update.effective_user.id):
        if update.effective_chat.type == 'private':
            await update.message.reply_text("❌ Нет прав")
        return
    
    game_version = get_game_version_from_command(update.message.text)
    
    if not word_games[game_version]['words']:
        await update.message.reply_text(f"❌ Нет слов. Добавьте: /{game_version}add")
        return
    
    current_word = random.choice(list(word_games[game_version]['words'].keys()))
    
    word_games[game_version].update({
        'current_word': current_word,
        'active': True,
        'winners': []
    })
    
    description = word_games[game_version]['words'][current_word]['description']
    media = word_games[game_version]['words'][current_word].get('media', [])
    
    # Send media
    for media_item in media:
        try:
            if media_item['type'] == 'photo':
                await update.message.reply_photo(
                    photo=media_item['file_id'],
                    caption=f"📸 Подсказка [{game_version.upper()}]"
                )
            elif media_item['type'] == 'video':
                await update.message.reply_video(
                    video=media_item['file_id'],
                    caption=f"🎥 Подсказка [{game_version.upper()}]"
                )
        except Exception as e:
            logger.error(f"Error sending media: {e}")
    
    await update.message.reply_text(
        f"🎮 Конкурс {game_version.upper()} НАЧАЛСЯ!\n\n"
        f"📝 {description}\n\n"
        f"🎯 /{game_version}slovo слово для участия\n"
        f"⏰ Интервал: {word_games[game_version]['interval']} мин"
    )

async def wordoff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop contest"""
    if not Config.is_admin(update.effective_user.id):
        if update.effective_chat.type == 'private':
            await update.message.reply_text("❌ Нет прав")
        return
    
    game_version = get_game_version_from_command(update.message.text)
    
    word_games[game_version]['active'] = False
    current_word = word_games[game_version]['current_word']
    winners = word_games[game_version]['winners']
    
    winner_text = (
        f"🏆 Победители: {', '.join([f'@{w}' for w in winners])}"
        if winners else "🏆 Победителей не было"
    )
    
    await update.message.reply_text(
        f"🛑 Конкурс {game_version.upper()} ЗАВЕРШЕН!\n\n"
        f"🎯 Слово было: {current_word or 'не выбрано'}\n"
        f"{winner_text}"
    )

async def wordinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show word info"""
    game_version = get_game_version_from_command(update.message.text)
    
    if not word_games[game_version]['active']:
        description = word_games[game_version].get('description', f"Конкурс {game_version.upper()} неактивен")
        await update.message.reply_text(f"ℹ️ [{game_version.upper()}]:\n\n📝 {description}")
        return
    
    current_word = word_games[game_version]['current_word']
    if current_word and current_word in word_games[game_version]['words']:
        description = word_games[game_version]['words'][current_word]['description']
        media = word_games[game_version]['words'][current_word].get('media', [])
        
        # Send media
        for media_item in media:
            try:
                if media_item['type'] == 'photo':
                    await update.message.reply_photo(
                        photo=media_item['file_id'],
                        caption=f"📸 Подсказка [{game_version.upper()}]"
                    )
                elif media_item['type'] == 'video':
                    await update.message.reply_video(
                        video=media_item['file_id'],
                        caption=f"🎥 Подсказка [{game_version.upper()}]"
                    )
            except Exception as e:
                logger.error(f"Error sending media: {e}")
        
        await update.message.reply_text(
            f"🎯 Информация [{game_version.upper()}]:\n\n"
            f"📝 {description}\n\n"
            f"💡 /{game_version}slovo слово"
        )
    else:
        await update.message.reply_text(f"❌ Нет активного слова")

async def game_say_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guess word"""
    game_version = get_game_version_from_command(update.message.text)
    
    if not context.args:
        await update.message.reply_text(f"📝 Использование: /{game_version}slovo слово")
        return
    
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID_{user_id}"
    guess = context.args[0]
    
    update_user_activity(user_id, username)
    
    if is_user_banned(user_id) or is_user_muted(user_id):
        await update.message.reply_text("❌ Вы не можете участвовать")
        return
    
    if not word_games[game_version]['active']:
        await update.message.reply_text(f"❌ Конкурс {game_version.upper()} неактивен")
        return
    
    if not can_attempt(user_id, game_version):
        interval = word_games[game_version]['interval']
        await update.message.reply_text(f"⏰ Подождите {interval} минут")
        return
    
    record_attempt(user_id, game_version)
    current_word = word_games[game_version]['current_word']
    
    # Notify mods
    try:
        await context.bot.send_message(
            chat_id=Config.MODERATION_GROUP_ID,
            text=(
                f"🎮 Попытка [{game_version.upper()}]\n\n"
                f"👤 @{username} (ID: {user_id})\n"
                f"🎯 Попытка: {guess}\n"
                f"✅ Ответ: {current_word}"
            )
        )
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
    
    if normalize_word(guess) == normalize_word(current_word):
        word_games[game_version]['winners'].append(username)
        word_games[game_version]['active'] = False
        
        await update.message.reply_text(
            f"🎉 ПОЗДРАВЛЯЕМ [{game_version.upper()}]!\n\n"
            f"@{username}, вы угадали '{current_word}'!\n\n"
            f"👑 Администратор свяжется с вами."
        )
        
        try:
            await context.bot.send_message(
                chat_id=Config.MODERATION_GROUP_ID,
                text=(
                    f"🏆 ПОБЕДИТЕЛЬ {game_version.upper()}!\n\n"
                    f"👤 @{username} (ID: {user_id})\n"
                    f"🎯 Угадал: {current_word}\n\n"
                    f"Свяжитесь с победителем!"
                )
            )
        except Exception as e:
            logger.error(f"Error sending winner notification: {e}")
    else:
        await update.message.reply_text(
            f"❌ Неправильно [{game_version.upper()}]. "
            f"Попробуйте через {word_games[game_version]['interval']} мин"
        )

# ============= ROLL COMMANDS =============

async def roll_participant_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get number for roll"""
    game_version = get_game_version_from_command(update.message.text)
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID_{user_id}"
    
    update_user_activity(user_id, username)
    
    if is_user_banned(user_id) or is_user_muted(user_id):
        await update.message.reply_text("❌ Вы не можете участвовать")
        return
    
    if user_id in roll_games[game_version]['participants']:
        number = roll_games[game_version]['participants'][user_id]['number']
        await update.message.reply_text(f"@{username}, ваш номер: {number}")
        return
    
    number = get_unique_roll_number(game_version)
    
    roll_games[game_version]['participants'][user_id] = {
        'username': username,
        'number': number,
        'joined_at': datetime.now()
    }
    
    await update.message.reply_text(
        f"@{username}, ваш номер: {number}\n\n"
        f"🎲 Участников: {len(roll_games[game_version]['participants'])}"
    )

async def mynumber_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show my number"""
    game_version = get_game_version_from_command(update.message.text)
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID_{user_id}"
    
    if user_id not in roll_games[game_version]['participants']:
        await update.message.reply_text(
            f"@{username}, вы не участвуете\n"
            f"/{game_version}roll для участия"
        )
        return
    
    number = roll_games[game_version]['participants'][user_id]['number']
    await update.message.reply_text(f"@{username}, ваш номер: {number}")

async def roll_draw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Draw winners - FIXED: with notifications"""
    if not Config.is_admin(update.effective_user.id):
        if update.effective_chat.type == 'private':
            await update.message.reply_text("❌ Нет прав")
        return
    
    game_version = get_game_version_from_command(update.message.text)
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(f"📝 /{game_version}rollstart 3")
        return
    
    winners_count = min(5, max(1, int(context.args[0])))
    participants = roll_games[game_version]['participants']
    
    if len(participants) < winners_count:
        await update.message.reply_text(f"❌ Недостаточно участников")
        return
    
    winning_number = random.randint(1, 9999)
    
    participants_list = [
        (user_id, data['username'], data['number'])
        for user_id, data in participants.items()
    ]
    
    participants_list.sort(key=lambda x: abs(x[2] - winning_number))
    winners = participants_list[:winners_count]
    
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    winners_text = []
    
    for i, (user_id, username, number) in enumerate(winners, 1):
        medal = medals.get(i, f"{i}.")
        diff = abs(number - winning_number)
        winners_text.append(f"{medal} @{username} (номер: {number}, разница: {diff})")
    
    await update.message.reply_text(
        f"🎉 РЕЗУЛЬТАТЫ {game_version.upper()}!\n\n"
        f"🎲 Выигрышное число: {winning_number}\n"
        f"👥 Участвовало: {len(participants)}\n\n"
        f"🏆 Победители:\n" + "\n".join(winners_text)
    )
    
    # Notify each winner
    for i, (user_id, username, number) in enumerate(winners, 1):
        try:
            medal = medals.get(i, f"{i}.")
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"🎉 **ПОЗДРАВЛЯЕМ!**\n\n"
                    f"{medal} Вы заняли {i} место в {game_version.upper()}!\n\n"
                    f"🎲 Выигрышное: {winning_number}\n"
                    f"🎯 Ваш номер: {number}\n"
                    f"📊 Разница: {abs(number - winning_number)}\n\n"
                    f"🎁 Администратор свяжется с вами!"
                ),
                parse_mode='Markdown'
            )
            logger.info(f"Winner notified: {user_id} ({username})")
        except Exception as e:
            logger.error(f"Failed to notify {user_id}: {e}")

async def rollreset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset roll"""
    if not Config.is_admin(update.effective_user.id):
        if update.effective_chat.type == 'private':
            await update.message.reply_text("❌ Нет прав")
        return
    
    game_version = get_game_version_from_command(update.message.text)
    count = len(roll_games[game_version]['participants'])
    roll_games[game_version]['participants'] = {}
    
    await update.message.reply_text(
        f"✅ Розыгрыш {game_version.upper()} сброшен!\n"
        f"📊 Удалено: {count}"
    )

async def rollstatus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Roll status"""
    if not Config.is_admin(update.effective_user.id):
        if update.effective_chat.type == 'private':
            await update.message.reply_text("❌ Нет прав")
        return
    
    game_version = get_game_version_from_command(update.message.text)
    participants = roll_games[game_version]['participants']
    
    if not participants:
        await update.message.reply_text(f"📊 {game_version.upper()}: нет участников")
        return
    
    text = f"📊 Статус [{game_version.upper()}]:\n\n👥 Участников: {len(participants)}\n\n"
    
    for i, (user_id, data) in enumerate(participants.items(), 1):
        text += f"{i}. @{data['username']} - {data['number']}\n"
    
    await update.message.reply_text(text)

# ============= INFO COMMANDS =============

async def gamesinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Game commands info"""
    game_version = get_game_version_from_command(update.message.text)
    
    await update.message.reply_text(
        f"🎮 ИГРОВЫЕ КОМАНДЫ [{game_version.upper()}]:\n\n"
        f"🎯 Угадай слово:\n"
        f"/{game_version}slovo слово\n"
        f"/{game_version}info\n\n"
        f"🎲 Розыгрыш:\n"
        f"/{game_version}roll\n"
        f"/{game_version}myroll"
    )

async def admgamesinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin game commands"""
    if not Config.is_admin(update.effective_user.id):
        if update.effective_chat.type == 'private':
            await update.message.reply_text("❌ Нет прав")
        return
    
    game_version = get_game_version_from_command(update.message.text)
    
    await update.message.reply_text(
        f"🔧 АДМИН [{game_version.upper()}]:\n\n"
        f"🎯 Слова:\n"
        f"/{game_version}add слово\n"
        f"/{game_version}edit слово описание\n"
        f"/{game_version}start\n"
        f"/{game_version}stop\n\n"
        f"🎲 Розыгрыш:\n"
        f"/{game_version}rollstart 1-5\n"
        f"/{game_version}reroll"
    )

async def anstimeset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set interval"""
    if not Config.is_admin(update.effective_user.id):
        if update.effective_chat.type == 'private':
            await update.message.reply_text("❌ Нет прав")
        return
    
    game_version = get_game_version_from_command(update.message.text)
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(f"📝 /{game_version}timeset 60")
        return
    
    minutes = int(context.args[0])
    word_games[game_version]['interval'] = minutes
    
    await update.message.reply_text(f"✅ Интервал [{game_version.upper()}]: {minutes} мин")

async def wordinfoedit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit contest description"""
    if not Config.is_admin(update.effective_user.id):
        if update.effective_chat.type == 'private':
            await update.message.reply_text("❌ Нет прав")
        return
    
    game_version = get_game_version_from_command(update.message.text)
    
    if not context.args:
        await update.message.reply_text(f"📝 /{game_version}infoedit текст")
        return
    
    new_description = ' '.join(context.args)
    word_games[game_version]['description'] = new_description
    
    await update.message.reply_text(f"✅ Описание [{game_version.upper()}]:\n\n{new_description}")

async def handle_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle game callbacks"""
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split(":")
    
    # Remove prefix
    if data_parts[0].startswith('gmc_'):
        action = data_parts[0][4:]
    else:
        action = data_parts[0]
    
    if action == 'skip_media':
        game_version = data_parts[1] if len(data_parts) > 1 else None
        word = data_parts[2] if len(data_parts) > 2 else None
        
        user_id = update.effective_user.id
        game_waiting.pop(user_id, None)
        
        await query.edit_message_text(
            f"✅ Слово добавлено [{game_version.upper()}]:\n\n"
            f"📝 {word}\n\n"
            f"/{game_version}start для запуска"
        )
    
    elif action == 'finish':
        game_version = data_parts[1] if len(data_parts) > 1 else None
        word = data_parts[2] if len(data_parts) > 2 else None
        
        user_id = update.effective_user.id
        game_waiting.pop(user_id, None)
        
        media_count = len(word_games[game_version]['words'][word].get('media', []))
        
        await query.edit_message_text(
            f"✅ Слово готово [{game_version.upper()}]:\n\n"
            f"📝 {word}\n"
            f"📸 Медиа: {media_count}\n\n"
            f"/{game_version}start для запуска"
        )

async def wordclear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Old command - redirect"""
    await update.message.reply_text(
        "ℹ️ Используйте новые команды:\n"
        "/need, /try, /more"
    )

__all__ = [
    'wordadd_command', 'wordedit_command', 'wordclear_command',
    'wordon_command', 'wordoff_command', 'wordinfo_command',
    'wordinfoedit_command', 'anstimeset_command',
    'gamesinfo_command', 'admgamesinfo_command', 'game_say_command',
    'roll_participant_command', 'roll_draw_command',
    'rollreset_command', 'rollstatus_command', 'mynumber_command',
    'handle_game_text_input', 'handle_game_media_input', 'handle_game_callback',
    'GAME_CALLBACKS',
]
