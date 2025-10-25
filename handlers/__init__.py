# handlers/__init__.py - OPTIMIZED v5.2
# Без profile_handler и help_commands

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
from .basic_handler import (
    id_command, 
    participants_command, 
    report_command
)
from .link_handler import trixlinks_command
from .advanced_moderation import (
    del_command, 
    purge_command, 
    slowmode_command, 
    noslowmode_command,
    lockdown_command, 
    antiinvite_command, 
    tagall_command, 
    admins_command
)
from .admin_handler import (
    admin_command, 
    say_command, 
    handle_admin_callback,
    broadcast_command,
    sendstats_command
)
from .autopost_handler import (
    autopost_command, 
    autopost_test_command
)

# ============= RATING (TOPPEOPLE) - OPTIMIZED v5.2 =============
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

# ============= CATALOG - OPTIMIZED v5.2 =============
from .catalog_handler_optimized import (
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

# ============= GAMES - OPTIMIZED v5.2 =============
from .games_handler_optimized import (
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
from .stats_commands import (
    channelstats_command,
    fullstats_command,
    resetmsgcount_command,
    chatinfo_command
)
from .social_handler import social_command, giveaway_command
from .bonus_handler import bonus_command

# ============= GIVEAWAY - OPTIMIZED v5.2 =============
from .giveaway_handler_optimized import (
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
    
    # Basic
    'id_command',
    'participants_command',
    'report_command',
    
    # Links
    'trixlinks_command',
    
    # Advanced moderation
    'del_command',
    'purge_command',
    'slowmode_command',
    'noslowmode_command',
    'lockdown_command',
    'antiinvite_command',
    'tagall_command',
    'admins_command',
    
    # Admin
    'admin_command',
    'say_command',
    'handle_admin_callback',
    'broadcast_command',
    'sendstats_command',
    
    # Autopost
    'autopost_command',
    'autopost_test_command',
    
    # Rating (TopPeople) - OPTIMIZED v5.2
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
    
    # Catalog - OPTIMIZED v5.2
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
    
    # Games - OPTIMIZED v5.2
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
    
    # Stats
    'channelstats_command',
    'fullstats_command',
    'resetmsgcount_command',
    'chatinfo_command',
    
    # Social
    'social_command',
    'giveaway_command',
    
    # Bonus
    'bonus_command',
    
    # Giveaway - OPTIMIZED v5.2
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
