#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция базы данных для каталога услуг
Запустите: python migrate_catalog.py
"""

import asyncio
import logging
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_catalog():
    """Создать таблицы каталога"""
    try:
        db_url = Config.DATABASE_URL
        
        if not db_url:
            logger.error("❌ DATABASE_URL not set!")
            return False
        
        # Конвертируем URL
        if db_url.startswith('postgresql://'):
            db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
        elif db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql+asyncpg://', 1)
        elif db_url.startswith('sqlite:///'):
            db_url = db_url.replace('sqlite:///', 'sqlite+aiosqlite:///', 1)
        
        logger.info(f"📊 Database URL: {db_url[:60]}...")
        
        # Создаем engine
        engine = create_async_engine(
            db_url,
            echo=False,
            pool_pre_ping=True
        )
        
        logger.info("🔄 Создаю таблицы каталога...")
        
        # SQL для создания таблиц
        catalog_tables_sql = """
        -- Таблица постов каталога
        CREATE TABLE IF NOT EXISTS catalog_posts (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            catalog_link VARCHAR(500) NOT NULL,
            category VARCHAR(100) NOT NULL,
            name VARCHAR(255),
            tags JSON DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            clicks INTEGER DEFAULT 0,
            views INTEGER DEFAULT 0,
            is_priority BOOLEAN DEFAULT FALSE,
            is_ad BOOLEAN DEFAULT FALSE,
            ad_frequency INTEGER DEFAULT 10
        );

        -- Таблица отзывов
        CREATE TABLE IF NOT EXISTS catalog_reviews (
            id SERIAL PRIMARY KEY,
            catalog_post_id INTEGER REFERENCES catalog_posts(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL,
            username VARCHAR(255),
            review_text TEXT,
            rating INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Таблица подписок
        CREATE TABLE IF NOT EXISTS catalog_subscriptions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            subscription_type VARCHAR(50),
            subscription_value VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Таблица сессий
        CREATE TABLE IF NOT EXISTS catalog_sessions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL UNIQUE,
            viewed_posts JSON DEFAULT '[]',
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            session_active BOOLEAN DEFAULT TRUE
        );

        -- Индексы
        CREATE INDEX IF NOT EXISTS idx_catalog_posts_category ON catalog_posts(category);
        CREATE INDEX IF NOT EXISTS idx_catalog_posts_user_id ON catalog_posts(user_id);
        CREATE INDEX IF NOT EXISTS idx_catalog_posts_is_priority ON catalog_posts(is_priority);
        CREATE INDEX IF NOT EXISTS idx_catalog_posts_is_ad ON catalog_posts(is_ad);
        CREATE INDEX IF NOT EXISTS idx_catalog_reviews_post_id ON catalog_reviews(catalog_post_id);
        CREATE INDEX IF NOT EXISTS idx_catalog_sessions_user_id ON catalog_sessions(user_id);
        """
        
        # Для SQLite используем другой синтаксис
        if 'sqlite' in db_url:
            catalog_tables_sql = catalog_tables_sql.replace('SERIAL', 'INTEGER')
            catalog_tables_sql = catalog_tables_sql.replace('JSON', 'TEXT')
            catalog_tables_sql = catalog_tables_sql.replace('BIGINT', 'INTEGER')
        
        try:
            async with engine.begin() as conn:
                # Разделяем на отдельные команды
                for statement in catalog_tables_sql.split(';'):
                    statement = statement.strip()
                    if statement:
                        await conn.execute(text(statement))
            
            logger.info("✅ Таблицы каталога созданы")
        except Exception as e:
            logger.error(f"❌ Ошибка при создании таблиц: {e}")
            return False
        
        # Проверяем таблицы
        logger.info("✅ Проверяю таблицы...")
        try:
            async with engine.connect() as conn:
                if 'postgresql' in db_url:
                    result = await conn.execute(
                        text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'catalog_%'")
                    )
                else:
                    result = await conn.execute(
                        text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'catalog_%'")
                    )
                
                tables = [row[0] for row in result.fetchall()]
                logger.info(f"✅ Таблицы каталога: {tables}")
                
                required_tables = {'catalog_posts', 'catalog_reviews', 'catalog_subscriptions', 'catalog_sessions'}
                missing_tables = required_tables - set(tables)
                
                if missing_tables:
                    logger.error(f"❌ Отсутствуют таблицы: {missing_tables}")
                    return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке таблиц: {e}")
            return False
        
        await engine.dispose()
        
        logger.info("\n" + "="*60)
        logger.info("✅ МИГРАЦИЯ КАТАЛОГА ЗАВЕРШЕНА!")
        logger.info("="*60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔄 НАЧИНАЮ МИГРАЦИЮ КАТАЛОГА...")
    print("="*60 + "\n")
    
    success = asyncio.run(migrate_catalog())
    
    if success:
        print("\n✅ Миграция каталога завершена!")
        print("🚀 Теперь запустите бота: python main.py\n")
        exit(0)
    else:
        print("\n❌ Миграция не удалась!")
        print("⚠️  Проверьте логи выше\n")
        exit(1)
