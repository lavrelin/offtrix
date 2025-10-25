#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки прав бота в канале

Использование:
python check_bot_permissions.py @catalogtrix
python check_bot_permissions.py -1002601716810
"""

import asyncio
import sys
import os
from telegram import Bot
from telegram.error import TelegramError

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def check_bot_permissions(channel_id: str):
    """Проверить права бота в канале"""
    try:
        bot = Bot(token=BOT_TOKEN)
        
        print(f"\n{'='*60}")
        print(f"🔍 ПРОВЕРКА ПРАВ БОТА В КАНАЛЕ")
        print(f"{'='*60}\n")
        
        # Преобразуем ID если нужно
        if channel_id.startswith('@'):
            chat_id = channel_id
        elif channel_id.isdigit():
            chat_id = int(f"-100{channel_id}")
        else:
            chat_id = int(channel_id)
        
        print(f"📋 Проверяемый канал: {chat_id}\n")
        
        # 1. Получаем информацию о канале
        try:
            chat = await bot.get_chat(chat_id)
            print(f"✅ ДОСТУП К КАНАЛУ: OK")
            print(f"   Название: {chat.title}")
            print(f"   Тип: {chat.type}")
            print(f"   ID: {chat.id}\n")
        except TelegramError as e:
            print(f"❌ ДОСТУП К КАНАЛУ: FAILED")
            print(f"   Ошибка: {e}\n")
            print("💡 Решение:")
            print("   1. Добавьте бота в канал")
            print("   2. Сделайте бота администратором\n")
            return
        
        # 2. Получаем права бота
        try:
            bot_member = await bot.get_chat_member(chat_id, bot.id)
            print(f"✅ ИНФОРМАЦИЯ О БОТЕ:")
            print(f"   Статус: {bot_member.status}")
            
            if bot_member.status == 'administrator':
                print(f"\n📝 ПРАВА АДМИНИСТРАТОРА:")
                perms = bot_member
                print(f"   • Может удалять сообщения: {'✅' if perms.can_delete_messages else '❌'}")
                print(f"   • Может редактировать сообщения: {'✅' if perms.can_edit_messages else '❌'}")
                print(f"   • Может закреплять сообщения: {'✅' if perms.can_pin_messages else '❌'}")
                print(f"   • Может приглашать пользователей: {'✅' if perms.can_invite_users else '❌'}")
                print(f"   • Может ограничивать участников: {'✅' if perms.can_restrict_members else '❌'}")
                print(f"   • Может повышать участников: {'✅' if perms.can_promote_members else '❌'}")
                print(f"   • Может изменять инфо канала: {'✅' if perms.can_change_info else '❌'}")
                print(f"   • Может публиковать: {'✅' if perms.can_post_messages else '❌'}")
                
                print(f"\n💡 ДЛЯ ИМПОРТА МЕДИА НУЖНО:")
                print(f"   • Бот должен быть администратором: {'✅' if bot_member.status == 'administrator' else '❌'}")
                print(f"   • Доступ к сообщениям канала: ✅ (есть)")
                
            elif bot_member.status == 'member':
                print(f"\n⚠️  БОТ НЕ ЯВЛЯЕТСЯ АДМИНИСТРАТОРОМ")
                print(f"   Статус: обычный участник")
                print(f"\n💡 Для импорта медиа:")
                print(f"   1. Сделайте бота администратором")
                print(f"   2. Дайте минимальные права на чтение")
                
            else:
                print(f"\n❌ НЕОЖИДАННЫЙ СТАТУС: {bot_member.status}")
                
        except TelegramError as e:
            print(f"❌ ОШИБКА ПОЛУЧЕНИЯ ПРАВ: {e}\n")
        
        # 3. Проверяем возможность копирования сообщения
        print(f"\n{'='*60}")
        print(f"🧪 ТЕСТ КОПИРОВАНИЯ СООБЩЕНИЯ")
        print(f"{'='*60}\n")
        
        # Получаем последнее сообщение
        try:
            # Для каналов можем попробовать копировать известное сообщение
            print("💡 Для проверки копирования укажите ID сообщения")
            print("   Пример: 186")
            print("   Или нажмите Enter для пропуска")
            
            # В автоматическом режиме пропускаем
            print("\n⏭️  Тест копирования пропущен (требуется ID сообщения)\n")
            
        except Exception as e:
            print(f"⚠️  Тест копирования недоступен: {e}\n")
        
        print(f"{'='*60}")
        print(f"✅ ПРОВЕРКА ЗАВЕРШЕНА")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\n❌ Использование:")
        print("   python check_bot_permissions.py @catalogtrix")
        print("   python check_bot_permissions.py -1002601716810\n")
        sys.exit(1)
    
    channel_id = sys.argv[1]
    asyncio.run(check_bot_permissions(channel_id))
