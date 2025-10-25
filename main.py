# -*- coding: utf-8 -*-
"""
TrixBot Main - ВЕРСИЯ 5.0
С интеграцией catalog_service v5.0 и rating_handler v5.0
"""
import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)
from dotenv import load_dotenv
from config import Config

# ============= HANDLERS - ОСНОВНЫЕ =============
from handlers.start_handler import start_command, help_command, show_main_menu, show_write_menu
from handlers.menu_handler import handle_menu_callback
from handlers.publication_handler import handle_publication_callback, handle_text_input, handle_media_input
from handlers.piar_handler import handle_piar_callback, handle_piar_text, handle_piar_photo
from handlers.moderation_handler import (
    handle_moderation_callback,
    handle_moderation_text,
    ban_command,
    unban_command,
    mute_command,
    unmute_command,
    banlist_command,
    stats_command,
    top_command,
    lastseen_command
)
from handlers.profile_handler import handle_profile_callback
from handlers.basic_handler import id_command, participants_command, report_command
from handlers.link_handler import trixlinks_command

# ============= HANDLERS - ПРОДВИНУТАЯ МОДЕРАЦИЯ =============
from handlers.advanced_moderation import (
    del_command,
    purge_command,
    slowmode_command,
    noslowmode_command,
    lockdown_command,
    antiinvite_command,
    tagall_command,
    admins_command
)

# ============= HANDLERS - АДМИН =============
from handlers.admin_handler import admin_command, say_command, handle_admin_callback, broadcast_command, sendstats_command

# ============= HANDLERS - AUTOPOST =============
from handlers.autopost_handler import autopost_command, autopost_test_command

# ============= HANDLERS - RATING (TOPPEOPLE) v5.0 =============
from handlers.rating_handler import (
    itsme_command,
    toppeople_command,
    topboys_command,
    topgirls_command,
    toppeoplereset_command,
    handle_rate_callback,
    handle_rate_moderation_callback,
    handle_rate_photo,
    handle_rate_age,
    handle_rate_name,
    handle_rate_about,
    handle_rate_profile
)

# ============= HANDLERS - КАТАЛОГ v5.0 =============
from handlers.catalog_handler import (
    catalog_command,
    search_command,
    addtocatalog_command,
    review_command,
    categoryfollow_command,
    catalogpriority_command,
    addcatalogreklama_command,
    catalogviews_command,
    catalogview_command,
    catalog_stats_users_command,
    catalog_stats_categories_command,
    catalog_stats_popular_command,
    catalog_stats_priority_command,
    catalog_stats_reklama_command,
    edit_catalog_command,
    remove_catalog_command,
    handle_catalog_callback,
    handle_catalog_text,
    handle_catalog_media,
    change_catalog_number_command,
    addgirltocat_command,
    addboytocat_command,
    catalogads_command,
    removeads_command,
    admincataloginfo_command
)

# ============= HANDLERS - ИГРЫ =============
from handlers.games_handler import (
    wordadd_command, wordedit_command, wordclear_command,
    wordon_command, wordoff_command, wordinfo_command,
    wordinfoedit_command, anstimeset_command,
    gamesinfo_command, admgamesinfo_command, game_say_command,
    roll_participant_command, roll_draw_command,
    rollreset_command, rollstatus_command, mynumber_command,
    handle_game_text_input, handle_game_media_input, handle_game_callback
)

# ============= HANDLERS - УТИЛИТЫ =============
from handlers.medicine_handler import hp_command, handle_hp_callback
from handlers.stats_commands import channelstats_command, fullstats_command, resetmsgcount_command, chatinfo_command
from handlers.help_commands import trix_command, handle_trix_callback
from handlers.social_handler import social_command, giveaway_command
from handlers.bonus_handler import bonus_command

# ============= HANDLERS - РОЗЫГРЫШИ =============
from handlers.giveaway_handler import (
    giveaway_command, handle_giveaway_callback, p2p_command
)
from handlers.trixticket_handler import (
    tickets_command, myticket_command, trixtickets_command,
    handle_trixticket_callback, givett_command, removett_command,
    userstt_command, trixticketstart_command, ttrenumber_command,
    ttsave_command, trixticketclear_command
)

