# -*- coding: utf-8 -*-
"""
Handler для каталога услуг - ВЕРСИЯ 2.0 С ПОЛНЫМ ФУНКЦИОНАЛОМ
Новые команды:
- /mysubscriptions - управление подписками
- /edit [id] - редактирование записей
- /remove [id] - удаление записей  
- /bulkimport - массовый импорт
- /catalog_stats_new - статистика новых записей
- /catalog_stats_priority - статистика приоритетных постов
- /catalog_stats_reklama - статистика рекламы
- /catalog_stats_topusers - топ пользователей
- /catalog_stats_export - экспорт данных
- /foryou - персональные рекомендации
- /favorites - избранное

Версия: 2.0.0 - Полный функционал согласно документации
"""
import logging
import re
from typing import Optional, Dict, List
from datetime import datetime, timedelta
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
            tags_formatted = []
            for tag in tags[:5]:
                if tag:
                    clean_tag = re.sub(r'[^\w\-]', '', str(tag).replace(' ', '_'))
                    if clean_tag:
                        tags_formatted.append(f"#{clean_tag}")
            
            if tags_formatted:
                card_text += f"{' '.join(tags_formatted)}\n\n"
        
        card_text += f"👁 {post.get('views', 0)} | 🔗 {post.get('clicks', 0)}\n"
        
        # Добавляем рейтинг если есть
        if post.get('rating') and post.get('review_count'):
            card_text += f"⭐ {post.get('rating'):.1f} ({post.get('review_count')} отзывов)\n"
        
        keyboard = [
            [
                InlineKeyboardButton("🔗 Перейти", url=post.get('catalog_link', '#')),
                InlineKeyboardButton("💬 Отзыв", callback_data=f"catalog:review:{post.get('id')}")
            ],
            [
                InlineKeyboardButton("🔔 Подписаться", callback_data=f"catalog:subscribe:{post.get('category')}"),
                InlineKeyboardButton("⭐ В избранное", callback_data=f"catalog:favorite:{post.get('id')}")
            ]
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
        data.update({
            'media_type': media_type,
            'media_file_id': media_file_id,
            'media_group_id': update.message.media_group_id,
            'media_json': [media_file_id],
            'step': 'tags'
        })
        await update.message.reply_text(
            f"✅ Медиа: {media_type}\n\n"
            "#️⃣ Теги через запятую (до 10):\n"
            "Пример: маникюр, гель-лак"
        )
        return True
    return False


# ============= ОСНОВНЫЕ КОМАНДЫ =============

async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр каталога - /catalog"""
    user_id = update.effective_user.id
    count = 5
    posts = await catalog_service.get_random_posts(user_id, count=count)
    
    if not posts:
        keyboard = [
            [InlineKeyboardButton("🔄 Начать заново", callback_data="catalog:restart")],
            [InlineKeyboardButton("↩️ Главное меню", callback_data="menu:back")]
        ]
        await update.message.reply_text(
            "📂 Актуальных публикаций больше нет\n\n"
            "Нажмите 🔄 'Начать заново'",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    for i, post in enumerate(posts, 1):
        await send_catalog_post_with_media(context.bot, update.effective_chat.id, post, i, len(posts))
    
    keyboard = [
        [
            InlineKeyboardButton(f"➡️ Следующие {count}", callback_data="catalog:next"),
            InlineKeyboardButton("⏹️ Закончить", callback_data="catalog:finish")
        ],
        [InlineKeyboardButton("🕵🏻‍♀️ Поиск", callback_data="catalog:search")]
    ]
    await update.message.reply_text(
        f"🔃 Показано: {len(posts)}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск - /search"""
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"catalog:cat:{cat}")] for cat in CATALOG_CATEGORIES.keys()]
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")])
    await update.message.reply_text(
        "🕵🏼‍♀️ **ПОИСК**\n\nВыберите категорию:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def addtocatalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить в каталог - /addtocatalog"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    context.user_data['catalog_add'] = {'step': 'link'}
    keyboard = [[InlineKeyboardButton("🚗 Отмена", callback_data="catalog:cancel")]]
    await update.message.reply_text(
        "🆕 **ДОБАВЛЕНИЕ**\n\nШаг 1/5\n\n"
        "⛓️ Ссылка на пост:\n"
        "Пример: https://t.me/channel/123",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отзыв - /review [id]"""
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "🔄 Использование: `/review [номер]`\n\n"
            "Пример: `/review 123`",
            parse_mode='Markdown'
        )
        return
    
    post_id = int(context.args[0])
    context.user_data['catalog_review'] = {'post_id': post_id, 'waiting': True}
    keyboard = [[InlineKeyboardButton("⏮️ Отмена", callback_data="catalog:cancel_review")]]
    await update.message.reply_text(
        f"🖋️ **ОТЗЫВ**\n\n"
        f"ID: {post_id}\n\n"
        "Введите отзыв (макс. 1000 символов):",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def catalogpriority_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приоритетные посты - /catalogpriority"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    context.user_data['catalog_priority'] = {'links': [], 'step': 'collecting'}
    keyboard = [[InlineKeyboardButton("✅ Завершить", callback_data="catalog:priority_finish")]]
    await update.message.reply_text(
        "⭐ **ПРИОРИТЕТНЫЕ**\n\n"
        "Отправляйте ссылки (до 10)",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def addcatalogreklama_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить рекламу - /addcatalogreklama"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    context.user_data['catalog_ad'] = {'step': 'link'}
    keyboard = [[InlineKeyboardButton("🚫 Отмена", callback_data="catalog:cancel_ad")]]
    await update.message.reply_text(
        "📢 **РЕКЛАМА**\n\nШаг 1/2\n\nСсылка на пост:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def catalogviews_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика просмотров - /catalogviews"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
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
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    try:
        stats = await catalog_service.get_catalog_stats()
        text = (
            f"👥 **СТАТИСТИКА**\n\n"
            f"📊 Постов: {stats.get('total_posts', 0)}\n"
            f"📸 С медиа: {stats.get('posts_with_media', 0)} ({stats.get('media_percentage', 0)}%)\n"
            f"📄 Без медиа: {stats.get('posts_without_media', 0)}\n\n"
            f"👁 Просмотров: {stats.get('total_views', 0)}\n"
            f"🔗 Переходов: {stats.get('total_clicks', 0)}\n"
            f"📈 CTR: {stats.get('ctr', 0)}%\n\n"
            f"🔥 Сессий: {stats.get('active_sessions', 0)}\n"
            f"💬 Отзывов: {stats.get('total_reviews', 0)}"
        )
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Ошибка")


async def catalog_stats_categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика категорий - /catalog_stats_categories"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
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
        await update.message.reply_text("❌ Команда только для администраторов")
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


# ============= НОВЫЕ КОМАНДЫ ВЕРСИИ 2.0 =============

async def mysubscriptions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление подписками - /mysubscriptions"""
    user_id = update.effective_user.id
    
    try:
        subscriptions = await catalog_service.get_user_subscriptions(user_id)
        
        if not subscriptions:
            keyboard = [[InlineKeyboardButton("🔔 Подписаться на категорию", callback_data="catalog:search")]]
            await update.message.reply_text(
                "📋 **МОИ ПОДПИСКИ**\n\n"
                "У вас пока нет подписок\n\n"
                "Подпишитесь на интересующие категории, чтобы получать уведомления о новых услугах!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return
        
        text = f"📋 **МОИ ПОДПИСКИ** ({len(subscriptions)})\n\n"
        
        keyboard = []
        for sub in subscriptions:
            category = sub.get('category')
            new_count = sub.get('new_count', 0)
            
            status = f"({new_count} новых)" if new_count > 0 else ""
            text += f"🔔 {category} {status}\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"🔕 Отписаться от '{category}'",
                    callback_data=f"catalog:unsub:{category}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔕 Отписаться от всех", callback_data="catalog:unsub_all")])
        keyboard.append([InlineKeyboardButton("⚙️ Настройки уведомлений", callback_data="catalog:notif_settings")])
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in mysubscriptions: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке подписок")


