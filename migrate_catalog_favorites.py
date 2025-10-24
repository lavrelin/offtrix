#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция для добавления функционала избранного в каталог
Использование: python migrate_catalog_favorites.py
"""

import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_favorites():
    """Добавить колонку favorites в catalog_sessions"""
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
        
        engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
        
        logger.info("🔄 Добавляю колонку favorites...")
        
        # SQL для PostgreSQL
        if 'postgresql' in db_url:
            migration_sql = """
            ALTER TABLE catalog_sessions 
            ADD COLUMN IF NOT EXISTS favorites JSON DEFAULT '[]';
            """
        # SQL для SQLite
        else:
            migration_sql = """
            ALTER TABLE catalog_sessions 
            ADD COLUMN favorites TEXT DEFAULT '[]';
            """
        
        try:
            async with engine.begin() as conn:
                await conn.execute(text(migration_sql))
            
            logger.info("✅ Колонка favorites добавлена")
        except Exception as e:
            if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                logger.info("ℹ️  Колонка favorites уже существует")
            else:
                logger.error(f"❌ Ошибка при добавлении колонки: {e}")
                return False
        
        # Проверяем таблицу
        logger.info("✅ Проверяю структуру таблицы...")
        try:
            async with engine.connect() as conn:
                if 'postgresql' in db_url:
                    result = await conn.execute(
                        text("""
                            SELECT column_name, data_type 
                            FROM information_schema.columns 
                            WHERE table_name = 'catalog_sessions'
                        """)
                    )
                else:
                    result = await conn.execute(
                        text("PRAGMA table_info(catalog_sessions)")
                    )
                
                columns = result.fetchall()
                logger.info(f"✅ Колонки таблицы catalog_sessions:")
                for col in columns:
                    logger.info(f"   • {col}")
                
                # Проверяем наличие favorites
                has_favorites = False
                for col in columns:
                    if 'favorites' in str(col).lower():
                        has_favorites = True
                        break
                
                if not has_favorites:
                    logger.error("❌ Колонка favorites не найдена!")
                    return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке таблицы: {e}")
            return False
        
        await engine.dispose()
        
        logger.info("\n" + "="*60)
        logger.info("✅ МИГРАЦИЯ ИЗБРАННОГО ЗАВЕРШЕНА!")
        logger.info("="*60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔄 НАЧИНАЮ МИГРАЦИЮ ИЗБРАННОГО...")
    print("="*60 + "\n")
    
    success = asyncio.run(migrate_favorites())
    
    if success:
        print("\n✅ Миграция завершена!")
        print("🚀 Теперь можете использовать команду /favorites\n")
        exit(0)
    else:
        print("\n❌ Миграция не удалась!")
        print("⚠️  Проверьте логи выше\n")
        exit(1)
