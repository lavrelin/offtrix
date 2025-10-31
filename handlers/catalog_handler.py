from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from config import Config
from keyboards import (
    CATALOG_CALLBACKS,
    get_navigation_keyboard,
    get_catalog_card_keyboard,
    get_category_keyboard,
    get_rating_keyboard,
    get_cancel_search_keyboard,
    get_catalog_cancel_keyboard,
    get_cancel_review_keyboard,
    get_reviews_menu_keyboard
)
from services.cooldown import cooldown_service, CooldownType
from services.db import db
from models import CatalogPost, CatalogReview
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

CATALOG_CATEGORIES = ["👱🏻‍♀️ Девушки", "🤵🏼‍♂️ Парни", "👥 Пары", "🎬 Контент", "🎭 Прочее"]
REVIEW_COOLDOWN_HOURS = 24

def check_user_reviewed_post(user_id: int, post_id: int) -> bool:
    """Проверка, оставил ли пользователь отзыв"""
    return False

async def catalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать каталог"""
    user_id = update.effective_user.id
    
    async with db.session_maker() as session:
        try:
            from sqlalchemy import select
            
            stmt = select(CatalogPost).where(
                CatalogPost.status == 'approved'
            ).order_by(CatalogPost.created_at.desc()).limit(1)
            
            result = await session.execute(stmt)
            post = result.scalar_one_or_none()
            
            if not post:
                await update.message.reply_text(
                    "📂 Каталог пуст\n\n"
                    "Добавьте первую карточку: /addtocatalog"
                )
                return
            
            context.user_data['catalog_browse'] = {
                'current_post_id': post.id,
                'offset': 0
            }
            
            caption = (
                f"📂 {post.category}\n"
                f"📝 {post.name}\n"
                f"🏷️ {', '.join(post.tags[:5]) if post.tags else 'Нет тегов'}\n"
                f"⭐ #{post.catalog_number}\n"
                f"💬 Отзывов: {post.review_count or 0}"
            )
            
            if post.media_type == 'photo' and post.media_file_id:
                await update.message.reply_photo(
                    photo=post.media_file_id,
                    caption=caption,
                    reply_markup=get_catalog_card_keyboard(post.__dict__, post.catalog_number)
                )
            else:
                await update.message.reply_text(
                    caption,
                    reply_markup=get_catalog_card_keyboard(post.__dict__, post.catalog_number)
                )
            
        except Exception as e:
            logger.error(f"Catalog error: {e}")
            await update.message.reply_text("❌ Ошибка загрузки каталога")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск в каталоге"""
    context.user_data['catalog_search'] = {'step': 'waiting'}
    await update.message.reply_text(
        "🔍 Поиск в каталоге\n\n"
        "Введите название или номер карточки:",
        reply_markup=get_cancel_search_keyboard()
    )

async def addtocatalog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление в каталог"""
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ Только для админов")
        return
    
    context.user_data['catalog_add'] = {'step': 'category'}
    await update.message.reply_text(
        "📂 Добавление в каталог\n\nШаг 1/5\n\nВыберите категорию:",
        reply_markup=get_category_keyboard(CATALOG_CATEGORIES)
    )

async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Оставить отзыв"""
    args = context.args
    if not args:
        await update.message.reply_text(
            "📝 Использование: /review [номер]\n\n"
            "Например: /review 123"
        )
        return
    
    try:
        catalog_number = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный номер")
        return
    
    user_id = update.effective_user.id
    
    async with db.session_maker() as session:
        try:
            from sqlalchemy import select
            
            stmt = select(CatalogPost).where(
                CatalogPost.catalog_number == catalog_number,
                CatalogPost.status == 'approved'
            )
            
            result = await session.execute(stmt)
            post = result.scalar_one_or_none()
            
            if not post:
                await update.message.reply_text("❌ Карточка не найдена")
                return
            
            if check_user_reviewed_post(user_id, post.id):
                await update.message.reply_text("❌ Вы уже оставили отзыв на эту карточку")
                return
            
            can_use, remaining = await cooldown_service.check_cooldown(
                user_id=user_id,
                command='review',
                duration=REVIEW_COOLDOWN_HOURS * 3600,
                cooldown_type=CooldownType.NORMAL
            )
            
            if not can_use:
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                await update.message.reply_text(
                    f"⏳ Следующий отзыв через: {hours}ч {minutes}м"
                )
                return
            
            context.user_data['catalog_review'] = {
                'post_id': post.id,
                'catalog_number': catalog_number,
                'step': 'rating'
            }
            
            await update.message.reply_text(
                f"⭐ Оценка #{catalog_number}\n\nВыберите рейтинг:",
                reply_markup=get_rating_keyboard(post.id, catalog_number)
            )
            
        except Exception as e:
            logger.error(f"Review error: {e}")
            await update.message.reply_text("❌ Ошибка")