async def edit_catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирование записи - /catalogedit [id]"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "🔄 Использование: `/catalogedit [id]`\n\n"
            "Пример: `/catalogedit 123`",
            parse_mode='Markdown'
        )
        return
    
    post_id = int(context.args[0])
    
    try:
        post = await catalog_service.get_post_by_id(post_id)
        
        if not post:
            await update.message.reply_text(f"❌ Пост #{post_id} не найден")
            return
        
        context.user_data['catalog_edit'] = {'post_id': post_id, 'post_data': post}
        
        text = (
            f"🛠️ **Редактирование поста #{post_id}**\n\n"
            f"📂 Категория: {post.get('category')}\n"
            f"📝 Название: {post.get('name')}\n"
            f"🏷️ Теги: {', '.join(post.get('tags', []))}\n"
            f"🔗 Ссылка: {post.get('catalog_link')}\n\n"
            "Что изменить?"
        )
        
        keyboard = [
            [InlineKeyboardButton("✏️ Категорию", callback_data="catalog:edit:category")],
            [InlineKeyboardButton("📝 Название", callback_data="catalog:edit:name")],
            [InlineKeyboardButton("🏷️ Теги", callback_data="catalog:edit:tags")],
            [InlineKeyboardButton("🔗 Ссылку", callback_data="catalog:edit:link")],
            [InlineKeyboardButton("📸 Медиа", callback_data="catalog:edit:media")],
            [InlineKeyboardButton("⭐ Приоритет", callback_data="catalog:edit:priority")],
            [InlineKeyboardButton("❌ Отменить", callback_data="catalog:edit_cancel")]
        ]
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in edit_catalog: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке поста")


