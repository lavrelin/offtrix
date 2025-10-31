from telegram import InlineKeyboardButton, InlineKeyboardMarkup

RATING_CALLBACKS = {
    'gender': 'rtg_gndr',
    'vote': 'rtg_vote',
    'back': 'rtg_back',
    'cancel': 'rtg_cnl',
    'noop': 'rtg_noop',
}

RATING_MOD_CALLBACKS = {
    'edit': 'rtgm_edit',
    'approve': 'rtgm_appr',
    'reject': 'rtgm_rjct',
    'back': 'rtgm_back',
}

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Отмена", callback_data=RATING_CALLBACKS['cancel'])]
    ])

def get_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Назад", callback_data=RATING_CALLBACKS['back'])]
    ])

def get_gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Девушка", callback_data=f"{RATING_CALLBACKS['gender']}:girl"),
            InlineKeyboardButton("Парень", callback_data=f"{RATING_CALLBACKS['gender']}:boy")
        ]
    ])

def get_moderation_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Одобрить", callback_data=f"{RATING_MOD_CALLBACKS['approve']}:{post_id}"),
            InlineKeyboardButton("Отклонить", callback_data=f"{RATING_MOD_CALLBACKS['reject']}:{post_id}")
        ]
    ])

def get_voting_keyboard(post_id: int, vote_counts: dict = None, total_score: int = 0, vote_count: int = 0) -> InlineKeyboardMarkup:
    if vote_counts is None:
        vote_counts = {-2: 0, -1: 0, 0: 0, 1: 0, 2: 0}
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"-2 ({vote_counts[-2]})", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:-2"),
            InlineKeyboardButton(f"-1 ({vote_counts[-1]})", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:-1"),
            InlineKeyboardButton(f"0 ({vote_counts[0]})", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:0"),
            InlineKeyboardButton(f"+1 ({vote_counts[1]})", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:1"),
            InlineKeyboardButton(f"+2 ({vote_counts[2]})", callback_data=f"{RATING_CALLBACKS['vote']}:{post_id}:2"),
        ],
        [
            InlineKeyboardButton(f"Рейтинг: {total_score} | Голосов: {vote_count}", callback_data=RATING_CALLBACKS['noop'])
        ]
    ])

__all__ = [
    'RATING_CALLBACKS',
    'RATING_MOD_CALLBACKS',
    'get_cancel_keyboard',
    'get_back_keyboard',
    'get_gender_keyboard',
    'get_moderation_keyboard',
    'get_voting_keyboard',
]