# ============= SERVICES =============
from services.autopost_service import autopost_service
from services.admin_notifications import admin_notifications
from services.stats_scheduler import stats_scheduler
from services.channel_stats import channel_stats
from services.db import db
from services.catalog_service import catalog_service

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def init_db_tables():
    """Initialize database tables with better error handling"""
    try:
        logger.info("🔄 Initializing database tables...")
        
        db_url = Config.DATABASE_URL
        
        if not db_url:
            logger.error("❌ DATABASE_URL not configured")
            return False
        
        logger.info(f"📊 Using database: {db_url[:50]}...")
        
        from models import Base, User, Post
        
        try:
            await db.init()
        except Exception as db_init_error:
            logger.error(f"⚠️  First init attempt failed: {db_init_error}")
            logger.warning("💡 Retrying with connection timeout...")
            
            try:
                await asyncio.sleep(2)
                await db.init()
            except Exception as retry_error:
                logger.error(f"❌ Database initialization failed after retry: {retry_error}")
                logger.warning("⚠️  Bot will run in LIMITED MODE without database")
                return False
        
        if db.engine is None or db.session_maker is None:
            logger.error("❌ Database engine not created")
            return False
        
        logger.info("✅ Database engine initialized")
        
        try:
            async with db.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created")
        except Exception as create_error:
            logger.error(f"❌ Failed to create tables: {create_error}")
            return False
        
        try:
            async with db.get_session() as session:
                from sqlalchemy import text
                
                if 'postgres' in db_url:
                    result = await session.execute(
                        text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
                    )
                else:
                    result = await session.execute(
                        text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                    )
                
                table_count = result.scalar()
                logger.info(f"✅ Database tables verified: {table_count} tables found")
                
                if table_count == 0:
                    logger.error("❌ No tables found in database!")
                    return False
            
            logger.info("✅ Database ready")
            return True
            
        except Exception as verify_error:
            logger.warning(f"⚠️  Could not verify tables: {verify_error}")
            logger.warning("   Continuing anyway...")
            return True
            
    except Exception as e:
        logger.error(f"❌ Database error: {e}", exc_info=True)
        logger.warning("⚠️  Bot will run in LIMITED MODE")
        return False

