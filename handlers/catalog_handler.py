# -*- coding: utf-8 -*-
"""
Handler для каталога услуг - ПОЛНАЯ ВЕРСИЯ С МЕДИА И ИСПРАВЛЕНИЯМИ
Команды: /catalog, /search, /addtocatalog, /review, /catalogpriority, /addcatalogreklama
Версия: 2.0.1 - Исправлены все ошибки
"""
import logging
import re
from typing import Optional, Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from config import Config
from services.catalog_service import catalog_service, CATALOG_CATEGORIES

logger = logging.getLogger(__name__)


# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

async def extract_media_from_link(bot: Bot, telegram_link: str) -> Optional[Dict]:
    """Автоматический импорт медиа из поста в Telegram-канале"""
    try:
        if not telegram_link or 't.me/' not in telegram_link:
            return None
        
        match = re.search(r't\.me/([^/]+)/(\d+)', telegram_link)
        if not match:
            return None
        
        channel_username = match.group(1)
        message_id = int(match.group(2))
        
        if channel_username.startswith('@'):
            channel_username = channel_username[1:]
        
        chat_id = f"@{channel_username}" if not channel_username.startswith('-100') else int(channel_username)
        
        try:
            message = await bot.forward_message(
                chat_id=bot.id,
                from_chat_id=chat_id,
                message_id=message_id
            )
            
            result = None
            if message.photo:
                result = {'type': 'photo', 'file_id': message.photo[-1].file_id, 'media_group_id': message.media_group_id, 'media_json': [message.photo[-1].file_id]}
            elif message.video:
                result = {'type': 'video', 'file_id': message.video.file_id, 'media_group_id': message.media_group_id, 'media_json': [message.video.file_id]}
            elif message.document:
                result = {'type': 'document', 'file_id': message.document.file_id, 'media_group_id': message.media_group_id, 'media_json': [message.document.file_id]}
            elif message.animation:
                result = {'type': 'animation', 'file_id': message.animation.file_id, 'media_group_id': message.media_group_id, 'media_json': [message.animation.file_id]}
            
            try:
                await bot.delete_message(chat_id=bot.id, message_id=message.message_id)
            except:
                pass
            
            if result:
                logger.info(f"✅ Media extracted: {result['type']}")
            return result
        except TelegramError as e:
            logger.error(f"Cannot access message: {e}")
            return None
    except Exception as e:
        logger.error(f"Error extracting media: {e}")
        return None


