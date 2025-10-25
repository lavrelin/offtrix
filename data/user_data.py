# -*- coding: utf-8 -*-
"""
User Data Management
Хранение данных пользователей и команд
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Хранилище данных пользователей
user_data: Dict[int, Dict] = {}

# Счетчик команд
command_stats: Dict[str, int] = {}

# Участники лотереи
lottery_participants: Dict[int, Dict] = {}

def update_user_activity(user_id: int, username: Optional[str] = None):
    """Обновить активность пользователя"""
    if user_id not in user_data:
        user_data[user_id] = {
            'id': user_id,
            'username': username or f'ID_{user_id}',
            'join_date': datetime.now(),
            'last_activity': datetime.now(),
            'message_count': 0,
            'command_count': 0,
            'banned': False,
            'muted_until': None
        }
    else:
        user_data[user_id]['last_activity'] = datetime.now()
        if username:
            user_data[user_id]['username'] = username

def increment_command(command_name: str, user_id: int):
    """Увеличить счетчик команды"""
    # Глобальная статистика команд
    if command_name not in command_stats:
        command_stats[command_name] = 0
    command_stats[command_name] += 1
    
    # Статистика пользователя
    if user_id in user_data:
        user_data[user_id]['command_count'] = user_data[user_id].get('command_count', 0) + 1

def increment_message(user_id: int):
    """Увеличить счетчик сообщений пользователя"""
    if user_id in user_data:
        user_data[user_id]['message_count'] = user_data[user_id].get('message_count', 0) + 1

def get_top_commands(limit: int = 5) -> List[Tuple[str, int]]:
    """Получить топ команд"""
    sorted_commands = sorted(command_stats.items(), key=lambda x: x[1], reverse=True)
    return sorted_commands[:limit]

def get_top_users(limit: int = 10) -> List[Dict]:
    """Получить топ пользователей по активности"""
    sorted_users = sorted(
        user_data.values(),
        key=lambda x: x.get('message_count', 0),
        reverse=True
    )
    return sorted_users[:limit]

def get_user_by_username(username: str) -> Optional[Dict]:
    """Получить пользователя по username"""
    for user in user_data.values():
        if user.get('username', '').lower() == username.lower():
            return user
    return None

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Получить пользователя по ID"""
    return user_data.get(user_id)

def is_user_banned(user_id: int) -> bool:
    """Проверить, забанен ли пользователь"""
    if user_id not in user_data:
        return False
    return user_data[user_id].get('banned', False)

def ban_user(user_id: int, reason: str = "Не указана"):
    """Забанить пользователя"""
    if user_id in user_data:
        user_data[user_id]['banned'] = True
        user_data[user_id]['ban_reason'] = reason
        user_data[user_id]['banned_at'] = datetime.now()

def unban_user(user_id: int):
    """Разбанить пользователя"""
    if user_id in user_data:
        user_data[user_id]['banned'] = False
        user_data[user_id]['ban_reason'] = None
        user_data[user_id]['banned_at'] = None

def mute_user(user_id: int, until: datetime):
    """Замутить пользователя"""
    if user_id in user_data:
        user_data[user_id]['muted_until'] = until

def unmute_user(user_id: int):
    """Размутить пользователя"""
    if user_id in user_data:
        user_data[user_id]['muted_until'] = None

def get_banned_users() -> List[Dict]:
    """Получить список забаненных пользователей"""
    return [user for user in user_data.values() if user.get('banned', False)]

__all__ = [
    'user_data',
    'command_stats',
    'lottery_participants',
    'update_user_activity',
    'increment_command',
    'increment_message',
    'get_top_commands',
    'get_top_users',
    'get_user_by_username',
    'get_user_by_id',
    'is_user_banned',
    'ban_user',
    'unban_user',
    'mute_user',
    'unmute_user',
    'get_banned_users',
]
