# 📋 Каталог услуг для TrixBot

## 🎯 Описание

Полнофункциональный каталог услуг для Telegram-бота с возможностью:
- 📱 Просмотра постов по 5-10 случайным образом (без повторов)
- 🔍 Поиска по категориям и тегам
- ⭐ Приоритетных постов (до 10)
- 📢 Рекламных постов (каждые 10 записей)
- 💬 Отзывов о специалистах
- 🔔 Подписок на уведомления
- 📊 Детальной статистики

---

## 📦 Структура файлов

```
TrixBot/
├── models.py                          # ← Добавить модели каталога
├── main.py                            # ← Добавить регистрацию команд
├── handlers/
│   ├── __init__.py                    # ← Добавить импорты
│   └── catalog_handler.py             # ← НОВЫЙ файл
├── services/
│   └── catalog_service.py             # ← НОВЫЙ файл
├── migrations/
│   └── 001_add_catalog.sql            # ← НОВЫЙ файл
└── docs/
    ├── CATALOG_README.md              # ← Этот файл
    ├── ИНТЕГРАЦИЯ_КАТАЛОГА.md         # ← Инструкция
    ├── CATALOG_USAGE_EXAMPLES.md      # ← Примеры
    └── CATALOG_QUICKSTART.sh          # ← Скрипт установки
```

---

## 🚀 Быстрый старт

### Вариант 1: Автоматическая установка

```bash
chmod +x CATALOG_QUICKSTART.sh
./CATALOG_QUICKSTART.sh
```

### Вариант 2: Ручная установка

#### 1. Скопируйте файлы

```bash
# Создайте файлы из артефактов Claude
cp models_catalog.py models.py  # Добавьте в конец models.py
cp catalog_service.py services/
cp catalog_handler.py handlers/
```

#### 2. Обновите models.py

Добавьте в конец файла классы из `models_catalog.py`:
- `CatalogPost`
- `CatalogReview`
- `CatalogSubscription`
- `CatalogSession`

#### 3. Обновите handlers/__init__.py

```python
from .catalog_handler import (
    catalog_command, search_command, addtocatalog_command,
    review_command, catalogpriority_command, addcatalogreklama_command,
    catalog_stats_users_command, catalog_stats_categories_command,
    catalog_stats_popular_command, handle_catalog_callback, handle_catalog_text
)

# Добавьте в __all__
```

#### 4. Обновите main.py

См. подробную инструкцию в `ИНТЕГРАЦИЯ_КАТАЛОГА.md`

#### 5. Миграция БД

```bash
# PostgreSQL
psql -U your_user -d your_database -f migrations/001_add_catalog.sql

# Или через Python
python migrate_db.py
```

#### 6. Запустите бота

```bash
python main.py
```

---

## 📋 Команды

### Для пользователей

| Команда | Описание |
|---------|----------|
| `/catalog` | Просмотр каталога (5-10 постов) |
| `/search` | Поиск по категориям |
| `/addtocatalog` | Добавить услугу |
| `/review [id]` | Оставить отзыв |

### Для админов

| Команда | Описание |
|---------|----------|
| `/catalogpriority` | Установить приоритетные посты |
| `/addcatalogreklama` | Добавить рекламу |
| `/catalog_stats_users` | Статистика пользователей |
| `/catalog_stats_categories` | Статистика категорий |
| `/catalog_stats_popular` | Топ-10 постов |

---

## 🗂️ Категории

### 💇‍♀️ Красота и уход
Барбер, БьютиПроцедуры, Волосы, Косметолог, Депиляция, Эпиляция, Маникюр, Ресницы и брови, Тату

### 🩺 Здоровье и тело
Ветеринар, Врач, Массажист, Психолог, Стоматолог, Спорт

### 🛠️ Услуги и помощь
Автомеханик, Грузчик, Клининг, Мастер по дому, Перевозчик, Ремонт техники, Няня, Юрист

### 📚 Обучение и развитие
Каналы по изучению венгерского, Каналы по изучению английского, Курсы, Переводчик, Репетитор, Музыка, Риелтор

### 🎭 Досуг и впечатления
Еда, Фотограф, Экскурсии, Для детей, Ремонт, Швея, Цветы

---

## 🔥 Основные функции

### ✅ Случайная выдача без повторов

```python
# Пользователь запускает /catalog
# Показываются 5-10 случайных постов
# В одной сессии посты не повторяются
# Сессия сбрасывается при /start
```

### ✅ Приоритетные посты

```python
# Админ: /catalogpriority
# Добавляет до 10 ссылок на посты
# Эти посты показываются первыми
# Пользователь не видит, что это приоритет
```

### ✅ Рекламные посты

```python
# Админ: /addcatalogreklama
# Добавляет рекламный пост
# Показывается каждые 10 записей
# Выглядит как обычный пост
```

### ✅ Поиск

```python
# /search → выбор категории → подкатегория
# Показываются только посты из выбранной категории
# Постраничный вывод по 5-10 записей
```

### ✅ Статистика

