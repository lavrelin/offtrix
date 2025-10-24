#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция для добавления уникальных номеров постам
python migrate_catalog_numbers.py
"""

import asyncio
import logging
import random
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_catalog_numbers():
    """Добавить catalog_number к постам"""
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
        
        logger.info("🔄 Добавляю колонку catalog_number...")
        
        # SQL для PostgreSQL
        if 'postgresql' in db_url:
            migration_sql = """
            ALTER TABLE catalog_posts 
            ADD COLUMN IF NOT EXISTS catalog_number INTEGER UNIQUE;
            
            CREATE INDEX IF NOT EXISTS idx_catalog_number ON catalog_posts(catalog_number);
            """
        # SQL для SQLite
        else:
            migration_sql = """
            ALTER TABLE catalog_posts 
            ADD COLUMN catalog_number INTEGER;
            """
        
        try:
            async with engine.begin() as conn:
                for statement in migration_sql.split(';'):
                    statement = statement.strip()
                    if statement:
                        await conn.execute(text(statement))
            
            logger.info("✅ Колонка catalog_number добавлена")
        except Exception as e:
            if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                logger.info("ℹ️  Колонка catalog_number уже существует")
            else:
                logger.error(f"❌ Ошибка при добавлении колонки: {e}")
                return False
        
        # Присваиваем уникальные номера существующим постам
        logger.info("🔄 Присваиваю уникальные номера существующим постам...")
        
        try:
            async with engine.begin() as conn:
                # Получаем посты без номеров
                result = await conn.execute(
                    text("SELECT id FROM catalog_posts WHERE catalog_number IS NULL")
                )
                posts = result.fetchall()
                
                if posts:
                    used_numbers = set()
                    
                    for post_id, in posts:
                        # Генерируем уникальный номер
                        while True:
                            number = random.randint(1, 9999)
                            if number not in used_numbers:
                                used_numbers.add(number)
                                break
                        
                        # Обновляем пост
                        await conn.execute(
                            text(f"UPDATE catalog_posts SET catalog_number = {number} WHERE id = {post_id}")
                        )
                    
                    logger.info(f"✅ Присвоены номера {len(posts)} постам")
                else:
                    logger.info("ℹ️  Все посты уже имеют номера")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка при присвоении номеров: {e}")
            return False
        
        await engine.dispose()
        
        logger.info("\n" + "="*60)
        logger.info("✅ МИГРАЦИЯ НОМЕРОВ ЗАВЕРШЕНА!")
        logger.info("="*60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔄 МИГРАЦИЯ УНИКАЛЬНЫХ НОМЕРОВ...")
    print("="*60 + "\n")
    
    success = asyncio.run(migrate_catalog_numbers())
    
    if success:
        print("\n✅ Миграция завершена!")
        print("🚀 Перезапустите бота: python main.py\n")
        exit(0)
    else:
        print("\n❌ Миграция не удалась!\n")
        exit(1)