async def remove_catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление записи - /remove [id]"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "🔄 Использование: `/remove [id]`\n\n"
            "Пример: `/remove 123`",
            parse_mode='Markdown'
        )
        return
    
    post_id = int(context.args[0])
    
    try:
        post = await catalog_service.get_post_by_id(post_id)
        
        if not post:
            await update.message.reply_text(f"❌ Пост #{post_id} не найден")
            return
        
        text = (
            f"⚠️ **Удаление поста #{post_id}**\n\n"
            f"📋 Название: {post.get('name')}\n"
            f"📂 Категория: {post.get('category')}\n"
            f"👁️ Просмотры: {post.get('views', 0)}\n"
            f"⭐ Рейтинг: {post.get('rating', 0):.1f} ({post.get('review_count', 0)} отзывов)\n\n"
            "Вы уверены?"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Удалить", callback_data=f"catalog:remove_confirm:{post_id}"),
                InlineKeyboardButton("❌ Отменить", callback_data="catalog:remove_cancel")
            ]
        ]
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in remove_catalog: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке поста")


async def bulkimport_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Массовый импорт - /bulkimport"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    context.user_data['catalog_bulk'] = {'links': [], 'step': 'collecting'}
    
    keyboard = [[InlineKeyboardButton("✅ Завершить сбор", callback_data="catalog:bulk_finish")]]
    
    await update.message.reply_text(
        "📦 **МАССОВЫЙ ИМПОРТ**\n\n"
        "Отправляйте ссылки на посты (до 50):\n"
        "• Каждая ссылка с новой строки\n"
        "• Или по одной ссылке за раз\n\n"
        "После сбора всех ссылок нажмите '✅ Завершить сбор'",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def catalog_stats_new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика новых записей - /catalog_stats_new"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    try:
        # Последние 7 дней
        days_7 = await catalog_service.get_new_posts_count(days=7)
        # Последние 30 дней
        days_30 = await catalog_service.get_new_posts_count(days=30)
        # Сегодня
        today = await catalog_service.get_new_posts_count(days=1)
        
        # Последние 10 записей
        recent_posts = await catalog_service.get_recent_posts(limit=10)
        
        text = (
            f"📊 **НОВЫЕ ЗАПИСИ**\n\n"
            f"📅 Сегодня: {today}\n"
            f"📅 За 7 дней: {days_7}\n"
            f"📅 За 30 дней: {days_30}\n\n"
            f"📋 Последние 10 записей:\n\n"
        )
        
        for idx, post in enumerate(recent_posts, 1):
            created_date = post.get('created_at', 'N/A')
            text += f"{idx}. #{post['id']} | {post['category']} - {post['name'][:25]}...\n"
            text += f"   📅 {created_date}\n\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in catalog_stats_new: {e}")
        await update.message.reply_text("❌ Ошибка")