- **Views** - просмотры постов
- **Clicks** - переходы по ссылкам
- **CTR** - отношение кликов к просмотрам
- **Активность** - по дням/неделям/месяцам

---

## 🗄️ База данных

### Таблицы

#### `catalog_posts`
```sql
id, user_id, catalog_link, category, name, tags,
created_at, updated_at, is_active, clicks, views,
is_priority, is_ad, ad_frequency
```

#### `catalog_reviews`
```sql
id, catalog_post_id, user_id, username, 
review_text, rating, created_at
```

#### `catalog_subscriptions`
```sql
id, user_id, subscription_type, 
subscription_value, created_at
```

#### `catalog_sessions`
```sql
id, user_id, viewed_posts, 
last_activity, session_active
```

### Индексы

- `idx_catalog_posts_category` - быстрый поиск по категории
- `idx_catalog_posts_tags` (GIN) - поиск по тегам
- `idx_catalog_posts_is_priority` - приоритетные посты
- `idx_catalog_posts_is_ad` - рекламные посты

### Представления

- `catalog_stats_by_category` - статистика по категориям
- `catalog_top_posts` - топ-50 популярных
- `catalog_user_activity` - активность пользователей

---

## 📊 API сервиса

### `CatalogService`

```python
# Добавление
await catalog_service.add_post(user_id, link, category, name, tags)

# Получение случайных
posts = await catalog_service.get_random_posts(user_id, count=5)

# Поиск
posts = await catalog_service.search_posts(category="Маникюр", tags=["гель-лак"])

# Статистика
await catalog_service.increment_views(post_id)
await catalog_service.increment_clicks(post_id)

# Приоритет
await catalog_service.set_priority_posts([link1, link2, link3])

# Реклама
await catalog_service.add_ad_post(link, description)

# Сессии
await catalog_service.reset_session(user_id)
```

---

## 🎨 UI/UX

### Просмотр каталога

```
📋 Запись 1/5

📂 Категория: Маникюр
📝 Мария - профессиональный маникюр

🏷️ Теги: маникюр, гель-лак, наращивание
👁 Просмотров: 45

[🔗 Перейти к посту] [💬 Оставить отзыв]

---

📊 Показано постов: 5

[➡️ Следующие 5] [✅ Закончить] [🔍 Поиск]
```

### Добавление поста

```
Шаг 1/4: Ссылка
Шаг 2/4: Категория
Шаг 3/4: Описание
Шаг 4/4: Теги
```

---

## 🔧 Конфигурация

### config.py

```python
CATALOG_CHANNEL_ID = -1002601716810  # ID канала каталога
CATALOG_POSTS_PER_PAGE = 5           # Постов на страницу
CATALOG_MAX_TAGS = 10                # Максимум тегов
CATALOG_MAX_PRIORITY = 10            # Максимум приоритетных
```

---

## 🐛 Troubleshooting

### Ошибка: модуль не найден

```bash
# Проверьте, что файлы скопированы
ls -la handlers/catalog_handler.py
ls -la services/catalog_service.py
```

### Ошибка: таблицы не существуют

```bash
# Запустите миграцию
python migrate_db.py
```

### Ошибка: callback не работает

```python
# Проверьте в main.py:
elif handler_type == "catalog":
    await handle_catalog_callback(update, context)
```

---

## 📈 Производительность

### Оптимизация запросов

- **GIN-индекс** на tags для быстрого поиска
- **Кэширование** сессий пользователей
- **Batch-запросы** для статистики
- **Async/await** везде

### Рекомендации

- Очищайте старые сессии (>7 дней)
- Удаляйте неактивные посты (is_active=False)
- Следите за размером таблицы views/clicks
- Используйте pg_cron для автоочистки

---

## 🔐 Безопасность

### Валидация

- ✅ Проверка ссылок (только t.me/)
- ✅ Ограничение тегов (до 10)
- ✅ Лимит символов (255/500/1000)
- ✅ SQL-инъекции защищены (ORM)

### Права доступа

- Пользователи: просмотр, добавление, отзывы
- Админы: приоритет, реклама, статистика, удаление

---

## 📚 Документация

- [ИНТЕГРАЦИЯ_КАТАЛОГА.md](./ИНТЕГРАЦИЯ_КАТАЛОГА.md) - подробная инструкция
- [CATALOG_USAGE_EXAMPLES.md](./CATALOG_USAGE_EXAMPLES.md) - примеры
- [001_add_catalog.sql](../migrations/001_add_catalog.sql) - SQL-миграция

---

## 🤝 Поддержка

### Вопросы?

1. Проверьте документацию выше
2. Посмотрите примеры в CATALOG_USAGE_EXAMPLES.md
3. Проверьте логи: `tail -f logs/bot.log`

---

## 📝 Changelog

### v1.0.0 (2025-01-19)
- ✨ Первый релиз
- ✅ Основной функционал
- ✅ Приоритетные посты
- ✅ Рекламные посты
- ✅ Статистика
- ✅ Отзывы

---

## 🎉 Готово!

Каталог услуг готов к использованию. Удачи! 🚀