async def categoryfollow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подписка на категории"""
    await update.message.reply_text(
        "📋 Подписки на категории\n\n"
        "Эта функция в разработке"
    )

async def addgirltocat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Быстрое добавление девушки"""
    if update.effective_user.id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ Только для админов")
        return
    
    context.user_data['catalog_add'] = {
        'step': 'catalog_link',
        'category': '👱🏻‍♀️ Девушки'
    }
    await update.message.reply_text(
        "📂 Девушки\n\nШаг 2/5\n\nОтправьте ссылку на профиль:",
        reply_markup=get_catalog_cancel_keyboard()
    )

async def addboytocat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Быстрое добавление парня"""
    if update.effective_user.id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ Только для админов")
        return
    
    context.user_data['catalog_add'] = {
        'step': 'catalog_link',
        'category': '🤵🏼‍♂️ Парни'
    }
    await update.message.reply_text(
        "📂 Парни\n\nШаг 2/5\n\nОтправьте ссылку на профиль:",
        reply_markup=get_catalog_cancel_keyboard()
    )

async def handle_catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех catalog callback"""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    
    async def safe_edit(text, keyboard=None):
        try:
            if keyboard:
                await query.edit_message_caption(caption=text, reply_markup=keyboard)
            else:
                await query.edit_message_caption(caption=text)
        except BadRequest:
            try:
                if keyboard:
                    await query.edit_message_text(text=text, reply_markup=keyboard)
                else:
                    await query.edit_message_text(text=text)
            except:
                pass
    
    if data == CATALOG_CALLBACKS['cancel']:
        context.user_data.pop('catalog_add', None)
        context.user_data.pop('catalog_search', None)
        await safe_edit("❌ Отменено")
        return
    
    if data == CATALOG_CALLBACKS['cancel_search']:
        context.user_data.pop('catalog_search', None)
        await safe_edit("❌ Поиск отменён")
        return
    
    if data == CATALOG_CALLBACKS['cancel_review']:
        context.user_data.pop('catalog_review', None)
        await safe_edit("❌ Отзыв отменён")
        return
    
    if data == CATALOG_CALLBACKS['close_menu']:
        await query.message.delete()
        return
    
    if data.startswith(CATALOG_CALLBACKS['add_cat']):
        parts = data.split(':', 1)
        if len(parts) == 2:
            category = parts[1]
            context.user_data['catalog_add'] = {
                'step': 'catalog_link',
                'category': category
            }
            await safe_edit(
                f"📂 {category}\n\nШаг 2/5\n\nОтправьте ссылку на профиль:",
                get_catalog_cancel_keyboard()
            )
        return
    
    if data.startswith(CATALOG_CALLBACKS['rate']):
        parts = data.split(':')
        
        if len(parts) == 3:
            post_id = int(parts[1])
            catalog_number = int(parts[2])
            
            if check_user_reviewed_post(user_id, post_id):
                await query.answer("❌ Вы уже оценили эту карточку", show_alert=True)
                return
            
            can_use, remaining = await cooldown_service.check_cooldown(
                user_id=user_id,
                command='review',
                duration=REVIEW_COOLDOWN_HOURS * 3600,
                cooldown_type=CooldownType.NORMAL
            )
            
            if not can_use:
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                await query.answer(f"⏳ Следующий отзыв через: {hours}ч {minutes}м", show_alert=True)
                return
            
            context.user_data['catalog_review'] = {
                'post_id': post_id,
                'catalog_number': catalog_number,
                'step': 'rating'
            }
            
            await safe_edit(
                f"⭐ Оценка #{catalog_number}\n\nВыберите рейтинг:",
                get_rating_keyboard(post_id, catalog_number)
            )
        
        elif len(parts) == 4:
            rating = int(parts[1])
            post_id = int(parts[2])
            catalog_number = int(parts[3])
            
            review_data = context.user_data.get('catalog_review', {})
            if review_data.get('post_id') != post_id:
                await query.answer("❌ Ошибка данных", show_alert=True)
                return
            
            review_data['rating'] = rating
            review_data['step'] = 'text'
            
            await safe_edit(
                f"⭐ Оценка: {rating}/5\n\nТеперь напишите текст отзыва:",
                get_cancel_review_keyboard()
            )
        return
    
    if data.startswith(CATALOG_CALLBACKS['next']):
        browse_data = context.user_data.get('catalog_browse', {})
        
        async with db.session_maker() as session:
            try:
                from sqlalchemy import select
                
                offset = browse_data.get('offset', 0) + 1
                
                stmt = select(CatalogPost).where(
                    CatalogPost.status == 'approved'
                ).order_by(CatalogPost.created_at.desc()).offset(offset).limit(1)
                
                result = await session.execute(stmt)
                post = result.scalar_one_or_none()
                
                if not post:
                    await query.answer("📂 Больше карточек нет", show_alert=True)
                    return
                
                browse_data['current_post_id'] = post.id
                browse_data['offset'] = offset
                
                caption = (
                    f"📂 {post.category}\n"
                    f"📝 {post.name}\n"
                    f"🏷️ {', '.join(post.tags[:5]) if post.tags else 'Нет тегов'}\n"
                    f"⭐ #{post.catalog_number}\n"
                    f"💬 Отзывов: {post.review_count or 0}"
                )
                
                if post.media_type == 'photo' and post.media_file_id:
                    await query.message.delete()
                    await context.bot.send_photo(
                        chat_id=query.message.chat.id,
                        photo=post.media_file_id,
                        caption=caption,
                        reply_markup=get_catalog_card_keyboard(post.__dict__, post.catalog_number)
                    )
                else:
                    await safe_edit(
                        caption,
                        get_catalog_card_keyboard(post.__dict__, post.catalog_number)
                    )
                
            except Exception as e:
                logger.error(f"Next catalog error: {e}")
                await query.answer("❌ Ошибка загрузки", show_alert=True)
        return

