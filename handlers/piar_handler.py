# -*- coding: utf-8 -*-
"""
Optimized Piar (Services) Handler
Prefix: prc_ (piar/services callback)
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from services.db import db
from models import User, Post, PostStatus
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

# ============= CALLBACK PREFIX: prc_ =============
PIAR_CALLBACKS = {
    'preview': 'prc_prv',       # Show preview
    'send': 'prc_snd',          # Send to moderation
    'edit': 'prc_edt',          # Edit (restart)
    'cancel': 'prc_cnl',        # Cancel
    'add_photo': 'prc_adp',     # Add photo
    'skip_photo': 'prc_skp',    # Skip photo
    'next_photo': 'prc_nxt',    # Next (preview)
    'back': 'prc_bck'           # Back to previous step
}

# Piar form steps - 8 steps
PIAR_STEPS = [
    ('name', 'Имя', "💭 Шаг 1/8\n\n💭 Укажите своё имя, псевдоним:"),
    ('profession', 'Профессия', "💭 Шаг 2/8\n\n💭 Какие *услуги* вы предоставляете?"),
    ('districts', 'Районы', "💭 Шаг 3/8\n\n💭 В каких *районах* работаете?"),
    ('phone', 'Телефон', "💭 Шаг 4/8\n\n💭 *Телефон* (или `-` для пропуска):"),
    ('instagram', 'Instagram', "💭 Шаг 5/8\n\n💭 *Instagram* (или `-` для пропуска):"),
    ('telegram', 'Telegram', "💭 Шаг 6/8\n\n💭 *Telegram* (или `-` для пропуска):"),
    ('price', 'Цена', "💭 Шаг 7/8\n\n💭 Укажите *цену* за услуги:"),
    ('description', 'Описание', "💭 Шаг 8/8\n\n💭 *Описание* услуг:")
]

async def handle_piar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unified piar callback handler"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    handlers = {
        PIAR_CALLBACKS['preview']: show_piar_preview,
        PIAR_CALLBACKS['send']: send_piar_to_moderation,
        PIAR_CALLBACKS['edit']: restart_piar_form,
        PIAR_CALLBACKS['cancel']: cancel_piar,
        PIAR_CALLBACKS['add_photo']: request_piar_photo,
        PIAR_CALLBACKS['skip_photo']: show_piar_preview,
        PIAR_CALLBACKS['next_photo']: show_piar_preview,
        PIAR_CALLBACKS['back']: go_back_step
    }
    
    handler = handlers.get(action)
    if handler:
        await handler(update, context)

async def handle_piar_text(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           field: str, value: str):
    """Handle text input for piar form"""
    if 'piar_data' not in context.user_data:
        context.user_data['piar_data'] = {}
    
    context.user_data['piar_step'] = field
    
    # Validate and save
    validators = {
        'name': lambda v: len(v) <= 100,
        'profession': lambda v: len(v) <= 100,
        'districts': lambda v: len([d.strip() for d in v.split(',')]) <= 3,
        'phone': lambda v: v == '-' or len(v) >= 7,
        'price': lambda v: len(v) <= 100,
        'description': lambda v: len(v) <= 1000
    }
    
    if field in validators and not validators[field](value):
        errors = {
            'name': "Имя слишком длинное (макс. 100)",
            'profession': "Профессия слишком длинная (макс. 100)",
            'districts': "Макс. 3 района",
            'phone': "Номер слишком короткий (мин. 7)",
            'price': "Цена слишком длинная (макс. 100)",
            'description': "Описание слишком длинное (макс. 1000)"
        }
        await update.message.reply_text(f"❌ {errors[field]}")
        return
    
    # Save data
    if field == 'districts':
        context.user_data['piar_data'][field] = [d.strip() for d in value.split(',')][:3]
    elif field in ['phone', 'instagram', 'telegram']:
        context.user_data['piar_data'][field] = None if value == '-' else value.strip()
    else:
        context.user_data['piar_data'][field] = value.strip()
    
    # Next step
    current_idx = next(i for i, (f, _, _) in enumerate(PIAR_STEPS) if f == field)
    
    if current_idx < len(PIAR_STEPS) - 1:
        next_field, next_name, next_text = PIAR_STEPS[current_idx + 1]
        context.user_data['waiting_for'] = f'piar_{next_field}'
        
        keyboard = []
        if current_idx >= 0:
            keyboard.append([InlineKeyboardButton("↩️ Назад", callback_data=PIAR_CALLBACKS['back'])])
        keyboard.append([InlineKeyboardButton("🗯️ Отмена", callback_data=PIAR_CALLBACKS['cancel'])])
        
        await update.message.reply_text(
            next_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        # Photos step
        context.user_data['piar_data']['photos'] = []
        context.user_data['piar_data']['media'] = []
        context.user_data['waiting_for'] = 'piar_photo'
        
        keyboard = [
            [InlineKeyboardButton("✅ Дальше", callback_data=PIAR_CALLBACKS['skip_photo'])],
            [InlineKeyboardButton("🚩 Отмена", callback_data=PIAR_CALLBACKS['cancel'])]
        ]
        
        await update.message.reply_text(
            "📷 *Шаг 8 - Фото*\n\nДо 3 фото/видео\n'Дальше' - без медиа",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def handle_piar_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo input"""
    if context.user_data.get('waiting_for') != 'piar_photo':
        return
    
    if 'piar_data' not in context.user_data:
        return
    
    photos = context.user_data['piar_data'].get('photos', [])
    media = context.user_data['piar_data'].get('media', [])
    
    if len(photos) >= Config.MAX_PHOTOS_PIAR:
        await update.message.reply_text(f"💿 Максимум {Config.MAX_PHOTOS_PIAR} фото")
        return
    
    media_added = False
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        photos.append(file_id)
        media.append({'type': 'photo', 'file_id': file_id})
        media_added = True
    elif update.message.video:
        file_id = update.message.video.file_id
        photos.append(file_id)
        media.append({'type': 'video', 'file_id': file_id})
        media_added = True
    
    if media_added:
        context.user_data['piar_data']['photos'] = photos
        context.user_data['piar_data']['media'] = media
        
        remaining = Config.MAX_PHOTOS_PIAR - len(photos)
        
        keyboard = []
        if remaining > 0:
            keyboard.append([InlineKeyboardButton(f"📸 Еще ({remaining})", callback_data=PIAR_CALLBACKS['add_photo'])])
        keyboard.append([InlineKeyboardButton("🩵 Предпросмотр", callback_data=PIAR_CALLBACKS['next_photo'])])
        keyboard.append([InlineKeyboardButton("👹 Отмена", callback_data=PIAR_CALLBACKS['cancel'])])
        
        await update.message.reply_text(
            f"🎬 Добавлено ({len(photos)})",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def show_piar_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show piar preview"""
    if 'piar_data' not in context.user_data:
        await update.callback_query.edit_message_text("👹 Данные не найдены")
        return
    
    data = context.user_data['piar_data']
    
    # Build text
    text = "💌 *Предпросмотр заявки*\n\n"
    text += f"🙋🏼‍♂️ *Имя:* {data.get('name')}\n"
    text += f"👷🏽‍♂️ *Услуга:* {data.get('profession')}\n"
    text += f"🏘️ *Районы:* {', '.join(data.get('districts', []))}\n"
    
    if data.get('phone'):
        text += f"🤳 *Телефон:* {data.get('phone')}\n"
    
    contacts = []
    if data.get('instagram'):
        contacts.append(f"🟧 Instagram: @{data.get('instagram')}")
    if data.get('telegram'):
        contacts.append(f"🔷 Telegram: {data.get('telegram')}")
    
    if contacts:
        text += f"📘 *Контакты:*\n{chr(10).join(contacts)}\n"
    
    text += f"💳 *Прайс:* {data.get('price')}\n\n"
    text += f"📝 *Описание:*\n{data.get('description')}\n\n"
    
    if data.get('photos'):
        text += f"💽 Медиа: {len(data['photos'])}\n\n"
    
    text += "#Услуги #КаталогУслуг\n\n" + Config.DEFAULT_SIGNATURE
    
    keyboard = [
        [
            InlineKeyboardButton("✅ На модерацию", callback_data=PIAR_CALLBACKS['send']),
            InlineKeyboardButton("🔏 Изменить", callback_data=PIAR_CALLBACKS['edit'])
        ],
        [InlineKeyboardButton("🚗 Отмена", callback_data=PIAR_CALLBACKS['cancel'])]
    ]
    
    try:
        await update.callback_query.delete_message()
    except:
        pass
    
    # Show media first
    if data.get('media'):
        for i, item in enumerate(data['media'][:3]):
            try:
                caption = f"📷 Медиа ({len(data['media'])} шт.)" if i == 0 else None
                if item['type'] == 'photo':
                    await update.effective_message.reply_photo(item['file_id'], caption=caption)
                elif item['type'] == 'video':
                    await update.effective_message.reply_video(item['file_id'], caption=caption)
            except Exception as e:
                logger.error(f"Preview media error: {e}")
    
    # Show text with buttons
    await update.effective_message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def send_piar_to_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send piar to moderation"""
    user_id = update.effective_user.id
    data = context.user_data.get('piar_data', {})
    
    try:
        if not db.session_maker:
            await update.callback_query.edit_message_text("🚨 БД недоступна")
            return
        
        async with db.get_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                await update.callback_query.edit_message_text("🚨 Пользователь не найден. /start")
                return
            
            # Create post
            post = Post(
                user_id=int(user_id),
                category='🙅 Каталог Услуг',
                text=str(data.get('description', ''))[:1000],
                hashtags=['#Услуги', '#КаталогУслуг'],
                is_piar=True,
                piar_name=str(data.get('name', ''))[:100],
                piar_profession=str(data.get('profession', ''))[:100],
                piar_districts=list(data.get('districts', [])),
                piar_phone=str(data.get('phone', ''))[:50] if data.get('phone') else None,
                piar_price=str(data.get('price', ''))[:100],
                piar_instagram=str(data.get('instagram', ''))[:100] if data.get('instagram') else None,
                piar_telegram=str(data.get('telegram', ''))[:100] if data.get('telegram') else None,
                piar_description=str(data.get('description', ''))[:1000],
                media=list(data.get('media', [])),
                anonymous=False,
                status=PostStatus.PENDING
            )
            session.add(post)
            await session.flush()
            await session.commit()
            await session.refresh(post)
            
            # Send to mod group
            await send_to_mod_group(update, context, post, user, data)
            
            context.user_data.pop('piar_data', None)
            context.user_data.pop('waiting_for', None)
            context.user_data.pop('piar_step', None)
            
            cooldown_mins = Config.COOLDOWN_SECONDS // 60
            
            success_keyboard = [
                [InlineKeyboardButton("🙅‍♂️ Канал", url="https://t.me/snghu")],
                [InlineKeyboardButton("🧍‍♂️ Главное меню", callback_data="mnc_bk")]
            ]
            
            await update.callback_query.edit_message_text(
                f"✅ *Заявка отправлена!*\n\n"
                f"После проверки вам придёт уведомление\n\n"
                f"💤 Следующая заявка через {cooldown_mins} мин",
                reply_markup=InlineKeyboardMarkup(success_keyboard),
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Send piar error: {e}", exc_info=True)
        await update.callback_query.edit_message_text("🚗 Ошибка. /start")

async def send_to_mod_group(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            post: Post, user: User, data: dict):
    """Send to moderation group"""
    bot = context.bot
    username = user.username if user.username else f"ID_{user.id}"
    
    mod_text = (
        f"⭐️ Новая заявка - Каталог Услуг\n\n"
        f"🧍‍♂️ @{username} (ID: {user.id})\n"
        f"😀 Имя: {data.get('name', '')}\n"
        f"🥱 Профессия: {data.get('profession', '')}\n"
        f"🏣 Районы: {', '.join(data.get('districts', []))}\n"
    )
    
    contacts = []
    if data.get('phone'):
        contacts.append(f"📞 Телефон: {data.get('phone')}")
    if data.get('instagram'):
        contacts.append(f"📷 Instagram: @{data.get('instagram')}")
    if data.get('telegram'):
        contacts.append(f"📱 Telegram: {data.get('telegram')}")
    
    if contacts:
        mod_text += f"📞 Контакты:\n{chr(10).join(contacts)}\n"
    
    mod_text += f"💰 Цена: {data.get('price', '')}\n"
    
    if data.get('media'):
        mod_text += f"📎 Медиа: {len(data['media'])} файл(ов)\n"
    
    description = data.get('description', '')[:300]
    if len(data.get('description', '')) > 300:
        description += "..."
    mod_text += f"\n📝 Описание:\n{description}"
    
    keyboard = [[
        InlineKeyboardButton("✅ Опубликовать", callback_data=f"mdc_ap:{post.id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"mdc_rj:{post.id}")
    ]]
    
    try:
        # Send media
        if data.get('media'):
            for i, item in enumerate(data['media']):
                try:
                    if item['type'] == 'photo':
                        await bot.send_photo(Config.MODERATION_GROUP_ID, item['file_id'])
                    elif item['type'] == 'video':
                        await bot.send_video(Config.MODERATION_GROUP_ID, item['file_id'])
                except Exception as e:
                    logger.error(f"Send piar media error: {e}")
        
        # Send text
        await bot.send_message(
            Config.MODERATION_GROUP_ID,
            mod_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Send to mod group error: {e}")

async def request_piar_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request more photos"""
    context.user_data['waiting_for'] = 'piar_photo'
    
    keyboard = [
        [InlineKeyboardButton("☑️ Дальше", callback_data=PIAR_CALLBACKS['next_photo'])],
        [InlineKeyboardButton("🔚 Отмена", callback_data=PIAR_CALLBACKS['cancel'])]
    ]
    
    await update.callback_query.edit_message_text(
        "💡 *Добавьте ещё фото/видео:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def go_back_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to previous step"""
    current_step = context.user_data.get('piar_step')
    
    if not current_step:
        await restart_piar_form(update, context)
        return
    
    step_order = [s[0] for s in PIAR_STEPS]
    
    try:
        current_idx = step_order.index(current_step)
        if current_idx > 0:
            prev_field, prev_name, prev_text = PIAR_STEPS[current_idx - 1]
            context.user_data['waiting_for'] = f'piar_{prev_field}'
            context.user_data['piar_step'] = prev_field
            
            keyboard = []
            if current_idx > 1:
                keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=PIAR_CALLBACKS['back'])])
            keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data=PIAR_CALLBACKS['cancel'])])
            
            await update.callback_query.edit_message_text(
                prev_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await restart_piar_form(update, context)
    except:
        await restart_piar_form(update, context)

async def restart_piar_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restart form"""
    context.user_data['piar_data'] = {}
    context.user_data['waiting_for'] = 'piar_name'
    context.user_data['piar_step'] = 'name'
    
    keyboard = [[InlineKeyboardButton("🗯️ Главное меню", callback_data="mnc_bk")]]
    
    text = (
        "📑 *Заявка в каталог*\n\n"
        "🧲 *Цель:* упростить жизнь\n\n"
        "*Шаг 1 из 8*\n"
        "💭 Укажите своё имя:"
    )
    
    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

async def cancel_piar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel piar"""
    context.user_data.pop('piar_data', None)
    context.user_data.pop('waiting_for', None)
    context.user_data.pop('piar_step', None)
    
    from handlers.start_handler import show_main_menu
    await show_main_menu(update, context)

__all__ = [
    'handle_piar_callback', 'handle_piar_text', 'handle_piar_photo', 
    'PIAR_CALLBACKS', 'PIAR_STEPS'
]