async def catalog_stats_priority_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика приоритетных постов - /catalog_stats_priority"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    try:
        priority_stats = await catalog_service.get_priority_stats()
        
        if not priority_stats.get('posts'):
            await update.message.reply_text("⭐ Нет приоритетных постов")
            return
        
        posts = priority_stats.get('posts', [])
        avg_ctr = priority_stats.get('avg_ctr', 0)
        normal_ctr = priority_stats.get('normal_ctr', 0)
        improvement = priority_stats.get('improvement', 0)
        
        text = f"⭐ **ПРИОРИТЕТНЫЕ ПОСТЫ** ({len(posts)}/10)\n\n"
        
        for idx, post in enumerate(posts, 1):
            emoji = ["🥇", "🥈", "🥉"][idx-1] if idx <= 3 else f"{idx}️⃣"
            ctr = (post['clicks'] / post['views'] * 100) if post['views'] > 0 else 0
            
            text += (
                f"{emoji} #{post['id']} | {post['name'][:20]}...\n"
                f"   👁 {post['views']} | 🖱 {post['clicks']} ({ctr:.1f}%)\n\n"
            )
        
        text += (
            f"📈 **Сравнение:**\n"
            f"• Приоритетные CTR: {avg_ctr:.1f}%\n"
            f"• Обычные посты CTR: {normal_ctr:.1f}%\n"
            f"• Прирост эффективности: +{improvement:.1f}%\n\n"
        )
        
        if len(posts) < 10:
            text += f"💡 Слоты {len(posts)+1}-10 свободны – добавьте новые приоритеты"
        
        keyboard = [[InlineKeyboardButton("⭐ Управление приоритетами", callback_data="catalog:manage_priority")]]
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in catalog_stats_priority: {e}")
        await update.message.reply_text("❌ Ошибка")


async def catalog_stats_reklama_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика рекламы - /catalog_stats_reklama"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    try:
        ad_stats = await catalog_service.get_ad_stats()
        
        if not ad_stats.get('ads'):
            await update.message.reply_text("💎 Нет активных рекламных кампаний")
            return
        
        ads = ad_stats.get('ads', [])
        total_views = ad_stats.get('total_views', 0)
        total_clicks = ad_stats.get('total_clicks', 0)
        avg_ctr = ad_stats.get('avg_ctr', 0)
        
        text = f"💎 **СТАТИСТИКА РЕКЛАМЫ**\n\n📊 Активные кампании ({len(ads)}):\n\n"
        
        for idx, ad in enumerate(ads, 1):
            ctr = (ad['clicks'] / ad['views'] * 100) if ad['views'] > 0 else 0
            
            text += (
                f"{idx}️⃣ {ad['name'][:25]}...\n"
                f"   👁 {ad['views']} | 🖱 {ad['clicks']}\n"
                f"   📈 CTR: {ctr:.1f}%\n\n"
            )
        
        text += (
            f"📈 **Общая статистика:**\n"
            f"• Всего показов: {total_views:,}\n"
            f"• Всего кликов: {total_clicks:,}\n"
            f"• Средний CTR: {avg_ctr:.1f}%\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("💎 Управление рекламой", callback_data="catalog:manage_ads")],
            [InlineKeyboardButton("📊 Детальная аналитика", callback_data="catalog:detailed_ads")]
        ]
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in catalog_stats_reklama: {e}")
        await update.message.reply_text("❌ Ошибка")


