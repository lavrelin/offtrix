from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CATALOG_CALLBACKS = {
    'next': 'ch_next',
    'finish': 'ch_finish',
    'restart': 'ch_restart',
    'search': 'ch_search',
    'cancel_search': 'ch_csearch',
    'category': 'ch_cat',
    'click': 'ch_click',
    'add_cat': 'ch_addcat',
    'rate': 'ch_rate',
    'cancel_review': 'ch_crev',
    'cancel': 'ch_cancel',
    'cancel_top': 'ch_ctop',
    'follow_menu': 'ch_fmenu',
    'follow_cat': 'ch_fcat',
    'my_follows': 'ch_myfol',
    'unfollow': 'ch_unfol',
    'unfollow_all': 'ch_uall',
    'reviews_menu': 'ch_rmenu',
    'view_reviews': 'ch_vrev',
    'write_review': 'ch_wrev',
    'close_menu': 'ch_close',
}

def get_navigation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➡️ Еще", callback_data=CATALOG_CALLBACKS['next']),
            InlineKeyboardButton("⏹️ Стоп", callback_data=CATALOG_CALLBACKS['finish'])
        ],
        [InlineKeyboardButton("🔍 Поиск", callback_data=CATALOG_CALLBACKS['search'])]
    ])

def get_catalog_card_keyboard(post: dict, catalog_number: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 Перейти", url=post.get('catalog_link', '#')),
            InlineKeyboardButton("⭐ Оценить", callback_data=f"{CATALOG_CALLBACKS['rate']}:{post['id']}:{catalog_number}")
        ]
    ])

def get_category_keyboard(categories: list) -> InlineKeyboardMarkup:
    keyboard = []
    for cat in categories:
        keyboard.append([InlineKeyboardButton(cat, callback_data=f"{CATALOG_CALLBACKS['add_cat']}:{cat}")])
    return InlineKeyboardMarkup(keyboard)

def get_rating_keyboard(post_id: int, catalog_number: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐", callback_data=f"{CATALOG_CALLBACKS['rate']}:1:{post_id}:{catalog_number}"),
            InlineKeyboardButton("⭐⭐", callback_data=f"{CATALOG_CALLBACKS['rate']}:2:{post_id}:{catalog_number}"),
            InlineKeyboardButton("⭐⭐⭐", callback_data=f"{CATALOG_CALLBACKS['rate']}:3:{post_id}:{catalog_number}")
        ],
        [
            InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"{CATALOG_CALLBACKS['rate']}:4:{post_id}:{catalog_number}"),
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"{CATALOG_CALLBACKS['rate']}:5:{post_id}:{catalog_number}")
        ],
        [
            InlineKeyboardButton("❌ Отмена", callback_data=CATALOG_CALLBACKS['cancel_review'])
        ]
    ])

def get_cancel_search_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отменить поиск", callback_data=CATALOG_CALLBACKS['cancel_search'])]
    ])

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data=CATALOG_CALLBACKS['cancel'])]
    ])

def get_cancel_review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отменить отзыв", callback_data=CATALOG_CALLBACKS['cancel_review'])]
    ])

def get_follow_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Подписаться", callback_data=CATALOG_CALLBACKS['follow_menu']),
            InlineKeyboardButton("📋 Мои подписки", callback_data=CATALOG_CALLBACKS['my_follows'])
        ]
    ])

def get_reviews_menu_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 Читать отзывы", callback_data=f"{CATALOG_CALLBACKS['view_reviews']}:{post_id}"),
            InlineKeyboardButton("✍️ Написать отзыв", callback_data=f"{CATALOG_CALLBACKS['write_review']}:{post_id}")
        ],
        [
            InlineKeyboardButton("❌ Закрыть", callback_data=CATALOG_CALLBACKS['close_menu'])
        ]
    ])

__all__ = [
    'CATALOG_CALLBACKS',
    'get_navigation_keyboard',
    'get_catalog_card_keyboard',
    'get_category_keyboard',
    'get_rating_keyboard',
    'get_cancel_search_keyboard',
    'get_cancel_keyboard',
    'get_cancel_review_keyboard',
    'get_follow_menu_keyboard',
    'get_reviews_menu_keyboard',
]
