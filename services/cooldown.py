# -*- coding: utf-8 -*-
"""
Cooldown Service v2.0 - Расширенная система кулдаунов
- Декораторы для команд
- Разные типы кулдаунов (обычные, ежедневные, недельные, глобальные)
- Сохранение в БД
- Логирование использования
- Автоматическая очистка
"""
from datetime import datetime, timedelta
from services.db import db
from models import User
from sqlalchemy import select, text
from config import Config
import logging
from functools import wraps
from typing import Optional, Dict, Any, Callable, Tuple
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

class CooldownType(str, Enum):
    """Типы кулдаунов"""
    NORMAL = 'normal'           # Обычный кулдаун
    DAILY = 'daily'             # Ежедневный (сбрасывается в полночь)
    WEEKLY = 'weekly'           # Недельный (сбрасывается в понедельник)
    GLOBAL = 'global'           # Глобальный на все команды

class CooldownService:
    """Service for managing post cooldowns с расширенным функционалом"""
    
    def __init__(self):
        self._cache: Dict[int, Dict[str, Dict[str, Any]]] = {}
        self._usage_log: list = []
        self._global_cooldowns: Dict[int, datetime] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_running = False
    
    # ============= ДЕКОРАТОРЫ =============
    
    def cooldown(
        self, 
        seconds: int = None,
        cooldown_type: CooldownType = CooldownType.NORMAL,
        command_name: str = None,
        bypass_for_mods: bool = True
        # Проверка кулдауна
        can_use, remaining = await cooldown_service.check_cooldown(
        user_id=user_id,
        command='itsme',
        duration=24 * 3600,
        cooldown_type=CooldownType.NORMAL
    )

    # Установка кулдауна
    await cooldown_service.set_cooldown(
        user_id=user_id,
        command='itsme',
        duration=24 * 3600,
        cooldown_type=CooldownType.NORMAL
    )
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(update, context, *args, **kwargs):
                user_id = update.effective_user.id
                cmd_name = command_name or func.__name__
                
                # Пропускаем модераторов если указано
                if bypass_for_mods and Config.is_moderator(user_id):
                    return await func(update, context, *args, **kwargs)
                
                # Проверяем кулдаун
                can_use, remaining = await self.check_cooldown(
                    user_id, 
                    cmd_name, 
                    seconds or Config.COOLDOWN_SECONDS,
                    cooldown_type
                )
                
                if not can_use:
                    await self._send_cooldown_message(update, remaining, cmd_name)
                    return
                
                # Логируем использование
                self._log_usage(user_id, cmd_name)
                
                # Выполняем команду
                result = await func(update, context, *args, **kwargs)
                
                # Устанавливаем кулдаун после успешного выполнения
                await self.set_cooldown(
                    user_id, 
                    cmd_name, 
                    seconds or Config.COOLDOWN_SECONDS,
                    cooldown_type
                )
                
                return result
            
            return wrapper
        return decorator
    
    async def _send_cooldown_message(self, update, remaining: int, command: str):
        """Отправка сообщения о кулдауне"""
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        secs = remaining % 60
        
        if hours > 0:
            time_str = f"{hours}ч {minutes}м"
        elif minutes > 0:
            time_str = f"{minutes}м {secs}с"
        else:
            time_str = f"{secs}с"
        
        await update.message.reply_text(
            f"⏳ Команда `/{command}` недоступна\n"
            f"⏰ Подождите: {time_str}",
            parse_mode='Markdown'
        )
    
    # ============= ОСНОВНЫЕ МЕТОДЫ =============
    
    async def check_cooldown(
        self, 
        user_id: int, 
        command: str, 
        duration: int,
        cooldown_type: CooldownType = CooldownType.NORMAL
    ) -> Tuple[bool, int]:
        """
        Проверка кулдауна
        Returns: (can_use: bool, remaining_seconds: int)
        """
        try:
            # Модераторы всегда могут использовать
            if Config.is_moderator(user_id):
                return True, 0
            
            # Проверяем глобальный кулдаун
            if await self._check_global_cooldown(user_id):
                remaining = await self._get_global_remaining(user_id)
                return False, remaining
            
            # Проверяем кэш
            if user_id in self._cache and command in self._cache[user_id]:
                cooldown_data = self._cache[user_id][command]
                
                # Проверяем тип кулдауна
                if self._is_cooldown_expired(cooldown_data, cooldown_type):
                    return True, 0
                
                remaining = self._calculate_remaining(cooldown_data)
                if remaining > 0:
                    return False, remaining
            
            # Проверяем БД если доступна
            if db.session_maker:
                db_remaining = await self._check_db_cooldown(user_id, command)
                if db_remaining > 0:
                    return False, db_remaining
            
            return True, 0
            
        except Exception as e:
            logger.error(f"Error checking cooldown: {e}")
            return True, 0
    
    async def set_cooldown(
        self, 
        user_id: int, 
        command: str, 
        duration: int,
        cooldown_type: CooldownType = CooldownType.NORMAL
    ):
        """Установить кулдаун"""
        try:
            if Config.is_moderator(user_id):
                return
            
            expires_at = self._calculate_expiry(duration, cooldown_type)
            
            # Обновляем кэш
            if user_id not in self._cache:
                self._cache[user_id] = {}
            
            self._cache[user_id][command] = {
                'type': cooldown_type,
                'expires_at': expires_at,
                'set_at': datetime.utcnow(),
                'count': self._cache[user_id].get(command, {}).get('count', 0) + 1
            }
            
            logger.info(f"Cooldown set for user {user_id}, command {command}, type {cooldown_type}")
            
            # Сохраняем в БД
            await self._save_to_db(user_id, command, expires_at, cooldown_type)
            
        except Exception as e:
            logger.error(f"Error setting cooldown: {e}")
    
    async def reset_cooldown(self, user_id: int, command: Optional[str] = None) -> bool:
        """Сбросить кулдаун (команда /cdreset)"""
        try:
            # Сброс из кэша
            if command:
                if user_id in self._cache and command in self._cache[user_id]:
                    del self._cache[user_id][command]
                    logger.info(f"Reset cooldown cache for user {user_id}, command {command}")
            else:
                if user_id in self._cache:
                    self._cache.pop(user_id)
                    logger.info(f"Reset all cooldowns cache for user {user_id}")
            
            # Сброс в БД
            if db.session_maker:
                await self._reset_db_cooldown(user_id, command)
            
            return True
            
        except Exception as e:
            logger.error(f"Error resetting cooldown: {e}")
            return False
    
    # ============= ТИПЫ КУЛДАУНОВ =============
    
    def _calculate_expiry(self, duration: int, cooldown_type: CooldownType) -> datetime:
        """Вычислить время истечения в зависимости от типа"""
        now = datetime.utcnow()
        
        if cooldown_type == CooldownType.NORMAL:
            return now + timedelta(seconds=duration)
        
        elif cooldown_type == CooldownType.DAILY:
            # До конца дня
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            return tomorrow
        
        elif cooldown_type == CooldownType.WEEKLY:
            # До начала следующей недели (понедельник)
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_monday = (now + timedelta(days=days_until_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return next_monday
        
        return now + timedelta(seconds=duration)
    
    def _is_cooldown_expired(self, cooldown_data: dict, cooldown_type: CooldownType) -> bool:
        """Проверить истек ли кулдаун"""
        expires_at = cooldown_data.get('expires_at')
        if not expires_at:
            return True
        
        return datetime.utcnow() >= expires_at
    
    def _calculate_remaining(self, cooldown_data: dict) -> int:
        """Вычислить оставшееся время"""
        expires_at = cooldown_data.get('expires_at')
        if not expires_at:
            return 0
        
        remaining = (expires_at - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))
    
    # ============= ГЛОБАЛЬНЫЙ КУЛДАУН =============
    
    async def set_global_cooldown(self, user_id: int, duration: int = 10):
        """Установить глобальный кулдаун на все команды (защита от спама)"""
        if Config.is_moderator(user_id):
            return
        
        self._global_cooldowns[user_id] = datetime.utcnow() + timedelta(seconds=duration)
        logger.info(f"Global cooldown set for user {user_id}, duration {duration}s")
    
    async def _check_global_cooldown(self, user_id: int) -> bool:
        """Проверить глобальный кулдаун"""
        if user_id not in self._global_cooldowns:
            return False
        
        if datetime.utcnow() >= self._global_cooldowns[user_id]:
            del self._global_cooldowns[user_id]
            return False
        
        return True
    
    async def _get_global_remaining(self, user_id: int) -> int:
        """Получить оставшееся время глобального кулдауна"""
        if user_id not in self._global_cooldowns:
            return 0
        
        remaining = (self._global_cooldowns[user_id] - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))
    
    # ============= РАБОТА С БД =============
    
    async def _check_db_cooldown(self, user_id: int, command: str) -> int:
        """Проверка кулдауна в БД"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user or not hasattr(user, 'cooldown_expires_at'):
                    return 0
                
                if user.cooldown_expires_at and user.cooldown_expires_at > datetime.utcnow():
                    remaining = int((user.cooldown_expires_at - datetime.utcnow()).total_seconds())
                    return remaining
                
                return 0
                
        except Exception as e:
            logger.warning(f"DB cooldown check error: {e}")
            return 0
    
    async def _save_to_db(self, user_id: int, command: str, expires_at: datetime, cooldown_type: CooldownType):
        """Сохранить кулдаун в БД"""
        if not db.session_maker:
            return
        
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if user and hasattr(user, 'cooldown_expires_at'):
                    user.cooldown_expires_at = expires_at
                    await session.commit()
                    logger.debug(f"Cooldown saved to DB for user {user_id}")
                    
        except Exception as e:
            logger.warning(f"Could not save cooldown to DB: {e}")
    
    async def _reset_db_cooldown(self, user_id: int, command: Optional[str] = None):
        """Сбросить кулдаун в БД"""
        if not db.session_maker:
            return
        
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if user and hasattr(user, 'cooldown_expires_at'):
                    user.cooldown_expires_at = None
                    await session.commit()
                    logger.info(f"Reset cooldown in DB for user {user_id}")
                    
        except Exception as e:
            logger.warning(f"Could not reset cooldown in DB: {e}")
    
    # ============= ЛОГИРОВАНИЕ И АНАЛИТИКА =============
    
    def _log_usage(self, user_id: int, command: str):
        """Логировать использование команды"""
        self._usage_log.append({
            'user_id': user_id,
            'command': command,
            'timestamp': datetime.utcnow()
        })
        
        # Ограничиваем размер лога
        if len(self._usage_log) > 10000:
            self._usage_log = self._usage_log[-5000:]
    
    async def get_usage_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Получить статистику использования за последние N часов"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_logs = [log for log in self._usage_log if log['timestamp'] >= cutoff]
        
        # Группировка по командам
        command_counts = {}
        user_counts = {}
        
        for log in recent_logs:
            cmd = log['command']
            user = log['user_id']
            
            command_counts[cmd] = command_counts.get(cmd, 0) + 1
            user_counts[user] = user_counts.get(user, 0) + 1
        
        return {
            'total_uses': len(recent_logs),
            'unique_users': len(user_counts),
            'command_counts': command_counts,
            'top_users': sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            'hours': hours
        }
    
    async def get_user_cooldown_info(self, user_id: int) -> Dict[str, Any]:
        """Получить информацию о всех кулдаунах пользователя"""
        info = {
            'user_id': user_id,
            'cooldowns': [],
            'global_cooldown': None
        }
        
        # Глобальный кулдаун
        if user_id in self._global_cooldowns:
            remaining = await self._get_global_remaining(user_id)
            if remaining > 0:
                info['global_cooldown'] = {
                    'remaining_seconds': remaining,
                    'expires_at': self._global_cooldowns[user_id]
                }
        
        # Кулдауны по командам
        if user_id in self._cache:
            for command, data in self._cache[user_id].items():
                remaining = self._calculate_remaining(data)
                if remaining > 0:
                    info['cooldowns'].append({
                        'command': command,
                        'type': data['type'],
                        'remaining_seconds': remaining,
                        'expires_at': data['expires_at'],
                        'usage_count': data.get('count', 0)
                    })
        
        return info
    
    # ============= АВТООЧИСТКА =============
    
    async def start_cleanup_task(self):
        """Запустить задачу автоматической очистки"""
        if self._cleanup_running:
            logger.warning("Cleanup task already running")
            return
        
        self._cleanup_running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Cooldown cleanup task started")
    
    async def stop_cleanup_task(self):
        """Остановить задачу автоочистки"""
        self._cleanup_running = False
        
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Cooldown cleanup task stopped")
    
    async def _cleanup_loop(self):
        """Цикл автоматической очистки истекших кулдаунов"""
        while self._cleanup_running:
            try:
                await asyncio.sleep(300)  # Каждые 5 минут
                
                cleaned_count = await self.cleanup_expired()
                if cleaned_count > 0:
                    logger.info(f"Cleaned {cleaned_count} expired cooldowns")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)
    
    async def cleanup_expired(self) -> int:
        """Очистить истекшие кулдауны"""
        cleaned = 0
        
        # Очистка кэша
        for user_id in list(self._cache.keys()):
            for command in list(self._cache[user_id].keys()):
                data = self._cache[user_id][command]
                if self._is_cooldown_expired(data, data['type']):
                    del self._cache[user_id][command]
                    cleaned += 1
            
            # Удаляем пустые записи пользователей
            if not self._cache[user_id]:
                del self._cache[user_id]
        
        # Очистка глобальных кулдаунов
        for user_id in list(self._global_cooldowns.keys()):
            if datetime.utcnow() >= self._global_cooldowns[user_id]:
                del self._global_cooldowns[user_id]
                cleaned += 1
        
        # Очистка старых логов (старше 7 дней)
        cutoff = datetime.utcnow() - timedelta(days=7)
        old_log_count = len(self._usage_log)
        self._usage_log = [log for log in self._usage_log if log['timestamp'] >= cutoff]
        cleaned += old_log_count - len(self._usage_log)
        
        return cleaned
    
    # ============= LEGACY МЕТОДЫ (для обратной совместимости) =============
    
    async def can_post(self, user_id: int) -> Tuple[bool, int]:
        """Legacy метод для обратной совместимости"""
        return await self.check_cooldown(user_id, 'post', Config.COOLDOWN_SECONDS)
    
    async def update_cooldown(self, user_id: int):
        """Legacy метод для обратной совместимости"""
        await self.set_cooldown(user_id, 'post', Config.COOLDOWN_SECONDS)
    
    def simple_can_post(self, user_id: int) -> bool:
        """Простая синхронная проверка (только кэш)"""
        if Config.is_moderator(user_id):
            return True
        
        if user_id in self._cache and 'post' in self._cache[user_id]:
            data = self._cache[user_id]['post']
            return self._is_cooldown_expired(data, data['type'])
        
        return True
    
    def set_last_post_time(self, user_id: int):
        """Legacy метод для установки времени поста"""
        if not Config.is_moderator(user_id):
            expires_at = datetime.utcnow() + timedelta(seconds=Config.COOLDOWN_SECONDS)
            
            if user_id not in self._cache:
                self._cache[user_id] = {}
            
            self._cache[user_id]['post'] = {
                'type': CooldownType.NORMAL,
                'expires_at': expires_at,
                'set_at': datetime.utcnow(),
                'count': 1
            }
    
    def get_remaining_time(self, user_id: int) -> int:
        """Legacy метод получения оставшегося времени"""
        if Config.is_moderator(user_id):
            return 0
        
        if user_id in self._cache and 'post' in self._cache[user_id]:
            return self._calculate_remaining(self._cache[user_id]['post'])
        
        return 0
    
    def clear_cache(self):
        """Очистить весь кэш"""
        self._cache.clear()
        self._global_cooldowns.clear()
        logger.info("Cooldown cache cleared")
    
    def get_cache_size(self) -> int:
        """Получить размер кэша"""
        return len(self._cache)
    
    async def get_all_active_cooldowns(self) -> list:
        """Получить список всех активных кулдаунов"""
        active = []
        
        for user_id, commands in self._cache.items():
            for command, data in commands.items():
                remaining = self._calculate_remaining(data)
                if remaining > 0:
                    active.append({
                        'user_id': user_id,
                        'command': command,
                        'type': data['type'],
                        'remaining_seconds': remaining,
                        'usage_count': data.get('count', 0)
                    })
        
        return active

# Глобальный экземпляр сервиса
cooldown_service = CooldownService()

__all__ = ['CooldownService', 'CooldownType', 'cooldown_service']
