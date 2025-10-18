# handlers/__init__.py - ИСПРАВЛЕННЫЕ ИМПОРТЫ

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
from .profile_handler import handle_profile_callback
from .basic_handler import (
    id_command, 
    whois_command, 
    join_command, 
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
    handle_admin_callback
)
from .autopost_handler import (
    autopost_command, 
    autopost_test_command
)
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
    handle_game_callback
)
from .medicine_handler import hp_command, handle_hp_callback
from .stats_commands import (
    channelstats_command,
    fullstats_command,
    resetmsgcount_command,
    chatinfo_command
)
from .help_commands import trix_command, handle_trix_callback
from .social_handler import social_command, giveaway_command
from .bonus_handler import bonus_command

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
    
    # Moderation (UNIFIED)
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
    
    # Profile
    'handle_profile_callback',
    
    # Basic
    'id_command',
    'whois_command',
    'join_command',
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
    
    # Autopost
    'autopost_command',
    'autopost_test_command',
    
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
    
    # Medicine
    'hp_command',
    'handle_hp_callback',
    
    # Stats
    'channelstats_command',
    'fullstats_command',
    'resetmsgcount_command',
    'chatinfo_command',
    
    # Help
    'trix_command',
    'handle_trix_callback',
    
    # Social
    'social_command',
    'giveaway_command',
    
    # Bonus
    'bonus_command'
]
