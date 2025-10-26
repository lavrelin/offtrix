# -*- coding: utf-8 -*-
"""
Info Handler v1.0 - UNIFIED
Combines: bonus, links, social, medicine
Prefix: ifc_ (info)
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

# ============= CALLBACK PREFIXES =============
INFO_CALLBACKS = {
    'bonus': 'ifc_bns',
    'links': 'ifc_lnk',
    'social': 'ifc_scl',
    'medicine': 'ifc_med',
    'hp_painkillers': 'ifc_hp_pk',
    'hp_digestive': 'ifc_hp_dg',
    'hp_allergy': 'ifc_hp_al',
    'hp_cough': 'ifc_hp_cg',
    'hp_throat': 'ifc_hp_th',
    'hp_nasal': 'ifc_hp_ns',
    'hp_skin': 'ifc_hp_sk',
    'hp_other': 'ifc_hp_ot',
    'hp_all': 'ifc_hp_all',
    'hp_back': 'ifc_hp_bk',
    'back': 'ifc_bk',
}

# ============= TRIX LINKS DATA =============
TRIX_LINKS = [
    {'id': 1, 'name': '🙅‍♂️ Канал Будапешт', 'url': 'https://t.me/snghu'},
    {'id': 2, 'name': '🙅‍♀️ Чат Будапешт', 'url': 'https://t.me/tgchatxxx'},
    {'id': 3, 'name': '🙅 Каталог услуг', 'url': 'https://t.me/catalogtrix'},
    {'id': 4, 'name': '🕵️‍♂️ Барахолка (КОП)', 'url': 'https://t.me/hungarytrade'}
]

# ============= MEDICINE DATA =============
MEDICINE_DATA = {
    'painkillers': {
        'name': '💊 Обезболивающие и жаропонижающие',
        'medicines': [
            'Парацетамол — Panadol, Rubophen, Paramax',
            'Ибупрофен — Advil Ultra, Algoflex, Voltaren',
            'Аспирин — Aspirin, Kalmopyrin',
            'Ношпа — No-Spa',
            'Саридон — Saridon',
            'Алгофлекс Дуо — Algoflex Duo',
            'Кетафлекс / Ketodex — Ketodex',
            'Катафлам — Cataflam',
            'Терафлю — Neo Citran',
            'Колдрекс — Coldrex'
        ]
    },
    'digestive': {
        'name': '🔴 Противодиарейные и ЖКТ',
        'medicines': [
            'Имодиум — Imodium',
            'Лопедиум — Lopedium',
            'Смекта — Smecta',
            'Биогаия — BioGaia',
            'Тасектан — Tasectan',
            'Кралекс — Cralex',
            'Линекс — Linex',
            'ОРС 200 Хипп — ORS 200 Hipp',
            'Тева-Энтеробене — Teva-Enterobene',
            'Лопакут — Lopacut'
        ]
    },
    'allergy': {
        'name': '🤧 Против аллергии',
        'medicines': [
            'Цетиризин — Zyrtec, Cetimax',
            'Фенистил — Fenistil гель',
            'Аллергодил — Allergodil спрей',
            'Кларитин — Claritine',
            'Лордестин — Lordestin',
            'Ксизал — Xyzal',
            'Ревицет — Revicet',
            'Лертазин — Lertazin',
            'Зилола — Zilola'
        ]
    },
    'cough': {
        'name': '😷 От кашля и простуды',
        'medicines': [
            'Туссирекс — Tussirex сироп',
            'Ринотиол — Rhinothiol сироп и таблетки',
            'Амброксол — Ambroxol',
            'НеоТусс — NeoTuss сироп',
            'Паксразол — Paxirazol'
        ]
    },
    'throat': {
        'name': '🗣️ Препараты для горла',
        'medicines': [
            'Тантум Верде — Tantum Verde спрей',
            'Стрепсилс — Strepsils пастилки',
            'Фарингосопт — FaringoStop спрей',
            'Септолете — Septolete пастилки',
            'Мебукайна Минт — Mebucain Mint пастилки с лидокаином',
            'Доритрицин — Dorithricin пастилки'
        ]
    },
    'nasal': {
        'name': '👃 От насморка',
        'medicines': [
            'Оксиметазолин — Afrin, Otrivin, Nasivin',
            'Ксилометазолин — Otrivin',
            'Риноспрей — Rhinospray',
            'Аквамарис — Aquamaris',
            'Ринофлуимуцил — Rinofluimucil',
            'Ревентил — Reventil'
        ]
    },
    'skin': {
        'name': '🩹 Препараты для кожи и ран',
        'medicines': [
            'Бепантен — Bepanthen крем и мазь',
            'Пантефен — Panthenol спрей',
            'Лидокаин-Эгис — Lidocain-Egis мазь',
            'Эмофикс — Emofix гель кровоостанавливающий',
            'Лаванида — Lavanid гель',
            'Дермазин — Dermazin крем',
            'Гентамицин-Вагнер — Gentamicin-Wagner мазь',
            'Тирозур — Tyrosur гель',
            'Хансапласт — Hansaplast крем'
        ]
    },
    'other': {
        'name': '➕ Прочие',
        'medicines': [
            'Регидрон — ORS 200 Hipp (регидратация)',
            'Активированный уголь — Carbo Medicinalis',
            'Витамин C — различные бренды',
            'Магне B6 — Magne B6',
            'Омега-3 — различные бренды'
        ]
    }
}

# ============= BONUS COMMAND =============

async def bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Реферальные ссылки и бонусы"""
    
    keyboard = [
        [InlineKeyboardButton("🃏 STAKE (Crypto Casino)", url="https://stake1071.com/ru?c=RooskenChister")],
        [InlineKeyboardButton("♥️ BINANCE (до 100 USDT)", url="https://accounts.binance.com/register?ref=TRIXBONUS")],
        [InlineKeyboardButton("♣️ OKX (до 1000 USDT)", url="https://okx.com/join/8831249")],
        [InlineKeyboardButton("♦️ BYBIT (до 1000 USDT)", url="https://www.bybit.com/invite?ref=DNWE7Q5")],
        [InlineKeyboardButton("♠️ MEXC (скидка 50%)", url="https://promote.mexc.com/r/IcgN3Ivv")],
        [InlineKeyboardButton("🔙 Назад", callback_data="mnc_bk")]
    ]
    
    text = (
        "🔋 **REF LINKS + BONUSES**\n\n"
        "**Crypto:**\n\n"
        "💲 **STAKE** top Crypto Gambling\n"
        "max RTP96% ➕\n"
        "Моментальный вывод, weekly, monthly bonus\n"
        "Ставки, казино, слоты - бонус рег, cashback\n\n"
        "🟨 **BINANCE**\n"
        "• До *100 USDT* бонус\n"
        "• До *20%* скидка на комиссии\n"
        "• P2P торговля\n\n"
        "◾️ **OKX**\n"
        "• До *1 000 USDT* бонусов\n"
        "• *50%* скидка на комиссии\n\n"
        "💹 **BYBIT**\n"
        "• До *1 000 USDT* бонусов\n"
        "• Бонусы без депозита\n"
        "• P2P торговля, акции\n\n"
        "🔷 **MEXC**\n"
        "• До *50%* скидка на торговые комиссии\n"
        "• Spot и фьючерсы\n"
        "• Много Low Cap монет\n\n"
        "💳 Нажмите на кнопку для перехода"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )

