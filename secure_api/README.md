# Secure API для Mini App

Защищенный прокси-сервер для LangGraph API с аутентификацией через Telegram WebApp.

## 🔐 Что это делает

1. **Валидирует Telegram initData** - проверяет криптографическую подпись, чтобы убедиться, что запрос от настоящего пользователя Telegram
2. **Проверяет доступ к чату** - через Telegram Bot API проверяет, что пользователь является участником запрашиваемого чата
3. **Проксирует запросы** - если всё ок, перенаправляет запрос в LangGraph API

## 🚀 Деплой на Heroku

### 1. Создайте новое приложение

```bash
# Войдите в Heroku CLI (если еще не вошли)
heroku login

# Создайте новое приложение
heroku create secure-api-miniapp

# Или используйте существующее
# heroku git:remote -a secure-api-miniapp
```

### 2. Настройте переменные окружения

```bash
# Telegram bot token (от BotFather)
heroku config:set TELEGRAM_BOT_TOKEN=your_bot_token_here

# URL вашего LangGraph API (Heroku app с LangGraph)
heroku config:set LANGGRAPH_API_URL=https://langgraph-server-611bd1822796.herokuapp.com
```

### 3. Задеплойте

```bash
# Из корневой директории репозитория
git subtree push --prefix secure_api heroku main

# Или если уже добавили файлы в git:
cd secure_api
git add .
git commit -m "Add secure API"
git push heroku main
```

### 4. Проверьте статус

```bash
# Откройте логи
heroku logs --tail

# Проверьте health endpoint
curl https://your-app-name.herokuapp.com/health
```

## 📝 После деплоя

1. **Обновите URL в mini app**:
   Отредактируйте `miniapp/src/services/api.js`:
   ```javascript
   const API_URLS = {
     prod: 'https://secure-api-miniapp.herokuapp.com',
     dev: 'http://localhost:8000'
   }
   ```

2. **Обновите переменную окружения для бота**:
   ```bash
   # В chatbot/.env или через Heroku config
   MINIAPP_URL=https://your-miniapp-domain.com
   ```

## 🧪 Локальное тестирование

```bash
# Установите зависимости
pip install -r requirements.txt

# Настройте .env файл
cat > .env << EOF
TELEGRAM_BOT_TOKEN=your_bot_token
LANGGRAPH_API_URL=http://localhost:2024
EOF

# Запустите сервер
python main.py

# В другом терминале запустите LangGraph
cd ../langgraph-app
langgraph dev

# Проверьте health check
curl http://localhost:8000/health
```

## 🔒 Безопасность

### Как это защищает от несанкционированного доступа:

1. **Нельзя подделать initData**
   - Telegram подписывает данные через HMAC-SHA256 с секретным ключом (bot token)
   - Если пользователь изменит chat_id в URL, подпись станет невалидной
   - API вернет 401 Unauthorized

2. **Проверка членства в чате**
   - Даже если бы кто-то смог подделать подпись (невозможно без bot token)
   - API проверяет через `bot.get_chat_member()`, что user действительно в чате
   - Если user не в чате или был кикнут - 403 Forbidden

3. **Актуальность проверки**
   - Проверка происходит при каждом запросе
   - Если user выйдет из чата - сразу потеряет доступ

## 📊 Endpoints

### `GET /threads/{thread_id}/state`
Получить состояние треда (сообщения)

**Headers:**
- `X-Telegram-Init-Data` (required) - Telegram WebApp initData

**Response:** Thread state from LangGraph

### `GET /threads/{thread_id}/history`
Получить историю треда (checkpoints)

**Headers:**
- `X-Telegram-Init-Data` (required)

**Response:** Thread history from LangGraph

### `POST /threads/{thread_id}/runs/wait`
Отправить сообщение в тред

**Headers:**
- `X-Telegram-Init-Data` (required)

**Body:** Run configuration (see LangGraph API docs)

**Response:** Run result from LangGraph

### `GET /health`
Health check endpoint (не требует аутентификации)

## 🐛 Отладка

### Проверка валидации initData

```python
from telegram_validator import validate_init_data

init_data = "user=...&hash=..."
bot_token = "your_bot_token"

try:
    user_id = validate_init_data(init_data, bot_token)
    print(f"Valid! User ID: {user_id}")
except ValueError as e:
    print(f"Invalid: {e}")
```

### Проверка доступа к чату

```python
from telegram import Bot
from access_validator import validate_thread_access

bot = Bot(token="your_bot_token")
has_access = await validate_thread_access(
    bot=bot,
    chat_id="-1002557941720",
    user_id=118497177
)
print(f"Has access: {has_access}")
```

## 📚 Архитектура

```
Mini App (Frontend)
    ↓ HTTP Request with X-Telegram-Init-Data header
Secure API (FastAPI)
    ↓ 1. Validate initData signature
    ↓ 2. Extract user_id
    ↓ 3. Get thread metadata (chat_id)
    ↓ 4. Check bot.get_chat_member(chat_id, user_id)
    ↓ 5. If authorized → proxy request
LangGraph API
    ↓ Response
Secure API
    ↓ Response
Mini App
```