def ignore_budapest_chat_commands(func):
    """Decorator to ignore commands from Budapest chat"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if chat_id == Config.BUDAPEST_CHAT_ID:
            if update.message and update.message.text and update.message.text.startswith('/'):
                try:
                    await update.message.delete()
                    logger.info(f"Ignored command {func.__name__} from Budapest chat")
                except Exception as e:
                    logger.error(f"Could not delete message: {e}")
                return
        
        return await func(update, context)
    
    return wrapper

# Wrap all commands with Budapest chat filter
start_command = ignore_budapest_chat_commands(start_command)
trix_command = ignore_budapest_chat_commands(trix_command)
id_command = ignore_budapest_chat_commands(id_command)
hp_command = ignore_budapest_chat_commands(hp_command)
participants_command = ignore_budapest_chat_commands(participants_command)
report_command = ignore_budapest_chat_commands(report_command)
admin_command = ignore_budapest_chat_commands(admin_command)
say_command = ignore_budapest_chat_commands(say_command)
broadcast_command = ignore_budapest_chat_commands(broadcast_command)
sendstats_command = ignore_budapest_chat_commands(sendstats_command)
channelstats_command = ignore_budapest_chat_commands(channelstats_command)
fullstats_command = ignore_budapest_chat_commands(fullstats_command)
resetmsgcount_command = ignore_budapest_chat_commands(resetmsgcount_command)
chatinfo_command = ignore_budapest_chat_commands(chatinfo_command)
trixlinks_command = ignore_budapest_chat_commands(trixlinks_command)
social_command = ignore_budapest_chat_commands(social_command)
giveaway_command = ignore_budapest_chat_commands(giveaway_command)
bonus_command = ignore_budapest_chat_commands(bonus_command)
p2p_command = ignore_budapest_chat_commands(p2p_command)
tickets_command = ignore_budapest_chat_commands(tickets_command)
myticket_command = ignore_budapest_chat_commands(myticket_command)
trixtickets_command = ignore_budapest_chat_commands(trixtickets_command)

# Rating commands
itsme_command = ignore_budapest_chat_commands(itsme_command)
toppeople_command = ignore_budapest_chat_commands(toppeople_command)
topboys_command = ignore_budapest_chat_commands(topboys_command)
topgirls_command = ignore_budapest_chat_commands(topgirls_command)
toppeoplereset_command = ignore_budapest_chat_commands(toppeoplereset_command)

# Moderation commands
ban_command = ignore_budapest_chat_commands(ban_command)
unban_command = ignore_budapest_chat_commands(unban_command)
mute_command = ignore_budapest_chat_commands(mute_command)
unmute_command = ignore_budapest_chat_commands(unmute_command)
banlist_command = ignore_budapest_chat_commands(banlist_command)
stats_command = ignore_budapest_chat_commands(stats_command)
top_command = ignore_budapest_chat_commands(top_command)
lastseen_command = ignore_budapest_chat_commands(lastseen_command)
del_command = ignore_budapest_chat_commands(del_command)
purge_command = ignore_budapest_chat_commands(purge_command)
slowmode_command = ignore_budapest_chat_commands(slowmode_command)
noslowmode_command = ignore_budapest_chat_commands(noslowmode_command)
lockdown_command = ignore_budapest_chat_commands(lockdown_command)
antiinvite_command = ignore_budapest_chat_commands(antiinvite_command)
tagall_command = ignore_budapest_chat_commands(tagall_command)
admins_command = ignore_budapest_chat_commands(admins_command)
autopost_command = ignore_budapest_chat_commands(autopost_command)
autopost_test_command = ignore_budapest_chat_commands(autopost_test_command)

# Game commands
wordadd_command = ignore_budapest_chat_commands(wordadd_command)
wordedit_command = ignore_budapest_chat_commands(wordedit_command)
wordclear_command = ignore_budapest_chat_commands(wordclear_command)
wordon_command = ignore_budapest_chat_commands(wordon_command)
wordoff_command = ignore_budapest_chat_commands(wordoff_command)
wordinfo_command = ignore_budapest_chat_commands(wordinfo_command)
wordinfoedit_command = ignore_budapest_chat_commands(wordinfoedit_command)
anstimeset_command = ignore_budapest_chat_commands(anstimeset_command)
gamesinfo_command = ignore_budapest_chat_commands(gamesinfo_command)
admgamesinfo_command = ignore_budapest_chat_commands(admgamesinfo_command)
game_say_command = ignore_budapest_chat_commands(game_say_command)
roll_participant_command = ignore_budapest_chat_commands(roll_participant_command)
roll_draw_command = ignore_budapest_chat_commands(roll_draw_command)
rollreset_command = ignore_budapest_chat_commands(rollreset_command)
rollstatus_command = ignore_budapest_chat_commands(rollstatus_command)
mynumber_command = ignore_budapest_chat_commands(mynumber_command)

# TrixTicket admin commands
givett_command = ignore_budapest_chat_commands(givett_command)
removett_command = ignore_budapest_chat_commands(removett_command)
userstt_command = ignore_budapest_chat_commands(userstt_command)
trixticketstart_command = ignore_budapest_chat_commands(trixticketstart_command)
ttrenumber_command = ignore_budapest_chat_commands(ttrenumber_command)
ttsave_command = ignore_budapest_chat_commands(ttsave_command)
trixticketclear_command = ignore_budapest_chat_commands(trixticketclear_command)

# Catalog commands
catalog_command = ignore_budapest_chat_commands(catalog_command)
search_command = ignore_budapest_chat_commands(search_command)
addtocatalog_command = ignore_budapest_chat_commands(addtocatalog_command)
review_command = ignore_budapest_chat_commands(review_command)
categoryfollow_command = ignore_budapest_chat_commands(categoryfollow_command)
catalogpriority_command = ignore_budapest_chat_commands(catalogpriority_command)
addcatalogreklama_command = ignore_budapest_chat_commands(addcatalogreklama_command)
catalogviews_command = ignore_budapest_chat_commands(catalogviews_command)
catalogview_command = ignore_budapest_chat_commands(catalogview_command)
catalog_stats_users_command = ignore_budapest_chat_commands(catalog_stats_users_command)
catalog_stats_categories_command = ignore_budapest_chat_commands(catalog_stats_categories_command)
catalog_stats_popular_command = ignore_budapest_chat_commands(catalog_stats_popular_command)
catalog_stats_priority_command = ignore_budapest_chat_commands(catalog_stats_priority_command)
catalog_stats_reklama_command = ignore_budapest_chat_commands(catalog_stats_reklama_command)
edit_catalog_command = ignore_budapest_chat_commands(edit_catalog_command)
remove_catalog_command = ignore_budapest_chat_commands(remove_catalog_command)
change_catalog_number_command = ignore_budapest_chat_commands(change_catalog_number_command)
addgirltocat_command = ignore_budapest_chat_commands(addgirltocat_command)
addboytocat_command = ignore_budapest_chat_commands(addboytocat_command)
admincataloginfo_command = ignore_budapest_chat_commands(admincataloginfo_command)
catalogads_command = ignore_budapest_chat_commands(catalogads_command)
removeads_command = ignore_budapest_chat_commands(removeads_command)

async def handle_all_callbacks(update: Update, context):
    """Router for all callback queries"""
    query = update.callback_query
    
    if not query or not query.data:
        return
    
    # Ignore callbacks from Budapest chat
    if query.message and query.message.chat.id == Config.BUDAPEST_CHAT_ID:
        await query.answer("⚠️ Бот не работает в этом чате", show_alert=True)
        logger.info(f"Ignored callback from Budapest chat: {query.data}")
        return
    
    data_parts = query.data.split(":")
    handler_type = data_parts[0] if data_parts else None
    
    logger.info(f"Callback: {query.data} from user {update.effective_user.id}")
    
    try:
        if handler_type == "menu":
            await handle_menu_callback(update, context)
        elif handler_type == "pub":
            await handle_publication_callback(update, context)
        elif handler_type == "piar":
            await handle_piar_callback(update, context)
        elif handler_type == "mod":
            await handle_moderation_callback(update, context)
        elif handler_type == "admin":
            await handle_admin_callback(update, context)
        elif handler_type == "profile":
            await handle_profile_callback(update, context)
        elif handler_type == "game":
            await handle_game_callback(update, context)
        elif handler_type == "hp":
            await handle_hp_callback(update, context)
        elif handler_type == "trix":
            await handle_trix_callback(update, context)
        elif handler_type == "giveaway":
            await handle_giveaway_callback(update, context)
        elif handler_type == "tt":
            await handle_trixticket_callback(update, context)
        elif handler_type == "rate":
            await handle_rate_callback(update, context)
        elif handler_type == "rate_mod":
            await handle_rate_moderation_callback(update, context)
        elif handler_type == "catalog":
            await handle_catalog_callback(update, context)
        else:
            await query.answer("⚠️ Неизвестная команда", show_alert=True)
    except Exception as e:
        logger.error(f"Error handling callback: {e}", exc_info=True)
        try:
            await query.answer("❌ Ошибка", show_alert=True)
        except:
            pass

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message handler - ВЕРСИЯ 5.0 С ПРАВИЛЬНЫМ ПРИОРИТЕТОМ"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # ✅ КРИТИЧНО: Проверяем сначала mod_waiting_for для модерации
    if context.user_data.get('mod_waiting_for'):
        logger.info(f"[MODERATION] User {user_id} waiting_for: {context.user_data.get('mod_waiting_for')}")
        await handle_moderation_text(update, context)
        return
    
    # Ignore all from Budapest chat EXCEPT message counting
    if chat_id == Config.BUDAPEST_CHAT_ID:
        channel_stats.increment_message_count(chat_id)
        return
    
    # Count messages in tracked chats
    if chat_id in Config.STATS_CHANNELS.values():
        channel_stats.increment_message_count(chat_id)
    
    waiting_for = context.user_data.get('waiting_for')
    
    try:
        # ============= ПРИОРИТЕТ 1: RATING HANDLERS (САМЫЙ ВЫСОКИЙ!) =============
        # КРИТИЧНО: Проверяем rating ПЕРЕД всеми остальными медиа-обработчиками
        # Иначе catalog перехватит фото для /itsme
        
        if waiting_for == 'rate_photo':
            logger.info(f"[RATING] Processing photo for user {user_id}")
            await handle_rate_photo(update, context)
            return
        
        if waiting_for == 'rate_name':
            logger.info(f"[RATING] Processing name for user {user_id}")
            await handle_rate_name(update, context)
            return
        
        if waiting_for == 'rate_age':
            logger.info(f"[RATING] Processing age for user {user_id}")
            await handle_rate_age(update, context)
            return
        
        if waiting_for == 'rate_about':
            logger.info(f"[RATING] Processing about for user {user_id}")
            await handle_rate_about(update, context)
            return
        
        if waiting_for == 'rate_profile':
            logger.info(f"[RATING] Processing profile for user {user_id}")
            await handle_rate_profile(update, context)
            return
        
        # ============= ПРИОРИТЕТ 2: GAME HANDLERS =============
        if await handle_game_text_input(update, context):
            logger.info(f"[GAME] Text processed for user {user_id}")
            return
        
        if await handle_game_media_input(update, context):
            logger.info(f"[GAME] Media processed for user {user_id}")
            return
        
        # ============= ПРИОРИТЕТ 3: PIAR HANDLERS =============
        if waiting_for and waiting_for.startswith('piar_'):
            if update.message.photo or update.message.video:
                logger.info(f"[PIAR] Processing photo for user {user_id}")
                await handle_piar_photo(update, context)
            else:
                field = waiting_for.replace('piar_', '')
                text = update.message.text or update.message.caption
                logger.info(f"[PIAR] Processing text field '{field}' for user {user_id}")
                await handle_piar_text(update, context, field, text)
            return
        
        # ============= ПРИОРИТЕТ 4: CATALOG HANDLERS =============
        # Проверяем медиа для каталога (ТОЛЬКО если есть активная сессия каталога)
        if (update.message.photo or update.message.video or 
            update.message.animation or update.message.document):
            
            # Проверяем есть ли активная сессия добавления в каталог
            if 'catalog_add' in context.user_data and context.user_data['catalog_add'].get('step') == 'media':
                logger.info(f"[CATALOG] Processing media for user {user_id}")
                if await handle_catalog_media(update, context):
                    return
        
        # Каталог text handler
        if ('catalog_add' in context.user_data or 
            'catalog_review' in context.user_data or
            'catalog_priority' in context.user_data or
            'catalog_ad' in context.user_data or
            'catalog_search' in context.user_data):
            logger.info(f"[CATALOG] Processing text for user {user_id}")
            await handle_catalog_text(update, context)
            return
        
        # ============= ПРИОРИТЕТ 5: PUBLICATION HANDLERS =============
        # Media for posts
        if update.message.photo or update.message.video or update.message.document:
            logger.info(f"[PUBLICATION] Processing media for user {user_id}")
            await handle_media_input(update, context)
            return
        
        # Text for posts
        if waiting_for == 'post_text' or context.user_data.get('post_data'):
            logger.info(f"[PUBLICATION] Processing text for user {user_id}")
            await handle_text_input(update, context)
            return
        
    except Exception as e:
        logger.error(f"Error handling message from user {user_id}: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка")

async def error_handler(update: object, context):
    """Error handler"""
    logger.error(f"Error: {context.error}", exc_info=context.error)
    
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("❌ Произошла ошибка")
        except:
            pass

def main():
    """Main function"""
    if not Config.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found!")
        return
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    logger.info("🚀 Starting TrixBot v5.0...")
    print("🚀 Starting TrixBot v5.0...")
    print(f"📊 Database: {Config.DATABASE_URL[:30]}...")
    print(f"🚫 Budapest chat: {Config.BUDAPEST_CHAT_ID}")
    
    # Initialize DB
    db_initialized = loop.run_until_complete(init_db_tables())
    
    if not db_initialized:
        logger.warning("⚠️ Bot starting without database")
        print("⚠️ Database not available")
    else:
        print("✅ Database connected")
    
    # Create application
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Setup services
    autopost_service.set_bot(application.bot)
    admin_notifications.set_bot(application.bot)
    channel_stats.set_bot(application.bot)
    stats_scheduler.set_admin_notifications(admin_notifications)
    
    logger.info("✅ Services initialized")
    
    # ============= REGISTER HANDLERS =============
    
    # Start and basic commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("trix", trix_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("hp", hp_command))
    application.add_handler(CommandHandler("social", social_command))
    application.add_handler(CommandHandler("giveaway", giveaway_command))
    application.add_handler(CommandHandler("bonus", bonus_command))
    application.add_handler(CommandHandler("p2p", p2p_command))
    application.add_handler(CommandHandler("trixlinks", trixlinks_command))
    application.add_handler(CommandHandler("participants", participants_command))
    application.add_handler(CommandHandler("report", report_command))
    
    # TrixTicket commands - User
    application.add_handler(CommandHandler("tickets", tickets_command))
    application.add_handler(CommandHandler("mytt", myticket_command))
    application.add_handler(CommandHandler("trixtickets", trixtickets_command))
    
    # Admin commands
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("say", say_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("sendstats", sendstats_command))
    
    # Rating commands (TopPeople)
    application.add_handler(CommandHandler("itsme", itsme_command))
    application.add_handler(CommandHandler("toppeople", toppeople_command))
    application.add_handler(CommandHandler("topboys", topboys_command))
    application.add_handler(CommandHandler("topgirls", topgirls_command))
    application.add_handler(CommandHandler("toppeoplereset", toppeoplereset_command))
    
    # Catalog commands - User
    application.add_handler(CommandHandler("catalog", catalog_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("addtocatalog", addtocatalog_command))
    application.add_handler(CommandHandler("review", review_command))
    application.add_handler(CommandHandler("categoryfollow", categoryfollow_command))
    
    # Catalog commands - Admin
    application.add_handler(CommandHandler("catalogpriority", catalogpriority_command))
    application.add_handler(CommandHandler("addcatalogreklama", addcatalogreklama_command))
    application.add_handler(CommandHandler("catalogviews", catalogviews_command))
    application.add_handler(CommandHandler("catalogview", catalogview_command))
    application.add_handler(CommandHandler("catalog_stats_users", catalog_stats_users_command))
    application.add_handler(CommandHandler("catalog_stats_categories", catalog_stats_categories_command))
    application.add_handler(CommandHandler("catalog_stats_popular", catalog_stats_popular_command))
    application.add_handler(CommandHandler("catalog_stats_priority", catalog_stats_priority_command))
    application.add_handler(CommandHandler("catalog_stats_reklama", catalog_stats_reklama_command))
    application.add_handler(CommandHandler("catalogedit", edit_catalog_command))
    application.add_handler(CommandHandler("remove", remove_catalog_command))
    application.add_handler(CommandHandler("changenumber", change_catalog_number_command))
    application.add_handler(CommandHandler("addgirltocat", addgirltocat_command))
    application.add_handler(CommandHandler("addboytocat", addboytocat_command))
    application.add_handler(CommandHandler("admincataloginfo", admincataloginfo_command))
    application.add_handler(CommandHandler("catalogads", catalogads_command))
    application.add_handler(CommandHandler("removeads", removeads_command))
    
    # Stats commands
    application.add_handler(CommandHandler("channelstats", channelstats_command))
    application.add_handler(CommandHandler("fullstats", fullstats_command))
    application.add_handler(CommandHandler("resetmsgcount", resetmsgcount_command))
    application.add_handler(CommandHandler("chatinfo", chatinfo_command))
    
    # Moderation commands
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("mute", mute_command))
    application.add_handler(CommandHandler("unmute", unmute_command))
    application.add_handler(CommandHandler("banlist", banlist_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("top", top_command))
    application.add_handler(CommandHandler("lastseen", lastseen_command))
    
    # Advanced moderation
    application.add_handler(CommandHandler("del", del_command))
    application.add_handler(CommandHandler("purge", purge_command))
    application.add_handler(CommandHandler("slowmode", slowmode_command))
    application.add_handler(CommandHandler("noslowmode", noslowmode_command))
    application.add_handler(CommandHandler("lockdown", lockdown_command))
    application.add_handler(CommandHandler("antiinvite", antiinvite_command))
    application.add_handler(CommandHandler("tagall", tagall_command))
    application.add_handler(CommandHandler("admins", admins_command))
    
    # Autopost
    application.add_handler(CommandHandler("autopost", autopost_command))
    application.add_handler(CommandHandler("autoposttest", autopost_test_command))
    
    # Game commands for all versions
    for version in ['need', 'try', 'more']:
        application.add_handler(CommandHandler(f"{version}add", wordadd_command))
        application.add_handler(CommandHandler(f"{version}edit", wordedit_command))
        application.add_handler(CommandHandler(f"{version}start", wordon_command))
        application.add_handler(CommandHandler(f"{version}stop", wordoff_command))
        application.add_handler(CommandHandler(f"{version}info", wordinfo_command))
        application.add_handler(CommandHandler(f"{version}infoedit", wordinfoedit_command))
        application.add_handler(CommandHandler(f"{version}timeset", anstimeset_command))
        application.add_handler(CommandHandler(f"{version}game", gamesinfo_command))
        application.add_handler(CommandHandler(f"{version}guide", admgamesinfo_command))
        application.add_handler(CommandHandler(f"{version}slovo", game_say_command))
        application.add_handler(CommandHandler(f"{version}roll", roll_participant_command))
        application.add_handler(CommandHandler(f"{version}rollstart", roll_draw_command))
        application.add_handler(CommandHandler(f"{version}reroll", rollreset_command))
        application.add_handler(CommandHandler(f"{version}rollstat", rollstatus_command))
        application.add_handler(CommandHandler(f"{version}myroll", mynumber_command))
    
    application.add_handler(CommandHandler("add", wordadd_command))
    application.add_handler(CommandHandler("edit", wordedit_command))
    application.add_handler(CommandHandler("wordclear", wordclear_command))
    
    # TrixTicket admin commands
    application.add_handler(CommandHandler("givett", givett_command))
    application.add_handler(CommandHandler("removett", removett_command))
    application.add_handler(CommandHandler("userstt", userstt_command))
    application.add_handler(CommandHandler("trixticketstart", trixticketstart_command))
    application.add_handler(CommandHandler("ttrenumber", ttrenumber_command))
    application.add_handler(CommandHandler("ttsave", ttsave_command))
    application.add_handler(CommandHandler("trixticketclear", trixticketclear_command))
    
    # ✅ КРИТИЧНО: Callback handler ПЕРЕД message handler
    application.add_handler(CallbackQueryHandler(handle_all_callbacks))
    
    # ✅ КРИТИЧНО: Message handler ПОСЛЕ callback handler
    application.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL,
        handle_messages
    ))
    
    application.add_error_handler(error_handler)
    
    # Start services
    if Config.SCHEDULER_ENABLED:
        loop.create_task(autopost_service.start())
        print("✅ Autopost enabled")
    
    loop.create_task(stats_scheduler.start())
    print("✅ Stats scheduler enabled")
    
    logger.info("🤖 TrixBot v5.0 starting...")
    print("\n" + "="*50)
    print("🤖 TRIXBOT v5.0 IS READY!")
    print("="*50)
    print(f"📊 Stats interval: {Config.STATS_INTERVAL_HOURS}h")
    print(f"📢 Moderation: {Config.MODERATION_GROUP_ID}")
    print(f"🔧 Admin group: {Config.ADMIN_GROUP_ID}")
    print(f"🚫 Budapest chat (IGNORE): {Config.BUDAPEST_CHAT_ID}")
    print(f"⏰ Cooldown: {Config.COOLDOWN_SECONDS // 3600}h")
    print(f"📸 Catalog v5.0: ✅ With media & TopPeople")
    print(f"⭐ Rating v5.0: ✅ /itsme with 6 steps")
    
    if db_initialized:
        print(f"💾 Database: ✅ Connected")
    else:
        print(f"💾 Database: ⚠️ Limited mode")
    
    print("="*50 + "\n")
    
    try:
        application.run_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt")
        print("\n🛑 Stopping bot...")
    except Exception as e:
        logger.error(f"Error in main loop: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
    finally:
        print("🔄 Cleaning up...")
        
        try:
            loop.run_until_complete(stats_scheduler.stop())
            loop.run_until_complete(autopost_service.stop())
            loop.run_until_complete(db.close())
            print("✅ Cleanup complete")
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")
        
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
            print("✅ Event loop closed")
        except Exception as loop_error:
            logger.error(f"Error closing loop: {loop_error}")
        
        print("\n👋 TrixBot v5.0 stopped")

if __name__ == '__main__':
    main()