async def handle_catalog_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текста для каталога"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if 'catalog_add' in context.user_data:
        data = context.user_data['catalog_add']
        step = data.get('step')
        
        if step == 'catalog_link':
            data['catalog_link'] = text
            data['step'] = 'name'
            await update.message.reply_text(
                "📝 Шаг 3/5\n\nВведите название:",
                reply_markup=get_catalog_cancel_keyboard()
            )
        elif step == 'name':
            data['name'] = text[:100]
            data['step'] = 'media'
            await update.message.reply_text(
                "📸 Шаг 4/5\n\nОтправьте фото или видео\n(или /skip для пропуска):",
                reply_markup=get_catalog_cancel_keyboard()
            )
        elif text == '/skip' and step == 'media':
            data['step'] = 'tags'
            await update.message.reply_text(
                "#️⃣ Шаг 5/5\n\nТеги через запятую:",
                reply_markup=get_catalog_cancel_keyboard()
            )
        elif step == 'tags':
            tags = [t.strip() for t in text.split(',') if t.strip()][:10]
            data['tags'] = tags
            
            async with db.session_maker() as session:
                try:
                    from sqlalchemy import select, func
                    
                    stmt = select(func.coalesce(func.max(CatalogPost.catalog_number), 0))
                    result = await session.execute(stmt)
                    max_number = result.scalar()
                    new_number = max_number + 1
                    
                    new_post = CatalogPost(
                        user_id=user_id,
                        catalog_link=data['catalog_link'],
                        category=data['category'],
                        name=data['name'],
                        tags=tags,
                        media_type=data.get('media_type'),
                        media_file_id=data.get('media_file_id'),
                        status='approved',
                        catalog_number=new_number,
                        created_at=datetime.utcnow(),
                        review_count=0
                    )
                    
                    session.add(new_post)
                    await session.commit()
                    
                    await update.message.reply_text(
                        f"✅ Пост #{new_number} добавлен!\n\n"
                        f"📂 {data['category']}\n"
                        f"📝 {data['name']}\n"
                        f"🏷️ {len(tags)} тегов"
                    )
                    context.user_data.pop('catalog_add', None)
                    
                except Exception as e:
                    logger.error(f"Add post error: {e}")
                    await update.message.reply_text("❌ Ошибка при добавлении")
        return
    
    if 'catalog_search' in context.user_data:
        search_data = context.user_data['catalog_search']
        if search_data.get('step') == 'waiting':
            query_text = text.strip()
            
            async with db.session_maker() as session:
                try:
                    from sqlalchemy import select, or_
                    
                    try:
                        catalog_number = int(query_text)
                        stmt = select(CatalogPost).where(
                            CatalogPost.catalog_number == catalog_number,
                            CatalogPost.status == 'approved'
                        )
                    except ValueError:
                        stmt = select(CatalogPost).where(
                            CatalogPost.status == 'approved',
                            or_(
                                CatalogPost.name.ilike(f'%{query_text}%'),
                                CatalogPost.tags.contains([query_text])
                            )
                        ).limit(1)
                    
                    result = await session.execute(stmt)
                    post = result.scalar_one_or_none()
                    
                    if not post:
                        await update.message.reply_text("❌ Ничего не найдено")
                        context.user_data.pop('catalog_search', None)
                        return
                    
                    caption = (
                        f"📂 {post.category}\n"
                        f"📝 {post.name}\n"
                        f"🏷️ {', '.join(post.tags[:5]) if post.tags else 'Нет тегов'}\n"
                        f"⭐ #{post.catalog_number}\n"
                        f"💬 Отзывов: {post.review_count or 0}"
                    )
                    
                    if post.media_type == 'photo' and post.media_file_id:
                        await update.message.reply_photo(
                            photo=post.media_file_id,
                            caption=caption,
                            reply_markup=get_catalog_card_keyboard(post.__dict__, post.catalog_number)
                        )
                    else:
                        await update.message.reply_text(
                            caption,
                            reply_markup=get_catalog_card_keyboard(post.__dict__, post.catalog_number)
                        )
                    
                    context.user_data.pop('catalog_search', None)
                    
                except Exception as e:
                    logger.error(f"Search error: {e}")
                    await update.message.reply_text("❌ Ошибка поиска")
        return
    
    if 'catalog_review' in context.user_data:
        review_data = context.user_data['catalog_review']
        if review_data.get('step') == 'text':
            review_text = text[:500]
            post_id = review_data['post_id']
            rating = review_data['rating']
            
            async with db.session_maker() as session:
                try:
                    new_review = CatalogReview(
                        post_id=post_id,
                        user_id=user_id,
                        rating=rating,
                        text=review_text,
                        created_at=datetime.utcnow()
                    )
                    
                    session.add(new_review)
                    
                    post = await session.get(CatalogPost, post_id)
                    if post:
                        post.review_count = (post.review_count or 0) + 1
                    
                    await session.commit()
                    
                    await update.message.reply_text(
                        f"✅ Отзыв добавлен!\n\n"
                        f"⭐ Оценка: {rating}/5\n"
                        f"💬 {review_text[:100]}"
                    )
                    context.user_data.pop('catalog_review', None)
                    
                except Exception as e:
                    logger.error(f"Review save error: {e}")
                    await update.message.reply_text("❌ Ошибка сохранения отзыва")
        return

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить карточку из каталога"""
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ Только для админов")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text(
            "🗑️ Использование: /remove [номер]\n\n"
            "Например: /remove 123"
        )
        return
    
    try:
        catalog_number = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный номер")
        return
    
    async with db.session_maker() as session:
        try:
            from sqlalchemy import select
            
            stmt = select(CatalogPost).where(
                CatalogPost.catalog_number == catalog_number
            )
            
            result = await session.execute(stmt)
            post = result.scalar_one_or_none()
            
            if not post:
                await update.message.reply_text("❌ Карточка не найдена")
                return
            
            post_name = post.name
            post_category = post.category
            
            await session.delete(post)
            await session.commit()
            
            await update.message.reply_text(
                f"✅ Карточка #{catalog_number} удалена\n\n"
                f"📂 {post_category}\n"
                f"📝 {post_name}"
            )
            
        except Exception as e:
            logger.error(f"Remove error: {e}")
            await update.message.reply_text("❌ Ошибка удаления")

async def handle_catalog_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик медиа для каталога"""
    if 'catalog_add' in context.user_data:
        data = context.user_data['catalog_add']
        if data.get('step') == 'media':
            if update.message.photo:
                data['media_type'] = 'photo'
                data['media_file_id'] = update.message.photo[-1].file_id
            elif update.message.video:
                data['media_type'] = 'video'
                data['media_file_id'] = update.message.video.file_id
            else:
                await update.message.reply_text("❌ Отправьте фото или видео")
                return
            
            data['step'] = 'tags'
            await update.message.reply_text(
                "#️⃣ Шаг 5/5\n\nТеги через запятую:",
                reply_markup=get_catalog_cancel_keyboard()
            )

__all__ = [
    'CATALOG_CALLBACKS',
    'catalog_command',
    'search_command',
    'addtocatalog_command',
    'remove_command',
    'review_command',
    'categoryfollow_command',
    'addgirltocat_command',
    'addboytocat_command',
    'handle_catalog_callback',
    'handle_catalog_text',
    'handle_catalog_media',
]
