#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ПОЛНАЯ МИГРАЦИЯ БАЗЫ ДАННЫХ - ЕДИНЫЙ ФАЙЛ
Заменяет все migrate_*.py файлы

Использование: python migrate_complete.py
"""

import asyncio
import logging
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_complete():
    """Полная миграция - создание всех таблиц с нуля"""
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
        
        logger.info(f"📊 Database: {db_url[:60]}...")
        
        engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
        
        logger.info("🔄 Проверяю подключение...")
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✅ Подключение OK")
        
        # ============= УДАЛЯЕМ СТАРЫЕ ТАБЛИЦЫ =============
        logger.info("🗑️  Удаляю старые таблицы...")
        
        try:
            async with engine.begin() as conn:
                if 'postgresql' in db_url:
                    await conn.execute(text("""
                        DROP TABLE IF EXISTS catalog_sessions CASCADE;
                        DROP TABLE IF EXISTS catalog_subscriptions CASCADE;
                        DROP TABLE IF EXISTS catalog_reviews CASCADE;
                        DROP TABLE IF EXISTS catalog_posts CASCADE;
                        DROP TABLE IF EXISTS posts CASCADE;
                        DROP TABLE IF EXISTS users CASCADE;
                    """))
                else:
                    for table in ['catalog_sessions', 'catalog_subscriptions', 'catalog_reviews', 
                                  'catalog_posts', 'posts', 'users']:
                        try:
                            await conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                        except:
                            pass
            
            logger.info("✅ Старые таблицы удалены")
        except Exception as e:
            logger.warning(f"⚠️  Ошибка при удалении (продолжаем): {e}")
        
        # ============= СОЗДАЁМ НОВЫЕ ТАБЛИЦЫ =============
        logger.info("🔨 Создаю новые таблицы...")
        
        # Определяем SQL в зависимости от БД
        if 'postgresql' in db_url:
            sql = """
            -- USERS TABLE
            CREATE TABLE users (
                id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                gender VARCHAR(10) DEFAULT 'UNKNOWN',
                referral_code VARCHAR(255) UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- POSTS TABLE
            CREATE TABLE posts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                category VARCHAR(255),
                subcategory VARCHAR(255),
                text TEXT,
                media JSON DEFAULT '[]',
                hashtags JSON DEFAULT '[]',
                media_type VARCHAR(50),
                media_file_id VARCHAR(500),
                media_group_id VARCHAR(255),
                media_json JSON DEFAULT '[]',
                anonymous BOOLEAN DEFAULT FALSE,
                status VARCHAR(20) DEFAULT 'PENDING',
                moderation_message_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_piar BOOLEAN DEFAULT FALSE,
                piar_name VARCHAR(255),
                piar_profession VARCHAR(255),
                piar_districts JSON DEFAULT '[]',
                piar_phone VARCHAR(255),
                piar_instagram VARCHAR(255),
                piar_telegram VARCHAR(255),
                piar_price VARCHAR(255),
                piar_description TEXT
            );

            -- CATALOG POSTS TABLE
            CREATE TABLE catalog_posts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                catalog_link VARCHAR(500) NOT NULL,
                category VARCHAR(100) NOT NULL,
                name VARCHAR(255),
                tags JSON DEFAULT '[]',
                catalog_number INTEGER UNIQUE,
                author_username VARCHAR(255),
                author_id BIGINT,
                media_type VARCHAR(50),
                media_file_id VARCHAR(500),
                media_group_id VARCHAR(255),
                media_json JSON DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                clicks INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                is_priority BOOLEAN DEFAULT FALSE,
                is_ad BOOLEAN DEFAULT FALSE,
                ad_frequency INTEGER DEFAULT 10
            );

            -- CATALOG REVIEWS TABLE
            CREATE TABLE catalog_reviews (
                id SERIAL PRIMARY KEY,
                catalog_post_id INTEGER REFERENCES catalog_posts(id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL,
                username VARCHAR(255),
                review_text TEXT,
                rating INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- CATALOG SUBSCRIPTIONS TABLE
            CREATE TABLE catalog_subscriptions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                subscription_type VARCHAR(50),
                subscription_value VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- CATALOG SESSIONS TABLE
            CREATE TABLE catalog_sessions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL UNIQUE,
                viewed_posts JSON DEFAULT '[]',
                favorites JSON DEFAULT '[]',
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_active BOOLEAN DEFAULT TRUE
            );

            -- INDEXES
            CREATE INDEX idx_posts_user_id ON posts(user_id);
            CREATE INDEX idx_posts_status ON posts(status);
            CREATE INDEX idx_catalog_posts_category ON catalog_posts(category);
            CREATE INDEX idx_catalog_posts_user_id ON catalog_posts(user_id);
            CREATE INDEX idx_catalog_posts_number ON catalog_posts(catalog_number);
            CREATE INDEX idx_catalog_reviews_post_id ON catalog_reviews(catalog_post_id);
            CREATE INDEX idx_catalog_sessions_user_id ON catalog_sessions(user_id);
            """
        else:
            # SQLite
            sql = """
            -- USERS TABLE
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                gender TEXT DEFAULT 'UNKNOWN',
                referral_code TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- POSTS TABLE
            CREATE TABLE posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT,
                subcategory TEXT,
                text TEXT,
                media TEXT DEFAULT '[]',
                hashtags TEXT DEFAULT '[]',
                media_type TEXT,
                media_file_id TEXT,
                media_group_id TEXT,
                media_json TEXT DEFAULT '[]',
                anonymous INTEGER DEFAULT 0,
                status TEXT DEFAULT 'PENDING',
                moderation_message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_piar INTEGER DEFAULT 0,
                piar_name TEXT,
                piar_profession TEXT,
                piar_districts TEXT DEFAULT '[]',
                piar_phone TEXT,
                piar_instagram TEXT,
                piar_telegram TEXT,
                piar_price TEXT,
                piar_description TEXT
            );

            -- CATALOG POSTS TABLE
            CREATE TABLE catalog_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                catalog_link TEXT NOT NULL,
                category TEXT NOT NULL,
                name TEXT,
                tags TEXT DEFAULT '[]',
                catalog_number INTEGER UNIQUE,
                author_username TEXT,
                author_id INTEGER,
                media_type TEXT,
                media_file_id TEXT,
                media_group_id TEXT,
                media_json TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                clicks INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                is_priority INTEGER DEFAULT 0,
                is_ad INTEGER DEFAULT 0,
                ad_frequency INTEGER DEFAULT 10
            );

            -- CATALOG REVIEWS TABLE
            CREATE TABLE catalog_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                catalog_post_id INTEGER REFERENCES catalog_posts(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL,
                username TEXT,
                review_text TEXT,
                rating INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- CATALOG SUBSCRIPTIONS TABLE
            CREATE TABLE catalog_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subscription_type TEXT,
                subscription_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- CATALOG SESSIONS TABLE
            CREATE TABLE catalog_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                viewed_posts TEXT DEFAULT '[]',
                favorites TEXT DEFAULT '[]',
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_active INTEGER DEFAULT 1
            );

            -- INDEXES
            CREATE INDEX idx_posts_user_id ON posts(user_id);
            CREATE INDEX idx_posts_status ON posts(status);
            CREATE INDEX idx_catalog_posts_category ON catalog_posts(category);
            CREATE INDEX idx_catalog_posts_user_id ON catalog_posts(user_id);
            CREATE INDEX idx_catalog_posts_number ON catalog_posts(catalog_number);
            CREATE INDEX idx_catalog_reviews_post_id ON catalog_reviews(catalog_post_id);
            CREATE INDEX idx_catalog_sessions_user_id ON catalog_sessions(user_id);
            """
        
        async with engine.begin() as conn:
            for statement in sql.split(';'):
                statement = statement.strip()
                if statement:
                    try:
                        await conn.execute(text(statement))
                    except Exception as e:
                        logger.error(f"❌ Ошибка SQL: {e}")
                        logger.error(f"   Statement: {statement[:100]}")
                        raise
        
        logger.info("✅ Таблицы созданы")
        
        # ============= ПРОВЕРКА =============
        logger.info("✅ Проверяю таблицы...")
        
        async with engine.connect() as conn:
            if 'postgresql' in db_url:
                result = await conn.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
                )
            else:
                result = await conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                )
            
            tables = [row[0] for row in result.fetchall()]
            logger.info(f"✅ Таблицы: {tables}")
            
            required = {'users', 'posts', 'catalog_posts', 'catalog_reviews', 
                       'catalog_subscriptions', 'catalog_sessions'}
            missing = required - set(tables)
            
            if missing:
                logger.error(f"❌ Отсутствуют таблицы: {missing}")
                return False
        
        await engine.dispose()
        
        logger.info("\n" + "="*60)
        logger.info("✅ МИГРАЦИЯ УСПЕШНА!")
        logger.info("="*60)
        logger.info("\n📋 Создано:")
        logger.info("  ✅ users - пользователи")
        logger.info("  ✅ posts - посты (с media_type!)")
        logger.info("  ✅ catalog_posts - каталог услуг")
        logger.info("  ✅ catalog_reviews - отзывы")
        logger.info("  ✅ catalog_subscriptions - подписки")
        logger.info("  ✅ catalog_sessions - сессии")
        logger.info("\n🚀 Теперь запустите: python main.py\n")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔄 ПОЛНАЯ МИГРАЦИЯ БАЗЫ ДАННЫХ")
    print("="*60 + "\n")
    
    success = asyncio.run(migrate_complete())
    
    if success:
        print("\n✅ Миграция завершена!")
        print("🚀 Запустите бота: python main.py\n")
        exit(0)
    else:
        print("\n❌ Миграция не удалась!\n")
        exit(1)