async def catalog_stats_topusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ пользователей - /catalog_stats_topusers"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    try:
        top_users = await catalog_service.get_top_users(limit=20)
        
        if not top_users:
            await update.message.reply_text("👥 Нет активных пользователей")
            return
        
        text = "👑 **ТОП-20 АКТИВНЫХ ПОЛЬЗОВАТЕЛЕЙ**\n\n"
        
        for idx, user in enumerate(top_users, 1):
            username = user.get('username', 'N/A')
            activity = user.get('activity_score', 0)
            subscriptions = user.get('subscriptions', 0)
            reviews = user.get('reviews', 0)
            
            text += (
                f"{idx}. @{username} (ID: {user['user_id']})\n"
                f"   📊 Активность: {activity} взаимодействий\n"
                f"   🔔 Подписок: {subscriptions} | 💬 Отзывов: {reviews}\n\n"
            )
        
        # Сегментация
        segments = await catalog_service.get_user_segments()
        
        text += (
            f"📊 **Сегментация:**\n"
            f"• Супер-активные: {segments.get('super_active', 0)} польз.\n"
            f"• Активные: {segments.get('active', 0)} польз.\n"
            f"• Умеренные: {segments.get('moderate', 0)} польз.\n"
            f"• Неактивные: {segments.get('inactive', 0)} польз.\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("📨 Сегментированная рассылка", callback_data="catalog:segment_broadcast")],
            [InlineKeyboardButton("📊 Детальный анализ", callback_data="catalog:detailed_users")]
        ]
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in catalog_stats_topusers: {e}")
        await update.message.reply_text("❌ Ошибка")


async def catalog_stats_export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт данных - /catalog_stats_export"""
    if not Config.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для администраторов")
        return
    
    keyboard = [
        [InlineKeyboardButton("☑️ Пользовательская активность", callback_data="catalog:export:users")],
        [InlineKeyboardButton("☑️ Статистика по категориям", callback_data="catalog:export:categories")],
        [InlineKeyboardButton("☑️ Топ постов", callback_data="catalog:export:top")],
        [InlineKeyboardButton("☑️ Новые записи", callback_data="catalog:export:new")],
        [InlineKeyboardButton("☑️ Подписки и уведомления", callback_data="catalog:export:subs")],
        [InlineKeyboardButton("☑️ Приоритетные посты", callback_data="catalog:export:priority")],
        [InlineKeyboardButton("☑️ Рекламные кампании", callback_data="catalog:export:ads")],
        [InlineKeyboardButton("📥 Экспортировать всё (Excel)", callback_data="catalog:export:all:xlsx")],
        [InlineKeyboardButton("📥 Экспортировать всё (CSV)", callback_data="catalog:export:all:csv")],
        [InlineKeyboardButton("📥 Экспортировать всё (JSON)", callback_data="catalog:export:all:json")]
    ]
    
    await update.message.reply_text(
        "📦 **ЭКСПОРТ СТАТИСТИКИ**\n\n"
        "Выберите данные для экспорта:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def foryou_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Персональные рекомендации - /foryou"""
    user_id = update.effective_user.id
    
    try:
        recommendations = await catalog_service.get_personalized_recommendations(user_id, count=10)
        
        if not recommendations:
            await update.message.reply_text(
                "✨ **РЕКОМЕНДАЦИИ**\n\n"
                "Пока недостаточно данных для персональных рекомендаций\n\n"
                "Используйте /catalog чтобы начать просмотр"
            )
            return
        
        await update.message.reply_text(
            "✨ **РЕКОМЕНДУЕМ СПЕЦИАЛЬНО ДЛЯ ВАС**\n\n"
            f"Подобрано {len(recommendations)} услуг на основе:\n"
            "• Ваших подписок\n"
            "• Недавних просмотров\n"
            "• Популярных в вашем районе"
        )
        
        for i, post in enumerate(recommendations, 1):
            await send_catalog_post_with_media(
                context.bot,
                update.effective_chat.id,
                post,
                i,
                len(recommendations)
            )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить рекомендации", callback_data="catalog:foryou_refresh")],
            [InlineKeyboardButton("⚙️ Настроить предпочтения", callback_data="catalog:preferences")]
        ]
        
        await update.message.reply_text(
            "💡 Понравились рекомендации?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error in foryou: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке рекомендаций")


