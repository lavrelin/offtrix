# -*- coding: utf-8 -*-
"""
TrixBot Main - ВЕРСИЯ 5.2.1 FIXED
Исправлен BudapestChatFilter для совместимости с python-telegram-bot
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
from handlers.start_handler import start_command, help_command
from handlers.menu_handler import handle_menu_callback
from handlers.publication_handler import (
    handle_publication_callback, 
    handle_text_input, 
    handle_media_input
)
from handlers.piar_handler import (
    handle_piar_callback, 
    handle_piar_text, 
    handle_piar_photo
)
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
from handlers.admin_handler import (
    admin_command,
    say_command,
    handle_admin_callback,
    broadcast_command,
    sendstats_command
)

# ============= HANDLERS - RATING, CATALOG, GAMES, GIVEAWAY =============
from handlers.rating_handler import (
    itsme_command, toppeople_command, topboys_command, topgirls_command,
    toppeoplereset_command, handle_rate_callback, handle_rate_moderation_callback,
    handle_rate_photo, handle_rate_age, handle_rate_name, handle_rate_about, handle_rate_profile
)
from handlers.catalog_handler import (
    catalog_command, search_command, addtocatalog_command, review_command,
    categoryfollow_command, addgirltocat_command, addboytocat_command,
    handle_catalog_callback, handle_catalog_text, handle_catalog_media
)
from handlers.games_handler import (
    wordadd_command, wordedit_command, wordclear_command,
    wordon_command, wordoff_command, wordinfo_command,
    wordinfoedit_command, anstimeset_command,
    gamesinfo_command, admgamesinfo_command, game_say_command,
    roll_participant_command, roll_draw_command,
    rollreset_command, rollstatus_command, mynumber_command,
    handle_game_text_input, handle_game_media_input, handle_game_callback
)
from handlers.giveaway_handler import (
    giveaway_command, handle_giveaway_callback, p2p_command
)

# ============= HANDLERS - ОСТАЛЬНЫЕ =============
from handlers.basic_handler import id_command, participants_command, report_command
from handlers.link_handler import trixlinks_command
from handlers.advanced_moderation import (
    del_command, purge_command, slowmode_command, noslowmode_command,
    lockdown_command, antiinvite_command, tagall_command, admins_command
)
from handlers.autopost_handler import autopost_command, autopost_test_command
from handlers.medicine_handler import hp_command, handle_hp_callback
from handlers.stats_commands import channelstats_command, fullstats_command, resetmsgcount_command, chatinfo_command
from handlers.social_handler import social_command
from handlers.bonus_handler import bonus_command
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

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============= BUDAPEST CHAT FILTER - ИСПРАВЛЕННЫЙ =============
class BudapestChatFilter(filters.MessageFilter):
    """
    Фильтр для автоматического игнорирования команд из Budapest чата.
    Совместим с python-telegram-bot filters system.
    """
    def __init__(self):
        self.budapest_chat_id = Config.BUDAPEST_CHAT_ID
        super().__init__()
    
    def filter(self, message) -> bool:
        """Возвращает True если сообщение НЕ из Budapest чата"""
        if not message or not message.chat:
            return True
        return message.chat.id != self.budapest_chat_id

# Создаем экземпляр фильтра
budapest_filter = BudapestChatFilter()

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

async def handle_all_callbacks(update: Update, context):
    """Router for all callback queries - OPTIMIZED v5.2"""
    query = update.callback_query
    
    if not query or not query.data:
        return
    
    # Ignore Budapest chat
    if query.message and query.message.chat.id == Config.BUDAPEST_CHAT_ID:
        await query.answer("⚠️ Бот не работает в этом чате", show_alert=True)
        return
    
    data = query.data
    logger.info(f"Callback: {data} from user {update.effective_user.id}")
    
    try:
        # ============= OPTIMIZED HANDLERS - Route by prefix =============
        if data.startswith('mnc_'):
            await handle_menu_callback(update, context)
        elif data.startswith('pbc_'):
            await handle_publication_callback(update, context)
        elif data.startswith('mdc_'):
            await handle_moderation_callback(update, context)
        elif data.startswith('adc_'):
            await handle_admin_callback(update, context)
        elif data.startswith('prc_'):
            await handle_piar_callback(update, context)
        elif data.startswith('ctc_'):
            # NEW: Catalog callbacks
            await handle_catalog_callback(update, context)
        elif data.startswith('gmc_'):
            # NEW: Game callbacks
            await handle_game_callback(update, context)
        elif data.startswith('gwc_'):
            # NEW: Giveaway callbacks
            await handle_giveaway_callback(update, context)
        elif data.startswith('rtc_'):
            # NEW: Rating callbacks
            await handle_rate_callback(update, context)
        elif data.startswith('rmc_'):
            # NEW: Rating moderation callbacks
            await handle_rate_moderation_callback(update, context)
        elif data.startswith('ttc_'):
            # TrixTicket callbacks
            await handle_trixticket_callback(update, context)
        elif data.startswith('hpc_'):
            # HP callbacks
            await handle_hp_callback(update, context)
        
        # ============= BACKWARD COMPATIBILITY - Old format support =============
        elif ":" in data:
            handler_type = data.split(":")[0]
            
            handler_map = {
                'menu': handle_menu_callback,
                'pub': handle_publication_callback,
                'piar': handle_piar_callback,
                'mod': handle_moderation_callback,
                'admin': handle_admin_callback,
                'catalog': handle_catalog_callback,
                'game': handle_game_callback,
                'giveaway': handle_giveaway_callback,
                'rate': handle_rate_callback,
                'rate_mod': handle_rate_moderation_callback,
                'tt': handle_trixticket_callback,
                'hp': handle_hp_callback,
            }
            
            handler = handler_map.get(handler_type)
            if handler:
                logger.warning(f"Old callback format: {data}")
                await handler(update, context)
            else:
                await query.answer("⚠️ Неизвестная команда", show_alert=True)
        else:
            await query.answer("⚠️ Неизвестная команда", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error handling callback: {e}", exc_info=True)
        try:
            await query.answer("❌ Ошибка", show_alert=True)
        except:
            pass

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message handler - v5.2 OPTIMIZED"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # ✅ КРИТИЧНО: Moderation FIRST
    if context.user_data.get('mod_waiting_for'):
        await handle_moderation_text(update, context)
        return
    
    # Ignore Budapest chat
    if chat_id == Config.BUDAPEST_CHAT_ID:
        channel_stats.increment_message_count(chat_id)
        return
    
    # Count messages
    if chat_id in Config.STATS_CHANNELS.values():
        channel_stats.increment_message_count(chat_id)
    
    waiting_for = context.user_data.get('waiting_for')
    
    try:
        # ПРИОРИТЕТ 1: RATING HANDLERS
        if waiting_for in ['rate_photo', 'rate_name', 'rate_age', 'rate_about', 'rate_profile']:
            handlers = {
                'rate_photo': handle_rate_photo,
                'rate_name': handle_rate_name,
                'rate_age': handle_rate_age,
                'rate_about': handle_rate_about,
                'rate_profile': handle_rate_profile,
            }
            await handlers[waiting_for](update, context)
            return
        
        # ПРИОРИТЕТ 2: GAME HANDLERS
        if await handle_game_text_input(update, context):
            return
        if await handle_game_media_input(update, context):
            return
        
        # ПРИОРИТЕТ 3: PIAR HANDLERS
        if waiting_for and waiting_for.startswith('piar_'):
            if update.message.photo or update.message.video:
                await handle_piar_photo(update, context)
            else:
                field = waiting_for.replace('piar_', '')
                text = update.message.text or update.message.caption
                await handle_piar_text(update, context, field, text)
            return
        
        # ПРИОРИТЕТ 4: CATALOG HANDLERS
        if (update.message.photo or update.message.video or 
            update.message.animation or update.message.document):
            if 'catalog_add' in context.user_data and context.user_data['catalog_add'].get('step') == 'media':
                if await handle_catalog_media(update, context):
                    return
        
        if any(key in context.user_data for key in ['catalog_add', 'catalog_review', 'catalog_priority', 'catalog_ad', 'catalog_search']):
            await handle_catalog_text(update, context)
            return
        
        # ПРИОРИТЕТ 5: PUBLICATION HANDLERS
        if update.message.photo or update.message.video or update.message.document:
            await handle_media_input(update, context)
            return
        
        if waiting_for == 'post_text' or context.user_data.get('post_data'):
            await handle_text_input(update, context)
            return
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await update.message.reply_text("❌ Ошибка")

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
    
    logger.info("🚀 Starting TrixBot v5.2.1 FIXED...")
    print("🚀 Starting TrixBot v5.2.1 FIXED...")
    print(f"📊 Database: {Config.DATABASE_URL[:30]}...")
    print(f"🚫 Budapest chat: {Config.BUDAPEST_CHAT_ID}")
    print("⚡ Fixed: BudapestChatFilter compatibility")
    
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
    
    # ============= REGISTER HANDLERS WITH BUDAPEST FILTER =============
    
    # Start and basic commands
    application.add_handler(CommandHandler("start", start_command, filters=budapest_filter))
    application.add_handler(CommandHandler("help", help_command, filters=budapest_filter))
    application.add_handler(CommandHandler("id", id_command, filters=budapest_filter))
    application.add_handler(CommandHandler("hp", hp_command, filters=budapest_filter))
    application.add_handler(CommandHandler("social", social_command, filters=budapest_filter))
    application.add_handler(CommandHandler("giveaway", giveaway_command, filters=budapest_filter))
    application.add_handler(CommandHandler("bonus", bonus_command, filters=budapest_filter))
    application.add_handler(CommandHandler("p2p", p2p_command, filters=budapest_filter))
    application.add_handler(CommandHandler("trixlinks", trixlinks_command, filters=budapest_filter))
    application.add_handler(CommandHandler("participants", participants_command, filters=budapest_filter))
    application.add_handler(CommandHandler("report", report_command, filters=budapest_filter))
    
    # TrixTicket commands - User
    application.add_handler(CommandHandler("tickets", tickets_command, filters=budapest_filter))
    application.add_handler(CommandHandler("mytt", myticket_command, filters=budapest_filter))
    application.add_handler(CommandHandler("trixtickets", trixtickets_command, filters=budapest_filter))
    
    # Admin commands
    application.add_handler(CommandHandler("admin", admin_command, filters=budapest_filter))
    application.add_handler(CommandHandler("say", say_command, filters=budapest_filter))
    application.add_handler(CommandHandler("broadcast", broadcast_command, filters=budapest_filter))
    application.add_handler(CommandHandler("sendstats", sendstats_command, filters=budapest_filter))
    
    # Rating commands (TopPeople)
    application.add_handler(CommandHandler("itsme", itsme_command, filters=budapest_filter))
    application.add_handler(CommandHandler("toppeople", toppeople_command, filters=budapest_filter))
    application.add_handler(CommandHandler("topboys", topboys_command, filters=budapest_filter))
    application.add_handler(CommandHandler("topgirls", topgirls_command, filters=budapest_filter))
    application.add_handler(CommandHandler("toppeoplereset", toppeoplereset_command, filters=budapest_filter))
    
    # Catalog commands - User
    application.add_handler(CommandHandler("search", search_command, filters=budapest_filter))
    application.add_handler(CommandHandler("addtocatalog", addtocatalog_command, filters=budapest_filter))
    application.add_handler(CommandHandler("review", review_command, filters=budapest_filter))
    application.add_handler(CommandHandler("categoryfollow", categoryfollow_command, filters=budapest_filter))
    
    # Catalog commands - Admin
    application.add_handler(CommandHandler("catalog", catalog_command, filters=budapest_filter))
    application.add_handler(CommandHandler("addgirltocat", addgirltocat_command, filters=budapest_filter))
    application.add_handler(CommandHandler("addboytocat", addboytocat_command, filters=budapest_filter))
    
    # Stats commands
    application.add_handler(CommandHandler("channelstats", channelstats_command, filters=budapest_filter))
    application.add_handler(CommandHandler("fullstats", fullstats_command, filters=budapest_filter))
    application.add_handler(CommandHandler("resetmsgcount", resetmsgcount_command, filters=budapest_filter))
    application.add_handler(CommandHandler("chatinfo", chatinfo_command, filters=budapest_filter))
    
    # Moderation commands
    application.add_handler(CommandHandler("ban", ban_command, filters=budapest_filter))
    application.add_handler(CommandHandler("unban", unban_command, filters=budapest_filter))
    application.add_handler(CommandHandler("mute", mute_command, filters=budapest_filter))
    application.add_handler(CommandHandler("unmute", unmute_command, filters=budapest_filter))
    application.add_handler(CommandHandler("banlist", banlist_command, filters=budapest_filter))
    application.add_handler(CommandHandler("stats", stats_command, filters=budapest_filter))
    application.add_handler(CommandHandler("top", top_command, filters=budapest_filter))
    application.add_handler(CommandHandler("lastseen", lastseen_command, filters=budapest_filter))
    
    # Advanced moderation
    application.add_handler(CommandHandler("del", del_command, filters=budapest_filter))
    application.add_handler(CommandHandler("purge", purge_command, filters=budapest_filter))
    application.add_handler(CommandHandler("slowmode", slowmode_command, filters=budapest_filter))
    application.add_handler(CommandHandler("noslowmode", noslowmode_command, filters=budapest_filter))
    application.add_handler(CommandHandler("lockdown", lockdown_command, filters=budapest_filter))
    application.add_handler(CommandHandler("antiinvite", antiinvite_command, filters=budapest_filter))
    application.add_handler(CommandHandler("tagall", tagall_command, filters=budapest_filter))
    application.add_handler(CommandHandler("admins", admins_command, filters=budapest_filter))
    
    # Autopost
    application.add_handler(CommandHandler("autopost", autopost_command, filters=budapest_filter))
    application.add_handler(CommandHandler("autoposttest", autopost_test_command, filters=budapest_filter))
    
    # Game commands for all versions
    for version in ['need', 'try', 'more']:
        application.add_handler(CommandHandler(f"{version}add", wordadd_command, filters=budapest_filter))
        application.add_handler(CommandHandler(f"{version}edit", wordedit_command, filters=budapest_filter))
        application.add_handler(CommandHandler(f"{version}start", wordon_command, filters=budapest_filter))
        application.add_handler(CommandHandler(f"{version}stop", wordoff_command, filters=budapest_filter))
        application.add_handler(CommandHandler(f"{version}info", wordinfo_command, filters=budapest_filter))
        application.add_handler(CommandHandler(f"{version}infoedit", wordinfoedit_command, filters=budapest_filter))
        application.add_handler(CommandHandler(f"{version}timeset", anstimeset_command, filters=budapest_filter))
        application.add_handler(CommandHandler(f"{version}game", gamesinfo_command, filters=budapest_filter))
        application.add_handler(CommandHandler(f"{version}guide", admgamesinfo_command, filters=budapest_filter))
        application.add_handler(CommandHandler(f"{version}slovo", game_say_command, filters=budapest_filter))
        application.add_handler(CommandHandler(f"{version}roll", roll_participant_command, filters=budapest_filter))
        application.add_handler(CommandHandler(f"{version}rollstart", roll_draw_command, filters=budapest_filter))
        application.add_handler(CommandHandler(f"{version}reroll", rollreset_command, filters=budapest_filter))
        application.add_handler(CommandHandler(f"{version}rollstat", rollstatus_command, filters=budapest_filter))
        application.add_handler(CommandHandler(f"{version}myroll", mynumber_command, filters=budapest_filter))
    
    application.add_handler(CommandHandler("add", wordadd_command, filters=budapest_filter))
    application.add_handler(CommandHandler("edit", wordedit_command, filters=budapest_filter))
    application.add_handler(CommandHandler("wordclear", wordclear_command, filters=budapest_filter))
    
    # TrixTicket admin commands
    application.add_handler(CommandHandler("givett", givett_command, filters=budapest_filter))
    application.add_handler(CommandHandler("removett", removett_command, filters=budapest_filter))
    application.add_handler(CommandHandler("userstt", userstt_command, filters=budapest_filter))
    application.add_handler(CommandHandler("trixticketstart", trixticketstart_command, filters=budapest_filter))
    application.add_handler(CommandHandler("ttrenumber", ttrenumber_command, filters=budapest_filter))
    application.add_handler(CommandHandler("ttsave", ttsave_command, filters=budapest_filter))
    application.add_handler(CommandHandler("trixticketclear", trixticketclear_command, filters=budapest_filter))
    
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
    
    logger.info("🤖 TrixBot v5.2.1 FIXED starting...")
    print("\n" + "="*50)
    print("🤖 TRIXBOT v5.2.1 FIXED IS READY!")
    print("="*50)
    print(f"⚡ Fixed: BudapestChatFilter (MessageFilter-based)")
    print(f"📋 Callback prefixes: mnc_, pbc_, mdc_, adc_, prc_, ctc_, gmc_, gwc_, rtc_, rmc_, ttc_, hpc_")
    print(f"📊 Stats interval: {Config.STATS_INTERVAL_HOURS}h")
    print(f"📢 Moderation: {Config.MODERATION_GROUP_ID}")
    print(f"🔧 Admin group: {Config.ADMIN_GROUP_ID}")
    print(f"🚫 Budapest chat (AUTO-FILTERED): {Config.BUDAPEST_CHAT_ID}")
    print(f"⏰ Cooldown: {Config.COOLDOWN_SECONDS // 3600}h")
    
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
        
        print("\n👋 TrixBot v5.2.1 FIXED stopped")

if __name__ == '__main__':
    main()
