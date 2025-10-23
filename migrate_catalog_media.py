#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция для добавления медиа-полей в каталог
python migrate_catalog_media.py
"""

import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_catalog_media():
    """Добавить колонки для медиа в catalog_posts"""
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
        
        logger.info("🔄 Добавляю колонки для медиа...")
        
        # SQL для добавления колонок
        migration_sql = """
        -- Добавляем колонки если их нет
        ALTER TABLE catalog_posts 
        ADD COLUMN IF NOT EXISTS media_type VARCHAR(50),
        ADD COLUMN IF NOT EXISTS media_file_id VARCHAR(500),
        ADD COLUMN IF NOT EXISTS media_group_id VARCHAR(255),
        ADD COLUMN IF NOT EXISTS media_json JSON DEFAULT '[]';
        """
        
        # Для SQLite
        if 'sqlite' in db_url:
            migration_sql = """
            -- SQLite не поддерживает IF NOT EXISTS для ALTER, проверяем через исключения
            """
            # Для SQLite миграция через try-except
        
        try:
            async with engine.begin() as conn:
                if 'sqlite' not in db_url:
                    await conn.execute(text(migration_sql))
                else:
                    # SQLite - пробуем добавить по одной
                    columns = [
                        "ALTER TABLE catalog_posts ADD COLUMN media_type TEXT",
                        "ALTER TABLE catalog_posts ADD COLUMN media_file_id TEXT",
                        "ALTER TABLE catalog_posts ADD COLUMN media_group_id TEXT",
                        "ALTER TABLE catalog_posts ADD COLUMN media_json TEXT DEFAULT '[]'"
                    ]
                    for col_sql in columns:
                        try:
                            await conn.execute(text(col_sql))
                        except:
                            pass  # Колонка уже существует
            
            logger.info("✅ Колонки медиа добавлены")
        except Exception as e:
            logger.error(f"❌ Ошибка при добавлении колонок: {e}")
            return False
        
        await engine.dispose()
        
        logger.info("\n" + "="*60)
        logger.info("✅ МИГРАЦИЯ МЕДИА ЗАВЕРШЕНА!")
        logger.info("="*60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔄 МИГРАЦИЯ МЕДИА-КОЛОНОК...")
    print("="*60 + "\n")
    
    success = asyncio.run(migrate_catalog_media())
    
    if success:
        print("\n✅ Миграция завершена!")
        print("🚀 Теперь запустите бота: python main.py\n")
        exit(0)
    else:
        print("\n❌ Миграция не удалась!\n")
        exit(1)