# ============= TRIXLINKS COMMAND =============

async def trixlinks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полезные ссылки Trix"""
    
    keyboard = []
    for link in TRIX_LINKS:
        keyboard.append([InlineKeyboardButton(link['name'], url=link['url'])])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="mnc_bk")])
    
    text = (
        "🔗 **ПОЛЕЗНЫЕ ССЫЛКИ TRIX**\n\n"
        "📱 Наши главные площадки:\n\n"
        "🙅‍♂️ Канал Будапешт\n"
        "📝 Основной канал сообщества\n\n"
        "🙅‍♀️ Чат Будапешт\n"
        "📝 Чат для общения участников\n\n"
        "🙅 Каталог услуг\n"
        "📝 Каталог услуг и специалистов\n\n"
        "🕵️‍♂️ Барахолка (КОП)\n"
        "📝 Купля, продажа, обмен товаров\n\n"
        "👆 Нажмите на кнопку чтобы перейти"
    )
    
    await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

# ============= SOCIAL COMMAND =============

async def social_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Социальные сети TRIX"""
    
    keyboard = [
        [InlineKeyboardButton("🟧 INSTAGRAM", url="https://www.instagram.com/budapest_trix?igsh=ZXlrNmo4NDdyN2Vz&utm_source=qr)],
        [InlineKeyboardButton("📘 FACEBOOK", url="https://www.facebook.com/share/g/1EKwURtZ13/?mibextid=wwXIfr")],
        [InlineKeyboardButton("🧵 THREADS", url="https://www.threads.com/@budapest_trix?igshid=NTc4MTIwNjQ2YQ==")],
        [InlineKeyboardButton("🌀 TELEGRAM", url="https://t.me/trixilvebot")],
        [InlineKeyboardButton("🔙 Назад", callback_data="mnc_bk")]
    ]
    
    text = (
        "⚡️ **СОЦИАЛЬНЫЕ СЕТИ TRIX**\n\n"
        "✅ Follow:\n\n"
        "🟧 **INSTAGRAM** — фото, stories, актуальные новости \n\n"
        "📘 **FACEBOOK** — дублирование телеграм контента\n\n"
        "🧵 **THREADS** — короткие посты и общение \n\n"
        "🌀 **TELEGRAM** — личная связь с администрацией\n\n"
        "🔘 Нажмите на кнопку для просмотра"
    )
    
    await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

# ============= HP (MEDICINE) COMMAND =============

async def hp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список медикаментов с категориями"""
    
    keyboard = [
        [
            InlineKeyboardButton("💊 Обезболивающие", callback_data=INFO_CALLBACKS['hp_painkillers']),
            InlineKeyboardButton("🔴 ЖКТ", callback_data=INFO_CALLBACKS['hp_digestive'])
        ],
        [
            InlineKeyboardButton("🤧 Аллергия", callback_data=INFO_CALLBACKS['hp_allergy']),
            InlineKeyboardButton("😷 Кашель", callback_data=INFO_CALLBACKS['hp_cough'])
        ],
        [
            InlineKeyboardButton("🗣️ Горло", callback_data=INFO_CALLBACKS['hp_throat']),
            InlineKeyboardButton("👃 Насморк", callback_data=INFO_CALLBACKS['hp_nasal'])
        ],
        [
            InlineKeyboardButton("🩹 Кожа/Раны", callback_data=INFO_CALLBACKS['hp_skin']),
            InlineKeyboardButton("➕ Прочие", callback_data=INFO_CALLBACKS['hp_other'])
        ],
        [InlineKeyboardButton("📋 Все категории", callback_data=INFO_CALLBACKS['hp_all'])]
    ]
    
    text = (
        "💊 **Препараты без рецепта в Венгрии**\n\n"
        "Выберите категорию для просмотра:\n\n"
        "⚠️ *Важно:*\n"
        "• Консультируйтесь с врачом\n"
        "• Читайте инструкции\n"
        "• Соблюдайте дозировки\n"
        "• Проверяйте противопоказания"
    )
    
    await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

# ============= MEDICINE CATEGORY DISPLAY =============

async def show_medicine_category(query, category: str):
    """Показать конкретную категорию медикаментов"""
    
    if category not in MEDICINE_DATA:
        await query.answer("❌ Категория не найдена", show_alert=True)
        return
    
    cat_data = MEDICINE_DATA[category]
    text = f"**{cat_data['name']}**\n\n"
    
    for i, medicine in enumerate(cat_data['medicines'], 1):
        text += f"{i}. {medicine}\n"
    
    text += "\n⚠️ *Перед применением консультируйтесь с врачом*"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=INFO_CALLBACKS['hp_back'])]]
    
    try:
        await query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error showing medicine category: {e}")

async def show_all_medicines(query):
    """Показать все медикаменты"""
    
    text = "💊 **Препараты без рецепта в Венгрии**\n\n"
    
    for category_key, cat_data in MEDICINE_DATA.items():
        text += f"\n**{cat_data['name']}**\n"
        for i, medicine in enumerate(cat_data['medicines'], 1):
            text += f"{i}. {medicine}\n"
    
    text += "\n\n⚠️ *Важно: Консультируйтесь с врачом перед применением*"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=INFO_CALLBACKS['hp_back'])]]
    
    # Если текст > 4000, отправляем по частям
    if len(text) > 4000:
        for category_key, cat_data in MEDICINE_DATA.items():
            category_text = f"**{cat_data['name']}**\n\n"
            for i, medicine in enumerate(cat_data['medicines'], 1):
                category_text += f"{i}. {medicine}\n"
            
            await query.message.reply_text(category_text, parse_mode='Markdown')
        
        await query.message.reply_text(
            "⚠️ *Важно: Консультируйтесь с врачом*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        try:
            await query.edit_message_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error showing all medicines: {e}")

async def show_medicine_menu(query):
    """Показать меню категорий медикаментов"""
    
    keyboard = [
        [
            InlineKeyboardButton("💊 Обезболивающие", callback_data=INFO_CALLBACKS['hp_painkillers']),
            InlineKeyboardButton("🔴 ЖКТ", callback_data=INFO_CALLBACKS['hp_digestive'])
        ],
        [
            InlineKeyboardButton("🤧 Аллергия", callback_data=INFO_CALLBACKS['hp_allergy']),
            InlineKeyboardButton("😷 Кашель", callback_data=INFO_CALLBACKS['hp_cough'])
        ],
        [
            InlineKeyboardButton("🗣️ Горло", callback_data=INFO_CALLBACKS['hp_throat']),
            InlineKeyboardButton("👃 Насморк", callback_data=INFO_CALLBACKS['hp_nasal'])
        ],
        [
            InlineKeyboardButton("🩹 Кожа/Раны", callback_data=INFO_CALLBACKS['hp_skin']),
            InlineKeyboardButton("➕ Прочие", callback_data=INFO_CALLBACKS['hp_other'])
        ],
        [InlineKeyboardButton("📋 Все категории", callback_data=INFO_CALLBACKS['hp_all'])]
    ]
    
    text = (
        "💊 **Препараты без рецепта в Венгрии**\n\n"
        "Выберите категорию для просмотра:\n\n"
        "⚠️ *Важно:*\n"
        "• Консультируйтесь с врачом\n"
        "• Читайте инструкции\n"
        "• Соблюдайте дозировки"
    )
    
    try:
        await query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error showing medicine menu: {e}")

# ============= CALLBACK HANDLER =============

async def handle_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle info callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Medicine categories
    if data == INFO_CALLBACKS['hp_painkillers']:
        await show_medicine_category(query, 'painkillers')
    elif data == INFO_CALLBACKS['hp_digestive']:
        await show_medicine_category(query, 'digestive')
    elif data == INFO_CALLBACKS['hp_allergy']:
        await show_medicine_category(query, 'allergy')
    elif data == INFO_CALLBACKS['hp_cough']:
        await show_medicine_category(query, 'cough')
    elif data == INFO_CALLBACKS['hp_throat']:
        await show_medicine_category(query, 'throat')
    elif data == INFO_CALLBACKS['hp_nasal']:
        await show_medicine_category(query, 'nasal')
    elif data == INFO_CALLBACKS['hp_skin']:
        await show_medicine_category(query, 'skin')
    elif data == INFO_CALLBACKS['hp_other']:
        await show_medicine_category(query, 'other')
    elif data == INFO_CALLBACKS['hp_all']:
        await show_all_medicines(query)
    elif data == INFO_CALLBACKS['hp_back']:
        await show_medicine_menu(query)
    elif data == INFO_CALLBACKS['bonus']:
        await bonus_command(update, context)
    elif data == INFO_CALLBACKS['social']:
        await social_command(update, context)
    else:
        await query.answer("⚠️ Неизвестная команда", show_alert=True)

__all__ = [
    'bonus_command',
    'trixlinks_command',
    'social_command',
    'hp_command',
    'handle_info_callback',
    'INFO_CALLBACKS',
]