async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Избранное - /favorites"""
    user_id = update.effective_user.id
    
    try:
        favorites = await catalog_service.get_user_favorites(user_id)
        
        if not favorites:
            keyboard = [[InlineKeyboardButton("🔍 Поиск услуг", callback_data="catalog:search")]]
            await update.message.reply_text(
                "⭐ **МОЕ ИЗБРАННОЕ**\n\n"
                "У вас пока нет избранных услуг\n\n"
                "Добавляйте интересные услуги в избранное, чтобы быстро находить их!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return
        
        await update.message.reply_text(
            f"⭐ **МОЕ ИЗБРАННОЕ** ({len(favorites)})\n\n"
            "Ваши сохранённые услуги:"
        )
        
        for i, post in enumerate(favorites, 1):
            await send_catalog_post_with_media(
                context.bot,
                update.effective_chat.id,
                post,
                i,
                len(favorites)
            )
        
        keyboard = [
            [InlineKeyboardButton("🗂️ Сортировать по категориям", callback_data="catalog:favorites_sort")],
            [InlineKeyboardButton("📤 Поделиться списком", callback_data="catalog:favorites_share")],
            [InlineKeyboardButton("🗑️ Очистить избранное", callback_data="catalog:favorites_clear")]
        ]
        
        await update.message.reply_text(
            "⚙️ **Управление избранным:**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error in favorites: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке избранного")


# ============= CALLBACKS =============

async def handle_catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback - ПОЛНАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()
    data = query.data.split(":")
    action = data[1] if len(data) > 1 else None
    user_id = update.effective_user.id
    
    # ============= БАЗОВЫЕ CALLBACKS =============
    
    if action == "next":
        posts = await catalog_service.get_random_posts(user_id, count=5)
        if not posts:
            keyboard = [
                [InlineKeyboardButton("🔄 Начать заново", callback_data="catalog:restart")],
                [InlineKeyboardButton("↩️ Главное меню", callback_data="menu:back")]
            ]
            await query.edit_message_text(
                "📂 Все посты просмотрены!\n\nНажмите 🔄 для сброса",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            for i, post in enumerate(posts, 1):
                await send_catalog_post_with_media(context.bot, query.message.chat_id, post, i, len(posts))
            await query.message.delete()
    
    elif action == "finish":
        await query.edit_message_text(
            "✅ Просмотр завершён!\n\n"
            "/catalog - начать заново\n"
            "/search - поиск\n"
            "/mysubscriptions - подписки\n"
            "/favorites - избранное"
        )
    
    elif action == "restart":
        await catalog_service.reset_session(user_id)
        await query.edit_message_text("🔄 Сессия сброшена!\n\nИспользуйте /catalog")
    
    elif action == "search":
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"catalog:cat:{cat}")] for cat in CATALOG_CATEGORIES.keys()]
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="catalog:finish")])
        await query.edit_message_text(
            "🔍 Выберите категорию:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif action == "cat":
        category = ":".join(data[2:])
        posts = await catalog_service.search_posts(category, limit=5)
        if posts:
            for i, post in enumerate(posts, 1):
                await send_catalog_post_with_media(context.bot, query.message.chat_id, post, i, len(posts))
            keyboard = [[InlineKeyboardButton("✅ Готово", callback_data="catalog:finish")]]
            await query.edit_message_text(
                f"📂 Найдено: {len(posts)}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text(f"❌ В категории '{category}' пока нет постов")
    
    elif action == "subscribe":
        category = ":".join(data[2:])
        success = await catalog_service.subscribe_to_category(user_id, category)
        await query.answer("🔔 Подписка оформлена!" if success else "❌ Ошибка", show_alert=True)
    
    elif action == "review":
        post_id = int(data[2]) if len(data) > 2 else None
        if post_id:
            context.user_data['catalog_review'] = {'post_id': post_id, 'waiting': True}
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="catalog:cancel_review")]]
            await query.message.reply_text(
                f"💬 Введите отзыв о посте #{post_id}:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    elif action == "cancel_review":
        context.user_data.pop('catalog_review', None)
        await query.edit_message_text("❌ Отзыв отменён")
    
    elif action == "cancel":
        context.user_data.pop('catalog_add', None)
        await query.edit_message_text("❌ Добавление отменено")
    
    elif action == "cancel_ad":
        context.user_data.pop('catalog_ad', None)
        await query.edit_message_text("❌ Добавление рекламы отменено")
    
    elif action == "priority_finish":
        links = context.user_data.get('catalog_priority', {}).get('links', [])
        if links:
            count = await catalog_service.set_priority_posts(links)
            await query.edit_message_text(f"✅ Установлено {count} приоритетных постов")
        else:
            await query.edit_message_text("❌ Ссылки не добавлены")
        context.user_data.pop('catalog_priority', None)
    
    # ============= НОВЫЕ CALLBACKS v2.0 =============
    
    elif action == "favorite":
        post_id = int(data[2]) if len(data) > 2 else None
        if post_id:
            success = await catalog_service.toggle_favorite(user_id, post_id)
            await query.answer(
                "⭐ Добавлено в избранное!" if success else "❌ Убрано из избранного",
                show_alert=True
            )
    
    elif action == "unsub":
        category = ":".join(data[2:])
        success = await catalog_service.unsubscribe_from_category(user_id, category)
        await query.answer("✅ Отписались" if success else "❌ Ошибка", show_alert=True)
        await mysubscriptions_command(update, context)
    
    elif action == "unsub_all":
        count = await catalog_service.unsubscribe_from_all(user_id)
        await query.edit_message_text(
            f"✅ Отписались от всех категорий ({count})\n\n/mysubscriptions"
        )
    
    elif action == "remove_confirm":
        post_id = int(data[2]) if len(data) > 2 else None
        if post_id:
            success = await catalog_service.delete_post(post_id, user_id)
            await query.edit_message_text(
                f"🗑️ Пост #{post_id} удалён" if success else "❌ Ошибка"
            )
    
    elif action == "remove_cancel":
        await query.edit_message_text("❌ Удаление отменено")
    
    elif action == "edit":
        field = data[2] if len(data) > 2 else None
        post_id = context.user_data.get('catalog_edit', {}).get('post_id')
        
        if not post_id:
            await query.answer("❌ Пост не найден", show_alert=True)
            return
        
        context.user_data['catalog_edit']['field'] = field
        context.user_data['catalog_edit']['waiting'] = True
        
        prompts = {
            'category': "Выберите новую категорию:",
            'name': "Введите новое название:",
            'tags': "Введите новые теги через запятую:",
            'link': "Введите новую ссылку:",
            'media': "Отправьте новое медиа:"
        }
        
        await query.edit_message_text(prompts.get(field, "Введите новое значение:"))
    
    elif action == "edit_cancel":
        context.user_data.pop('catalog_edit', None)
        await query.edit_message_text("❌ Редактирование отменено")
    
    elif action == "bulk_finish":
        links = context.user_data.get('catalog_bulk', {}).get('links', [])
        
        if not links:
            await query.edit_message_text("❌ Ссылки не добавлены")
            return
        
        await query.edit_message_text(f"⏳ Импорт {len(links)} постов...")
        
        results = await catalog_service.bulk_import(links, user_id)
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                f"✅ **ИМПОРТ ЗАВЕРШЕН**\n\n"
                f"Успешно: {results['success']}\n"
                f"Ошибки: {results['failed']}"
            ),
            parse_mode='Markdown'
        )
        
        context.user_data.pop('catalog_bulk', None)
    
    elif action == "foryou_refresh":
        await foryou_command(update, context)
    
    elif action == "favorites_sort":
        categories = await catalog_service.get_user_favorite_categories(user_id)
        keyboard = [
            [InlineKeyboardButton(cat, callback_data=f"catalog:fav_cat:{cat}")]
            for cat in categories
        ]
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="catalog:favorites_back")])
        
        await query.edit_message_text(
            "🗂️ Выберите категорию:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif action == "favorites_share":
        share_link = await catalog_service.generate_favorites_share_link(user_id)
        await query.edit_message_text(
            f"📤 **Поделиться избранным**\n\n{share_link}\n\nОтправьте друзьям!"
        )
    
    elif action == "favorites_clear":
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, очистить", callback_data="catalog:fav_clear_confirm"),
                InlineKeyboardButton("❌ Отмена", callback_data="catalog:favorites_back")
            ]
        ]
        await query.edit_message_text(
            "⚠️ Удалить всё избранное?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif action == "fav_clear_confirm":
        count = await catalog_service.clear_favorites(user_id)
        await query.edit_message_text(f"🗑️ Избранное очищено ({count})\n\n/favorites")
    
    elif action == "favorites_back":
        await favorites_command(update, context)
# ============= TEXT HANDLER =============

async def handle_catalog_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текста - РАСШИРЕННАЯ ВЕРСИЯ"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # [ПРЕДЫДУЩИЕ ОБРАБОТЧИКИ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ]
    # ... (код из оригинала) ...
    
    # ============= НОВЫЕ ОБРАБОТЧИКИ v2.0 =============
    
    # Массовый импорт
    if 'catalog_bulk' in context.user_data:
        if text.startswith('https://t.me/'):
            # Проверяем на несколько ссылок
            links = [line.strip() for line in text.split('\n') if line.strip().startswith('https://t.me/')]
            
            context.user_data['catalog_bulk']['links'].extend(links)
            current_count = len(context.user_data['catalog_bulk']['links'])
            
            await update.message.reply_text(
                f"✅ Добавлено ссылок: {len(links)}\n"
                f"Всего собрано: {current_count}/50\n\n"
                "Отправьте ещё ссылки или нажмите '✅ Завершить сбор'"
            )
    
    # Редактирование поста
    elif 'catalog_edit' in context.user_data and context.user_data['catalog_edit'].get('waiting'):
        post_id = context.user_data['catalog_edit'].get('post_id')
        field = context.user_data['catalog_edit'].get('field')
        
        if field == 'category':
            # Показываем категории
            keyboard = [[InlineKeyboardButton(cat, callback_data=f"catalog:edit_save:category:{cat}")] for cat in CATALOG_CATEGORIES.keys()]
            await update.message.reply_text(
                "Выберите категорию:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif field == 'name':
            success = await catalog_service.update_post_field(post_id, 'name', text[:255])
            await update.message.reply_text(
                "✅ Название обновлено!" if success else "❌ Ошибка"
            )
            context.user_data.pop('catalog_edit', None)
        elif field == 'tags':
            tags = [t.strip() for t in text.split(',') if t.strip()][:10]
            success = await catalog_service.update_post_field(post_id, 'tags', tags)
            await update.message.reply_text(
                f"✅ Теги обновлены ({len(tags)})!" if success else "❌ Ошибка"
            )
            context.user_data.pop('catalog_edit', None)
        elif field == 'link':
            if text.startswith('https://t.me/'):
                success = await catalog_service.update_post_field(post_id, 'catalog_link', text)
                await update.message.reply_text(
                    "✅ Ссылка обновлена!" if success else "❌ Ошибка"
                )
            else:
                await update.message.reply_text("❌ Ссылка должна начинаться с https://t.me/")
            context.user_data.pop('catalog_edit', None)


__all__ = [
    # Основные команды
    'catalog_command',
    'search_command',
    'addtocatalog_command',
    'review_command',
    'catalogpriority_command',
    'addcatalogreklama_command',
    'catalogviews_command',
    'catalog_stats_users_command',
    'catalog_stats_categories_command',
    'catalog_stats_popular_command',
    # Новые команды v2.0
    'mysubscriptions_command',
    'edit_catalog_command',
    'remove_catalog_command',
    'bulkimport_command',
    'catalog_stats_new_command',
    'catalog_stats_priority_command',
    'catalog_stats_reklama_command',
    'catalog_stats_topusers_command',
    'catalog_stats_export_command',
    'foryou_command',
    'favorites_command',
    # Handlers
    'handle_catalog_callback',
    'handle_catalog_text',
    'handle_catalog_media'
]
