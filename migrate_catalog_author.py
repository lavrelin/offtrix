#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция для добавления полей автора в каталог
python migrate_catalog_author.py
"""

import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_catalog_author():
    """Добавить author_username и author_id в catalog_posts"""
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
        
        logger.info(f"📊 Database URL: {db_url[:60]}...")
        
        engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
        
        logger.info("🔄 Добавляю колонки для автора...")
        
        # SQL для PostgreSQL
        if 'postgresql' in db_url:
            migration_sql = """
            ALTER TABLE catalog_posts 
            ADD COLUMN IF NOT EXISTS author_username VARCHAR(255),
            ADD COLUMN IF NOT EXISTS author_id BIGINT;
            
            CREATE INDEX IF NOT EXISTS idx_catalog_author_id ON catalog_posts(author_id);
            """
        # SQL для SQLite
        else:
            migration_sql = """
            ALTER TABLE catalog_posts 
            ADD COLUMN author_username TEXT;
            
            ALTER TABLE catalog_posts 
            ADD COLUMN author_id INTEGER;
            """
        
        try:
            async with engine.begin() as conn:
                for statement in migration_sql.split(';'):
                    statement = statement.strip()
                    if statement:
                        await conn.execute(text(statement))
            
            logger.info("✅ Колонки автора добавлены")
        except Exception as e:
            if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                logger.info("ℹ️  Колонки автора уже существуют")
            else:
                logger.error(f"❌ Ошибка при добавлении колонок: {e}")
                return False
        
        await engine.dispose()
        
        logger.info("\n" + "="*60)
        logger.info("✅ МИГРАЦИЯ АВТОРА ЗАВЕРШЕНА!")
        logger.info("="*60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔄 МИГРАЦИЯ ПОЛЕЙ АВТОРА...")
    print("="*60 + "\n")
    
    success = asyncio.run(migrate_catalog_author())
    
    if success:
        print("\n✅ Миграция завершена!")
        print("🚀 Перезапустите бота: python main.py\n")
        exit(0)
    else:
        print("\n❌ Миграция не удалась!\n")
        exit(1)
