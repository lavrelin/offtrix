# handlers/__init__.py - OPTIMIZED v5.3
# Удалены: basic_handler, advanced_moderation, stats_commands
# Добавлены: id_command, report_command, silence_command из admin_handler

from .start_handler import start_command, help_command, show_main_menu, show_write_menu
from .menu_handler import handle_menu_callback
from .publication_handler import (
    handle_publication_callback, 
    handle_text_input, 
    handle_media_input
)
from .piar_handler import (
    handle_piar_callback, 
    handle_piar_text, 
    handle_piar_photo
)
from .moderation_handler import (
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
from .link_handler import trixlinks_command
from .admin_handler import (
    admin_command, 
    talkto_command,
    handle_admin_callback,
    broadcast_command,
    sendstats_command,
    id_command,
    report_command,
    silence_command,
    is_user_silenced
)
from .autopost_handler import (
    autopost_command, 
    autopost_test_command
)

# ============= RATING (TOPPEOPLE) =============
from .rating_handler import (
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
    handle_rate_profile,
    RATING_CALLBACKS,
    RATING_MOD_CALLBACKS,
)

# ============= CATALOG =============
from .catalog_handler import (
    catalog_command,
    search_command,
    addtocatalog_command,
    review_command,
    categoryfollow_command,
    addgirltocat_command,
    addboytocat_command,
    handle_catalog_callback,
    handle_catalog_text,
    handle_catalog_media,
    CATALOG_CALLBACKS,
)

# ============= GAMES =============
from .games_handler import (
    wordadd_command, 
    wordedit_command, 
    wordclear_command,
    wordon_command, 
    wordoff_command, 
    wordinfo_command,
    wordinfoedit_command, 
    anstimeset_command,
    gamesinfo_command, 
    admgamesinfo_command, 
    game_say_command,
    roll_participant_command, 
    roll_draw_command,
    rollreset_command, 
    rollstatus_command, 
    mynumber_command,
    handle_game_text_input,
    handle_game_media_input,
    handle_game_callback,
    GAME_CALLBACKS,
)

from .medicine_handler import hp_command, handle_hp_callback
from .social_handler import social_command, giveaway_command
from .bonus_handler import bonus_command

# ============= GIVEAWAY =============
from .giveaway_handler import (
    giveaway_command,
    handle_giveaway_callback,
    p2p_command,
    GIVEAWAY_CALLBACKS,
)

from .trixticket_handler import (
    tickets_command,
    myticket_command,
    trixtickets_command,
    handle_trixticket_callback,
    givett_command,
    removett_command,
    userstt_command,
    trixticketstart_command,
    ttrenumber_command,
    ttsave_command,
    trixticketclear_command
)

__all__ = [
    # Start
    'start_command',
    'help_command',
    'show_main_menu',
    'show_write_menu',
    
    # Menu
    'handle_menu_callback',
    
    # Publication
    'handle_publication_callback',
    'handle_text_input',
    'handle_media_input',
    
    # Piar
    'handle_piar_callback',
    'handle_piar_text',
    'handle_piar_photo',
    
    # Moderation
    'handle_moderation_callback',
    'handle_moderation_text',
    'ban_command',
    'unban_command',
    'mute_command',
    'unmute_command',
    'banlist_command',
    'stats_command',
    'top_command',
    'lastseen_command',
    
    # Links
    'trixlinks_command',
    
    # Admin (NEW: без basic_handler и advanced_moderation)
    'admin_command',
    'talkto_command',
    'handle_admin_callback',
    'broadcast_command',
    'sendstats_command',
    'id_command',
    'report_command',
    'silence_command',
    'is_user_silenced',
    
    # Autopost
    'autopost_command',
    'autopost_test_command',
    
    # Rating (TopPeople)
    'itsme_command',
    'toppeople_command',
    'topboys_command',
    'topgirls_command',
    'toppeoplereset_command',
    'handle_rate_callback',
    'handle_rate_moderation_callback',
    'handle_rate_photo',
    'handle_rate_age',
    'handle_rate_name',
    'handle_rate_about',
    'handle_rate_profile',
    'RATING_CALLBACKS',
    'RATING_MOD_CALLBACKS',
    
    # Catalog
    'catalog_command',
    'search_command',
    'addtocatalog_command',
    'review_command',
    'categoryfollow_command',
    'addgirltocat_command',
    'addboytocat_command',
    'handle_catalog_callback',
    'handle_catalog_text',
    'handle_catalog_media',
    'CATALOG_CALLBACKS',
    
    # Games
    'wordadd_command',
    'wordedit_command',
    'wordclear_command',
    'wordon_command',
    'wordoff_command',
    'wordinfo_command',
    'wordinfoedit_command',
    'anstimeset_command',
    'gamesinfo_command',
    'admgamesinfo_command',
    'game_say_command',
    'roll_participant_command',
    'roll_draw_command',
    'rollreset_command',
    'rollstatus_command',
    'mynumber_command',
    'handle_game_text_input',
    'handle_game_media_input',
    'handle_game_callback',
    'GAME_CALLBACKS',
    
    # Medicine
    'hp_command',
    'handle_hp_callback',
    
    # Social
    'social_command',
    'giveaway_command',
    
    # Bonus
    'bonus_command',
    
    # Giveaway
    'handle_giveaway_callback',
    'p2p_command',
    'GIVEAWAY_CALLBACKS',
    
    # TrixTicket
    'tickets_command',
    'myticket_command',
    'trixtickets_command',
    'handle_trixticket_callback',
    'givett_command',
    'removett_command',
    'userstt_command',
    'trixticketstart_command',
    'ttrenumber_command',
    'ttsave_command',
    'trixticketclear_command',
]
