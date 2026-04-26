# РБП - Разъеб ботов поддержки

Telegram-бот на Python + aiogram 3 + SQLite.

## Быстрый старт

1. Скопируйте `.env.example` в `.env` и заполните значения.
2. По умолчанию база будет создана автоматически в `data/rbp.sqlite3`.
3. Установите зависимости:

```bash
pip install -r requirements.txt
```

4. Положите приветственную картинку в `assets/welcome.jpg` или поменяйте `WELCOME_PHOTO_PATH` в `.env`.
5. Запустите бота:

```bash
python -m app.main
```

Таблицы создаются автоматически при старте. Для SQLite включены `WAL`, `foreign_keys` и `busy_timeout`, чтобы бот нормально работал с параллельными событиями.

## Команды

- `/start` - меню пользователя
- `/admin` - админ-панель, доступна только ID из `ADMIN_IDS`