async def send_catalog_post_with_media(bot: Bot, chat_id: int, post: Dict, index: int, total: int) -> bool:
    """Отправка карточки каталога с медиа"""
    try:
        card_text = f"🆔 **Пост #{index} из {total}**\n\n"
        card_text += f"📂 {post.get('category', 'Не указана')}\n"
        card_text += f"📝 {post.get('name', 'Без названия')}\n\n"
        
        tags = post.get('tags', [])
        if tags and isinstance(tags, list):
            # Форматируем теги (нельзя использовать \w в f-string)
            tags_formatted = []
            for tag in tags[:5]:
                if tag:
                    clean_tag = re.sub(r'[^\w\-]', '', str(tag).replace(' ', '_'))
                    if clean_tag:
                        tags_formatted.append(f"#{clean_tag}")
            
            if tags_formatted:
                card_text += f"{' '.join(tags_formatted)}\n\n"
        
        card_text += f"👁 {post.get('views', 0)} | 🔗 {post.get('clicks', 0)}\n"
        
        keyboard = [
            [InlineKeyboardButton("🔗 Перейти", url=post.get('catalog_link', '#')), InlineKeyboardButton("💬 Отзыв", callback_data=f"catalog:review:{post.get('id')}")],
            [InlineKeyboardButton("🔔 Подписаться", callback_data=f"catalog:subscribe:{post.get('category')}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        media_type = post.get('media_type')
        media_file_id = post.get('media_file_id')
        sent = False
        
        if media_file_id and media_type:
            try:
                if media_type == 'photo':
                    await bot.send_photo(chat_id=chat_id, photo=media_file_id, caption=card_text, reply_markup=reply_markup, parse_mode='Markdown')
                elif media_type == 'video':
                    await bot.send_video(chat_id=chat_id, video=media_file_id, caption=card_text, reply_markup=reply_markup, parse_mode='Markdown')
                elif media_type == 'document':
                    await bot.send_document(chat_id=chat_id, document=media_file_id, caption=card_text, reply_markup=reply_markup, parse_mode='Markdown')
                elif media_type == 'animation':
                    await bot.send_animation(chat_id=chat_id, animation=media_file_id, caption=card_text, reply_markup=reply_markup, parse_mode='Markdown')
                sent = True
            except TelegramError:
                sent = False
        
        if not sent:
            await bot.send_message(chat_id=chat_id, text=card_text, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)
        
        return True
    except Exception as e:
        logger.error(f"Error sending catalog post: {e}")
        return False


async def handle_catalog_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обработка загрузки медиа при добавлении поста"""
    if 'catalog_add' not in context.user_data or context.user_data['catalog_add'].get('step') != 'media':
        return False
    
    data = context.user_data['catalog_add']
    media_type = media_file_id = None
    
    if update.message.photo:
        media_type, media_file_id = 'photo', update.message.photo[-1].file_id
    elif update.message.video:
        media_type, media_file_id = 'video', update.message.video.file_id
    elif update.message.document:
        media_type, media_file_id = 'document', update.message.document.file_id
    elif update.message.animation:
        media_type, media_file_id = 'animation', update.message.animation.file_id
    
    if media_type and media_file_id:
        data.update({'media_type': media_type, 'media_file_id': media_file_id, 'media_group_id': update.message.media_group_id, 'media_json': [media_file_id], 'step': 'tags'})
        await update.message.reply_text(f"✅ Медиа: {media_type}\n\n#️⃣ Теги через запятую (до 10):\nПример: маникюр, гель-лак")
        return True
    return False


# ============= КОМАНДЫ =============

async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр каталога - /catalog"""
    user_id = update.effective_user.id
    count = 5
    posts = await catalog_service.get_random_posts(user_id, count=count)
    
    if not posts:
        keyboard = [[InlineKeyboardButton("🔄 Начать заново", callback_data="catalog:restart")], [InlineKeyboardButton("↩️ Главное меню", callback_data="menu:back")]]
        await update.message.reply_text("📂 Актуальных публикаций больше нет\n\nНажмите 🔄 'Начать заново'", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    for i, post in enumerate(posts, 1):
        await send_catalog_post_with_media(context.bot, update.effective_chat.id, post, i, len(posts))
    
    keyboard = [[InlineKeyboardButton(f"➡️ Следующие {count}", callback_data="catalog:next"), InlineKeyboardButton("⏹️ Закончить", callback_data="catalog:finish")], [InlineKeyboardButton("🕵🏻‍♀️ Поиск", callback_data="catalog:search")]]
    await update.message.reply_text(f"🔃 Показано: {len(posts)}", reply_markup=InlineKeyboardMarkup(keyboard))


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск - /search"""
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"catalog:cat:{cat}")] for cat in CATALOG_CATEGORIES.keys()]
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")])
    await update.message.reply_text("🕵🏼‍♀️ **ПОИСК**\n\nВыберите категорию:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def addtocatalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить в каталог - /addtocatalog"""
    context.user_data['catalog_add'] = {'step': 'link'}
    keyboard = [[InlineKeyboardButton("🚗 Отмена", callback_data="catalog:cancel")]]
    await update.message.reply_text("🆕 **ДОБАВЛЕНИЕ**\n\nШаг 1/5\n\n⛓️ Ссылка на пост:\nПример: https://t.me/channel/123", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отзыв - /review [id]"""
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("🔄 Использование: `/review [номер]`\n\nПример: `/review 123`", parse_mode='Markdown')
        return
    
    post_id = int(context.args[0])
    context.user_data['catalog_review'] = {'post_id': post_id, 'waiting': True}
    keyboard = [[InlineKeyboardButton("⏮️ Отмена", callback_data="catalog:cancel_review")]]
    await update.message.reply_text(f"🖋️ **ОТЗЫВ**\n\nID: {post_id}\n\nВведите отзыв (макс. 1000 символов):", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def catalogpriority_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приоритетные посты - /catalogpriority"""
    if not Config.is_admin(update.effective_user.id):
        return
    context.user_data['catalog_priority'] = {'links': [], 'step': 'collecting'}
    keyboard = [[InlineKeyboardButton("✅ Завершить", callback_data="catalog:priority_finish")]]
    await update.message.reply_text("⭐ **ПРИОРИТЕТНЫЕ**\n\nОтправляйте ссылки (до 10)", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def addcatalogreklama_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить рекламу - /addcatalogreklama"""
    if not Config.is_admin(update.effective_user.id):
        return
    context.user_data['catalog_ad'] = {'step': 'link'}
    keyboard = [[InlineKeyboardButton("🚫 Отмена", callback_data="catalog:cancel_ad")]]
    await update.message.reply_text("📢 **РЕКЛАМА**\n\nШаг 1/2\n\nСсылка на пост:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def catalogviews_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика просмотров - /catalogviews"""
    if not Config.is_admin(update.effective_user.id):
        return
    try:
        stats = await catalog_service.get_views_stats(limit=20)
        if not stats:
            await update.message.reply_text("📊 Статистика пуста")
            return
        text = "📊 **ТОП-20 ПО ПРОСМОТРАМ**\n\n"
        for idx, (post_id, views, name) in enumerate(stats, 1):
            emoji = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else "▪️"
            text += f"{emoji} #{post_id}: {views} 👁 - {name[:30]}...\n"
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Ошибка")


async def catalog_stats_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика пользователей - /catalog_stats_users"""
    if not Config.is_admin(update.effective_user.id):
        return
    try:
        stats = await catalog_service.get_catalog_stats()
        text = f"👥 **СТАТИСТИКА**\n\n📊 Постов: {stats.get('total_posts', 0)}\n📸 С медиа: {stats.get('posts_with_media', 0)} ({stats.get('media_percentage', 0)}%)\n📄 Без медиа: {stats.get('posts_without_media', 0)}\n\n👁 Просмотров: {stats.get('total_views', 0)}\n🔗 Переходов: {stats.get('total_clicks', 0)}\n📈 CTR: {stats.get('ctr', 0)}%\n\n🔥 Сессий: {stats.get('active_sessions', 0)}\n💬 Отзывов: {stats.get('total_reviews', 0)}"
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Ошибка")


async def catalog_stats_categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика категорий - /catalog_stats_categories"""
    if not Config.is_admin(update.effective_user.id):
        return
    try:
        stats = await catalog_service.get_category_stats()
        if not stats:
            await update.message.reply_text("📁 Статистика пуста")
            return
        text = "📁 **ПО КАТЕГОРИЯМ**\n\n"
        for category, count in stats.items():
            text += f"▪️ {category}: {count}\n"
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Ошибка")


async def catalog_stats_popular_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ТОП-10 - /catalog_stats_popular"""
    if not Config.is_admin(update.effective_user.id):
        return
    try:
        stats = await catalog_service.get_views_stats(limit=10)
        if not stats:
            await update.message.reply_text("🏆 ТОП пуст")
            return
        text = "🏆 **ТОП-10**\n\n"
        for idx, (post_id, views, name) in enumerate(stats, 1):
            emoji = ["🥇", "🥈", "🥉"][idx-1] if idx <= 3 else f"{idx}."
            text += f"{emoji} {name[:30]}... - {views} 👁\n"
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Ошибка")


# ============= CALLBACKS =============

async def handle_catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback"""
    query = update.callback_query
    await query.answer()
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    user_id = update.effective_user.id
    
    if action == "next":
        posts = await catalog_service.get_random_posts(user_id, count=5)
        if not posts:
            await query.edit_message_text("🎦 Каталог просмотрен\n\n/catalog - обновить")
            return
        await query.message.delete()
        for i, post in enumerate(posts, 1):
            await send_catalog_post_with_media(context.bot, query.message.chat_id, post, i, len(posts))
        keyboard = [[InlineKeyboardButton("➡️ Следующие 5", callback_data="catalog:next"), InlineKeyboardButton("⏹️ Закончить", callback_data="catalog:finish")]]
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"🔃 Показано: {len(posts)}", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif action == "finish":
        await query.edit_message_text("🔭 Просмотр завершен!\n\n/start - меню")
    
    elif action == "restart":
        await catalog_service.reset_session(user_id)
        await query.edit_message_text("🔄 Сессия сброшена\n\n/catalog")
    
    elif action == "search":
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"catalog:cat:{cat}")] for cat in CATALOG_CATEGORIES.keys()]
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="catalog:back_main")])
        await query.edit_message_text("🔦 **ПОИСК**\n\nКатегория:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif action == "cat":
        category = ":".join(data[2:])
        subcats = CATALOG_CATEGORIES.get(category, [])
        keyboard = [[InlineKeyboardButton(s, callback_data=f"catalog:searchcat:{category}:{s}")] for s in subcats]
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="catalog:search")])
        await query.edit_message_text(f"📂 **{category}**\n\nПодкатегория:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif action == "searchcat":
        category = data[2] if len(data) > 2 else None
        subcategory = data[3] if len(data) > 3 else None
        posts = await catalog_service.search_posts(query=subcategory or category, limit=10)
        if not posts:
            await query.edit_message_text(f"🫙 '{subcategory or category}' пуста")
            return
        await query.message.delete()
        for i, post in enumerate(posts, 1):
            await send_catalog_post_with_media(context.bot, query.message.chat_id, post, i, len(posts))
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"💿 Найдено: {len(posts)}")
    
    elif action == "addcat":
        if 'catalog_add' not in context.user_data:
            await query.answer("Ошибка", show_alert=True)
            return
        category = ":".join(data[2:])
        context.user_data['catalog_add']['category'] = category
        context.user_data['catalog_add']['step'] = 'name'
        await query.edit_message_text(f"✅ Категория: {category}\n\n🚶‍♀️ Шаг 3/5\n\n📝 Название:")
    
    elif action == "skip_media":
        if 'catalog_add' not in context.user_data:
            await query.answer("Ошибка", show_alert=True)
            return
        context.user_data['catalog_add']['step'] = 'tags'
        await query.edit_message_text("⏭️ Медиа пропущено\n\n#️⃣ Теги через запятую:")
    
    elif action == "subscribe":
        category = ":".join(data[2:])
        success = await catalog_service.subscribe_to_category(user_id, category)
        await query.answer("✅ Подписались!" if success else "❌ Ошибка", show_alert=True)
    
    elif action == "unsubscribe":
        category = ":".join(data[2:])
        success = await catalog_service.unsubscribe_from_category(user_id, category)
        await query.answer("✅ Отписались" if success else "❌ Ошибка", show_alert=True)
    
    elif action == "click":
        post_id = int(data[2]) if len(data) > 2 else None
        if post_id:
            await catalog_service.increment_clicks(post_id)
    
    elif action == "review":
        post_id = int(data[2]) if len(data) > 2 else None
        if post_id:
            context.user_data['catalog_review'] = {'post_id': post_id, 'waiting': True}
            keyboard = [[InlineKeyboardButton("⏮️ Отмена", callback_data="catalog:cancel_review")]]
            await query.message.reply_text(f"🖋️ **ОТЗЫВ**\n\nID: {post_id}\n\nВведите отзыв:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif action == "cancel":
        context.user_data.pop('catalog_add', None)
        await query.edit_message_text("🙅🏻 Отменено")
    
    elif action == "cancel_review":
        context.user_data.pop('catalog_review', None)
        await query.edit_message_text("🚮 Отменено")
    
    elif action == "cancel_ad":
        context.user_data.pop('catalog_ad', None)
        await query.edit_message_text("🕳️ Отменено")
    
    elif action == "priority_finish":
        links = context.user_data.get('catalog_priority', {}).get('links', [])
        if not links:
            await query.edit_message_text("🖇️ Ссылки не добавлены")
            return
        count = await catalog_service.set_priority_posts(links)
        context.user_data.pop('catalog_priority', None)
        await query.edit_message_text(f"✅ Приоритет установлен\n\nДобавлено: {count}/{len(links)}")


# ============= TEXT HANDLER =============

async def handle_catalog_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текста"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Отзывы
    if 'catalog_review' in context.user_data and context.user_data['catalog_review'].get('waiting'):
        post_id = context.user_data['catalog_review'].get('post_id')
        success = await catalog_service.add_review(post_id=post_id, user_id=user_id, review_text=text[:1000], rating=5, username=update.effective_user.username)
        await update.message.reply_text("✅ Отзыв добавлен! 💚" if success else "❌ Ошибка")
        context.user_data.pop('catalog_review', None)
        return
    
    # Добавление поста
    if 'catalog_add' in context.user_data:
        data = context.user_data['catalog_add']
        step = data.get('step')
        
        if step == 'link':
            if not text.startswith('https://t.me/'):
                await update.message.reply_text("❌ Ссылка должна начинаться с https://t.me/")
                return
            data['link'] = text
            data['step'] = 'category'
            keyboard = [[InlineKeyboardButton(cat, callback_data=f"catalog:addcat:{cat}")] for cat in CATALOG_CATEGORIES.keys()]
            await update.message.reply_text("🚶🏻‍➡️ Шаг 2/5\n\n📂 Категория:", reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif step == 'name':
            data['name'] = text[:255]
            data['step'] = 'media'
            keyboard = [[InlineKeyboardButton("⏭️ Пропустить", callback_data="catalog:skip_media")]]
            media = await extract_media_from_link(context.bot, data['link'])
            if media:
                data.update({'media_type': media['type'], 'media_file_id': media['file_id'], 'media_group_id': media.get('media_group_id'), 'media_json': media.get('media_json', []), 'step': 'tags'})
                await update.message.reply_text(f"✅ Медиа получено: {media['type']}\n\n#️⃣ Теги через запятую:")
            else:
                await update.message.reply_text("⚠️ Не удалось получить медиа\n\n📸 Отправьте медиа или пропустите →", reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif step == 'tags':
            tags = [t.strip() for t in text.split(',') if t.strip()][:10]
            data['tags'] = tags
            post_id = await catalog_service.add_post(
                user_id=user_id,
                catalog_link=data['link'],
                category=data.get('category', 'Без категории'),
                name=data.get('name', 'Без названия'),
                tags=tags,
                media_type=data.get('media_type'),
                media_file_id=data.get('media_file_id'),
                media_group_id=data.get('media_group_id'),
                media_json=data.get('media_json', [])
            )
            
            if post_id:
                subscribers = await catalog_service.get_category_subscribers(data.get('category'))
                for sub_id in subscribers:
                    try:
                        await context.bot.send_message(chat_id=sub_id, text=f"🔔 Новый пост в '{data.get('category')}'!\n\n{data.get('link')}")
                    except:
                        pass
                await update.message.reply_text(f"✅ Пост добавлен!\n\nID: {post_id}\nУведомлено: {len(subscribers)}")
            else:
                await update.message.reply_text("❌ Ошибка")
            
            context.user_data.pop('catalog_add', None)
    
    # Приоритет
    elif 'catalog_priority' in context.user_data:
        if text.startswith('https://t.me/'):
            context.user_data['catalog_priority']['links'].append(text)
            await update.message.reply_text(f"✅ Добавлено ({len(context.user_data['catalog_priority']['links'])}/10)")
    
    # Реклама
    elif 'catalog_ad' in context.user_data:
        ad_data = context.user_data['catalog_ad']
        if ad_data.get('step') == 'link':
            if not text.startswith('https://t.me/'):
                await update.message.reply_text("❌ Ссылка должна начинаться с https://t.me/")
                return
            ad_data['link'] = text
            ad_data['step'] = 'description'
            await update.message.reply_text("📢 Шаг 2/2\n\nОписание:")
        elif ad_data.get('step') == 'description':
            post_id = await catalog_service.add_ad_post(catalog_link=ad_data['link'], description=text[:500])
            await update.message.reply_text(f"✅ Реклама добавлена!\n\nID: {post_id}" if post_id else "❌ Ошибка")
            context.user_data.pop('catalog_ad', None)


__all__ = ['catalog_command', 'search_command', 'addtocatalog_command', 'review_command', 'catalogpriority_command', 'addcatalogreklama_command', 'catalogviews_command', 'catalog_stats_users_command', 'catalog_stats_categories_command', 'catalog_stats_popular_command', 'handle_catalog_callback', 'handle_catalog_text', 'handle_catalog_media']
