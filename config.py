import os
from dotenv import load_dotenv
from typing import List, Set
import logging

logger = logging.getLogger(__name__)

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", "-1002743668534"))
    MODERATION_GROUP_ID = int(os.getenv("MODERATION_GROUP_ID", "-1002734837434"))
    ADMIN_GROUP_ID = int(os.getenv("XXXADMDBGROUP", "-1003039151203"))
    CHAT_FOR_ACTUAL = int(os.getenv("CHAT_FOR_ACTUAL", "-1002734837434"))
    BUDAPEST_CHAT_ID = int(os.getenv("BUDAPEST_CHAT_ID", "-1002883770818"))
    CATALOG_CHANNEL_ID = int(os.getenv("CATALOG_CHANNEL_ID", "-1002601716810"))
    BUDAPES_CHANNEL_ID = int(os.getenv("BUDAPES_CHANNEL_ID", "-1003114019170"))
    TRADE_CHANNEL_ID = int(os.getenv("TRADE_CHANNEL_ID", "-1003033694255"))
    
    BUDAPEST_CHANNEL = os.getenv("BUDAPEST_CHANNEL", "https://t.me/snghu")
    BUDAPEST_CHAT = os.getenv("BUDAPEST_CHAT", "https://t.me/tgchatxxx")
    CATALOG_CHANNEL = os.getenv("CATALOG_CHANNEL", "https://t.me/catalogtrix")
    TRADE_CHANNEL = os.getenv("TRADE_CHANNEL", "https://t.me/hungarytrade")

    STATS_CHANNELS = {
        'catalog': int(os.getenv("CATALOG_ID", "-1002601716810")),
        'trade': int(os.getenv("TRADE_ID", "-1003033694255")),
        'budapest_main': int(os.getenv("BUDAPEST_MAIN_ID", "-1002743668534")),
        'budapest_chat': int(os.getenv("BUDAPEST_CHAT_STATS_ID", "-1002883770818")),
        'partners': int(os.getenv("PARTNERS_ID", "-1002919380244")),
        'budapest_people': int(os.getenv("BUDAPEST_PEOPLE_ID", "-1003088023508")),
        'budapest_unicorn': int(os.getenv("BUDAPES_CHANNEL_ID", "-1003114019170")),
    }
    
    BUDAPEST_PLAY_ID = int(os.getenv("BUDAPEST_PLAY_ID", "0"))
    
    _raw_db_url = os.getenv("DATABASE_URL")
    
    if not _raw_db_url:
        logger.warning("DATABASE_URL not set! Using SQLite fallback")
        DATABASE_URL = "sqlite:///./trixbot.db"
    else:
        DATABASE_URL = _raw_db_url
        logger.info(f"DATABASE_URL set: {DATABASE_URL[:40]}...")
    
    ADMIN_IDS: Set[int] = set(map(int, filter(None, os.getenv("ADMIN_IDS", "7811593067").split(","))))
    MODERATOR_IDS: Set[int] = set(map(int, filter(None, os.getenv("MODERATOR_IDS", "").split(","))))
    
    COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "3600"))
    
    SCHEDULER_MIN_INTERVAL = int(os.getenv("SCHEDULER_MIN", "120"))
    SCHEDULER_MAX_INTERVAL = int(os.getenv("SCHEDULER_MAX", "160"))
    SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "false").lower() == "true"
    
    STATS_INTERVAL_HOURS = int(os.getenv("STATS_INTERVAL_HOURS", "8"))
    
    DEFAULT_SIGNATURE = os.getenv("DEFAULT_SIGNATURE", "@TrixLiveBot - Ваш гид по Будапешту")
    DEFAULT_PROMO_MESSAGE = os.getenv("DEFAULT_PROMO_MESSAGE", 
                                      "Создать публикацию: https://t.me/TrixLiveBot\n"
                                      "Лучший канал Будапешта: https://t.me/snghu")
    
    MAX_PHOTOS_PIAR = int(os.getenv("MAX_PHOTOS_PIAR", "3"))
    MAX_DISTRICTS_PIAR = int(os.getenv("MAX_DISTRICTS_PIAR", "3"))
    MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "4096"))
    
    BANNED_DOMAINS = [
        "bit.ly", "tinyurl.com", "cutt.ly", "goo.gl",
        "shorturl.at", "ow.ly", "is.gd", "buff.ly"
    ]
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        return user_id in cls.ADMIN_IDS
    
    @classmethod
    def is_moderator(cls, user_id: int) -> bool:
        return user_id in cls.MODERATOR_IDS or cls.is_admin(user_id)
    
    @classmethod
    def get_all_moderators(cls) -> Set[int]:
        return cls.ADMIN_IDS.union(cls.MODERATOR_IDS)
    
    @classmethod
    def validate_config(cls) -> List[str]:
        errors = []
        
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN не задан")
        
        if not cls.DATABASE_URL or cls.DATABASE_URL == "sqlite:///./trixbot.db":
            errors.append("DATABASE_URL не задан или используется SQLite (локальное хранилище)")
        
        if not cls.ADMIN_IDS:
            errors.append("ADMIN_IDS не заданы")
        
        if cls.ADMIN_GROUP_ID == cls.MODERATION_GROUP_ID:
            errors.append("ADMIN_GROUP_ID и MODERATION_GROUP_ID совпадают (рекомендуется разделить)")
        
        return errors
    
    @classmethod
    def get_info(cls) -> str:
        db_type = "PostgreSQL" if "postgresql" in cls.DATABASE_URL else (
            "MySQL" if "mysql" in cls.DATABASE_URL else "SQLite"
        )
        
        return f"""
КОНФИГУРАЦИЯ БОТА

Основное:
Bot Token: {'Установлен' if cls.BOT_TOKEN else 'Не установлен'}
Database: {db_type} ({'Облако' if "postgresql" in cls.DATABASE_URL or "mysql" in cls.DATABASE_URL else 'Локальная'})

Группы и каналы:
Канал публикаций: {cls.TARGET_CHANNEL_ID}
Группа модерации: {cls.MODERATION_GROUP_ID}
Группа администрирования: {cls.ADMIN_GROUP_ID}
Актуальное: {cls.CHAT_FOR_ACTUAL}
Торговый канал: {cls.TRADE_CHANNEL_ID}
Будапешт чат: {cls.BUDAPEST_CHAT_ID}

Права доступа:
Администраторов: {len(cls.ADMIN_IDS)}
Модераторов: {len(cls.MODERATOR_IDS)}

Настройки:
Кулдаун: {cls.COOLDOWN_SECONDS // 3600}ч
Автопостинг: {'Включен' if cls.SCHEDULER_ENABLED else 'Выключен'}
Интервал автопоста: {cls.SCHEDULER_MIN_INTERVAL}-{cls.SCHEDULER_MAX_INTERVAL} мин
Статистика каждые: {cls.STATS_INTERVAL_HOURS}ч

Лимиты:
Макс. фото (пиар): {cls.MAX_PHOTOS_PIAR}
Макс. районов (пиар): {cls.MAX_DISTRICTS_PIAR}
Макс. длина сообщения: {cls.MAX_MESSAGE_LENGTH}
"""

if __name__ != "__main__":
    config_errors = Config.validate_config()
    if config_errors:
        logger.warning("Проблемы конфигурации:")
        for error in config_errors:
            logger.warning(f"  {error}")
    else:
        logger.info("Конфигурация валидна")
