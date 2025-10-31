import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)
from dotenv import load_dotenv
from config import Config

from handlers.start_handler import start_command
from handlers.menu_handler import handle_menu_callback
from handlers.publication_handler import (
    handle_publication_callback, handle_text_input, handle_media_input
)
from handlers.piar_handler import (
    handle_piar_callback, handle_piar_text, handle_piar_photo
)
from handlers.moderation_handler import (
    handle_moderation_callback, handle_moderation_text,
    ban_command, unban_command, mute_command, unmute_command,
    banlist_command, stats_command, top_command, lastseen_command
)
from handlers.admin_handler import (
    admin_command, talkto_command, handle_admin_callback,
    broadcast_command, sendstats_command,
    id_command, report_command, silence_command, is_user_silenced
)

from handlers.rating_handler import (
    itsme_command, toppeople_command, topboys_command, topgirls_command,
    toppeoplereset_command, handle_rate_callback, handle_rate_moderation_callback,
    handle_rate_photo, handle_rate_age, handle_rate_name, handle_rate_about, handle_rate_profile
)
from handlers.catalog_handler import (
    catalog_command, search_command, addtocatalog_command, review_command,
    categoryfollow_command, addgirltocat_command, addboytocat_command,
    remove_command, handle_catalog_callback, handle_catalog_text, handle_catalog_media
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

from handlers.info_handler import (
    social_command, bonus_command, trixlinks_command, hp_command, handle_info_callback
)
from handlers.autopost_handler import autopost_command, autopost_test_command
from handlers.trixticket_handler import (
    tickets_command, myticket_command, trixtickets_command,
    handle_trixticket_callback, givett_command, removett_command,
    userstt_command, trixticketstart_command, ttrenumber_command,
    ttsave_command, trixticketclear_command
)

from services.autopost_service import autopost_service
from services.admin_notifications import admin_notifications
from services.stats_scheduler import stats_scheduler
from services.channel_stats import channel_stats
from services.cooldown import cooldown_service
from services.db import db

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BudapestChatFilter(filters.MessageFilter):
    def __init__(self):
        self.budapest_chat_id = Config.BUDAPEST_CHAT_ID
        super().__init__()
    
    def filter(self, message) -> bool:
        if not message or not message.chat:
            return True
        return message.chat.id != self.budapest_chat_id

budapest_filter = BudapestChatFilter()

async def init_db_tables():
    try:
        logger.info("Initializing database...")
        
        db_url = Config.DATABASE_URL
        if not db_url:
            logger.error("DATABASE_URL not configured")
            return False
        
        logger.info(f"Using database: {db_url[:50]}...")
        
        from models import Base
        
        try:
            await db.init()
        except Exception as db_init_error:
            logger.error(f"Database init failed: {db_init_error}")
            logger.warning("Bot will run in LIMITED MODE")
            return False
        
        if not db.engine or not db.session_maker:
            logger.error("Database engine not created")
            return False
        
        logger.info("Database engine initialized")
        
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")
        
        logger.info("Database ready")
        return True
        
    except Exception as e:
        logger.error(f"Database error: {e}", exc_info=True)
        logger.warning("Bot will run in LIMITED MODE")
        return False

async def handle_all_callbacks(update: Update, context):
    query = update.callback_query
    
    if not query or not query.data:
        return
    
    if query.message and query.message.chat.id == Config.BUDAPEST_CHAT_ID:
        await query.answer("Бот не работает в этом чате", show_alert=True)
        return
    
    if is_user_silenced(update.effective_user.id):
        await query.answer("Вы в режиме silence", show_alert=True)
        return
    
    data = query.data
    logger.info(f"Callback: {data} from user {update.effective_user.id}")
    
    try:
        if data.startswith('mnc_'):
            await handle_menu_callback(update, context)
        elif data.startswith('pbc_'):
            await handle_publication_callback(update, context)
        elif data.startswith('mdc_'):
            await handle_moderation_callback(update, context)
        elif data.startswith('adm_'):
            await handle_admin_callback(update, context)
        elif data.startswith('prc_'):
            await handle_piar_callback(update, context)
        elif data.startswith('ctlg_'):
            await handle_catalog_callback(update, context)
        elif data.startswith('gmc_'):
            await handle_game_callback(update, context)
        elif data.startswith('gwc_'):
            await handle_giveaway_callback(update, context)
        elif data.startswith(('rtg_', 'rtgm_')):
            if data.startswith('rtgm_'):
                await handle_rate_moderation_callback(update, context)
            else:
                await handle_rate_callback(update, context)
        elif data.startswith('ttc_'):
            await handle_trixticket_callback(update, context)
        elif data.startswith('hpc_'):
            await handle_info_callback(update, context)
        else:
            logger.warning(f"Unknown callback prefix: {data[:10]}")
            await query.answer("Неизвестная команда")
    
    except Exception as e:
        logger.error(f"Callback error: {e}", exc_info=True)
        try:
            await query.answer("Произошла ошибка", show_alert=True)
        except:
            pass

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.chat.id == Config.BUDAPEST_CHAT_ID:
        return
    
    if is_user_silenced(update.effective_user.id):
        return
    
    try:
        if 'publication_state' in context.user_data:
            if update.message.photo or update.message.video or update.message.document:
                await handle_media_input(update, context)
            elif update.message.text:
                await handle_text_input(update, context)
            return
        
        if 'piar_state' in context.user_data:
            if update.message.photo:
                await handle_piar_photo(update, context)
            elif update.message.text:
                await handle_piar_text(update, context)
            return
        
        if 'rating_form' in context.user_data:
            form_data = context.user_data['rating_form']
            step = form_data.get('step')
            if update.message.photo:
                await handle_rate_photo(update, context)
            elif update.message.text:
                if step == 'age':
                    await handle_rate_age(update, context)
                elif step == 'name':
                    await handle_rate_name(update, context)
                elif step == 'about':
                    await handle_rate_about(update, context)
                elif step == 'profile':
                    await handle_rate_profile(update, context)
            return
        
        if 'catalog_add' in context.user_data or 'catalog_search' in context.user_data or 'catalog_review' in context.user_data:
            if update.message.photo or update.message.video:
                await handle_catalog_media(update, context)
            elif update.message.text:
                await handle_catalog_text(update, context)
            return
        
        if 'moderation_state' in context.user_data:
            await handle_moderation_text(update, context)
            return
        
        if 'game_state' in context.user_data:
            if update.message.photo or update.message.video:
                await handle_game_media_input(update, context)
            elif update.message.text:
                await handle_game_text_input(update, context)
            return
    
    except Exception as e:
        logger.error(f"Message handler error: {e}", exc_info=True)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception: {context.error}", exc_info=context.error)

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    print("\n" + "="*50)
    print("TRIXBOT v5.3 OPTIMIZED STARTING...")
    print("="*50)
    print(f"Moderation: {Config.MODERATION_GROUP_ID}")
    print(f"Admin: {Config.ADMIN_GROUP_ID}")
    print(f"Budapest chat: {Config.BUDAPEST_CHAT_ID}")
    print("Optimized prefixes: ctlg_, rtg_")
    
    db_initialized = loop.run_until_complete(init_db_tables())
    
    if not db_initialized:
        logger.warning("Bot starting without database")
        print("Database not available")
    else:
        print("Database connected")
    
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    autopost_service.set_bot(application.bot)
    admin_notifications.set_bot(application.bot)
    channel_stats.set_bot(application.bot)
    stats_scheduler.set_admin_notifications(admin_notifications)
    
    loop.create_task(cooldown_service.start_cleanup_task())
    
    logger.info("Services initialized")
    
    application.add_handler(CommandHandler("start", start_command, filters=budapest_filter))
    application.add_handler(CommandHandler("id", id_command, filters=budapest_filter))
    application.add_handler(CommandHandler("report", report_command, filters=budapest_filter))
    application.add_handler(CommandHandler("hp", hp_command, filters=budapest_filter))
    application.add_handler(CommandHandler("social", social_command, filters=budapest_filter))
    application.add_handler(CommandHandler("giveaway", giveaway_command, filters=budapest_filter))
    application.add_handler(CommandHandler("bonus", bonus_command, filters=budapest_filter))
    application.add_handler(CommandHandler("p2p", p2p_command, filters=budapest_filter))
    application.add_handler(CommandHandler("trixlinks", trixlinks_command, filters=budapest_filter))
    
    application.add_handler(CommandHandler("itsme", itsme_command, filters=budapest_filter))
    application.add_handler(CommandHandler("toppeople", toppeople_command, filters=budapest_filter))
    application.add_handler(CommandHandler("topboys", topboys_command, filters=budapest_filter))
    application.add_handler(CommandHandler("topgirls", topgirls_command, filters=budapest_filter))
    application.add_handler(CommandHandler("toppeoplereset", toppeoplereset_command, filters=budapest_filter))
    
    application.add_handler(CommandHandler("search", search_command, filters=budapest_filter))
    application.add_handler(CommandHandler("addtocatalog", addtocatalog_command, filters=budapest_filter))
    application.add_handler(CommandHandler("remove", remove_command, filters=budapest_filter))
    application.add_handler(CommandHandler("review", review_command, filters=budapest_filter))
    application.add_handler(CommandHandler("categoryfollow", categoryfollow_command, filters=budapest_filter))
    application.add_handler(CommandHandler("catalog", catalog_command, filters=budapest_filter))
    application.add_handler(CommandHandler("addgirltocat", addgirltocat_command, filters=budapest_filter))
    application.add_handler(CommandHandler("addboytocat", addboytocat_command, filters=budapest_filter))
    
    application.add_handler(CommandHandler("ban", ban_command, filters=budapest_filter))
    application.add_handler(CommandHandler("unban", unban_command, filters=budapest_filter))
    application.add_handler(CommandHandler("mute", mute_command, filters=budapest_filter))
    application.add_handler(CommandHandler("unmute", unmute_command, filters=budapest_filter))
    application.add_handler(CommandHandler("banlist", banlist_command, filters=budapest_filter))
    application.add_handler(CommandHandler("stats", stats_command, filters=budapest_filter))
    application.add_handler(CommandHandler("top", top_command, filters=budapest_filter))
    application.add_handler(CommandHandler("lastseen", lastseen_command, filters=budapest_filter))
    
    application.add_handler(CommandHandler("autopost", autopost_command, filters=budapest_filter))
    application.add_handler(CommandHandler("autoposttest", autopost_test_command, filters=budapest_filter))
    
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
    
    application.add_handler(CommandHandler("givett", givett_command, filters=budapest_filter))
    application.add_handler(CommandHandler("removett", removett_command, filters=budapest_filter))
    application.add_handler(CommandHandler("userstt", userstt_command, filters=budapest_filter))
    application.add_handler(CommandHandler("trixticketstart", trixticketstart_command, filters=budapest_filter))
    application.add_handler(CommandHandler("ttrenumber", ttrenumber_command, filters=budapest_filter))
    application.add_handler(CommandHandler("ttsave", ttsave_command, filters=budapest_filter))
    application.add_handler(CommandHandler("trixticketclear", trixticketclear_command, filters=budapest_filter))
    
    application.add_handler(CallbackQueryHandler(handle_all_callbacks))
    
    application.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL,
        handle_messages
    ))
    
    application.add_error_handler(error_handler)
    
    if Config.SCHEDULER_ENABLED:
        loop.create_task(autopost_service.start())
        print("Autopost enabled")
    
    loop.create_task(stats_scheduler.start())
    print("Stats scheduler enabled")
    
    logger.info("TrixBot v5.3 OPTIMIZED starting...")
    print("\n" + "="*50)
    print("TRIXBOT v5.3 OPTIMIZED IS READY!")
    print("="*50)
    print(f"Callback prefixes: mnc_, pbc_, mdc_, adm_, prc_, ctlg_, gmc_, gwc_, rtg_, rtgm_, ttc_, hpc_")
    print(f"Moderation: {Config.MODERATION_GROUP_ID}")
    print(f"Admin group: {Config.ADMIN_GROUP_ID}")
    print(f"Budapest chat (AUTO-FILTERED): {Config.BUDAPEST_CHAT_ID}")
    
    if db_initialized:
        print(f"Database: Connected")
    else:
        print(f"Database: Limited mode")
    
    print("="*50 + "\n")
    
    try:
        application.run_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt")
        print("\nStopping bot...")
    except Exception as e:
        logger.error(f"Error in main loop: {e}", exc_info=True)
        print(f"\nError: {e}")
    finally:
        print("Cleaning up...")
        
        try:
            loop.run_until_complete(stats_scheduler.stop())
            loop.run_until_complete(autopost_service.stop())
            loop.run_until_complete(cooldown_service.stop_cleanup_task())
            loop.run_until_complete(db.close())
            print("Cleanup complete")
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")
        
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
            print("Event loop closed")
        except Exception as loop_error:
            logger.error(f"Error closing loop: {loop_error}")
        
        print("\nTrixBot v5.3 OPTIMIZED stopped")

if __name__ == '__main__':
    main()
