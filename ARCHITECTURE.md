# ARCHITECTURE.md

## 📁 СТРУКТУРА ПРОЕКТА

### 🎯 ЯДРО СИСТЕМЫ
- main.py
- config.py
- models.py
- requirements.txt

### 📊 ДАННЫЕ (data/)
- user_data.py
- games_data.py
- links_data.py

### 🎮 ОБРАБОТЧИКИ (handlers/)
- start_handler.py
- menu_handler.py
- catalog_handler.py
- games_handler.py
- giveaway_handler.py
- info_handler.py
- rating_handler.py
- trixticket_handler.py
- admin_handler.py
- moderation_handler.py
- autopost_handler.py
- piar_handler.py
- publication_handler.py
- message_handler.py

### ⚙️ СЕРВИСЫ (services/)
- db.py
- cache_service.py
- catalog_service.py
- admin_notifications.py
- channel_stats.py
- autopost_service.py
- scheduler_service.py
- filter_service.py
- cooldown.py
- hashtags.py

### 🔧 УТИЛИТЫ (utils/)
- decorators.py
- permissions.py
- validators.py

### 🗄️ МИГРАЦИИ БАЗЫ ДАННЫХ
- check_db.py
- init_db.py
- migrate_db.py
- fix_catalog_db.py
- migrate_catalog.py
- migrate_catalog_author.py
- migrate_catalog_media.py
- migrate_catalog_numbers.py

### 🚀 ДЕПЛОЙ
- Procfile
- railway.json
- runtime.txt
