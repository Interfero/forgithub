# Запуск Jarvis на сервере (VPS)

Проект рассчитан на **один процесс**: собранный React + FastAPI на порту **8000**.  
Постоянный адрес даёт **домен + HTTPS** (nginx/Caddy + Let's Encrypt), не сам Jarvis.

## Публичный UI vs панель разработчика

При `npm run build` / Docker **панель разработчика не собирается в бандл** (память, XTTS, телефония, журнал).  
В интерфейсе остаются: режимы чата, индикаторы (сервер, DeepSeek, агент, токены, модель), сайдбар, чат.

Локально (`npm run dev`) панель разработчика доступна сверху.  
Чтобы включить её в production-сборку для отладки: `VITE_ENABLE_DEV_PANEL=true npm run build`.

## Быстрый старт (Docker)

```bash
git clone <ваш-репозиторий> jarvis && cd jarvis
cp .env.example .env
# Отредактируйте JARVIS_PUBLIC_URL и JARVIS_CORS_ORIGINS

chmod +x deploy/install-server.sh
./deploy/install-server.sh
```

Проверка: `curl http://127.0.0.1:8000/api/health`

### HTTPS и домен

1. Укажите A-запись домена на IP VPS.
2. Скопируйте `deploy/nginx-jarvis.conf` в nginx, подставьте домен.
3. `sudo certbot --nginx -d jarvis.example.com`
4. В `.env`: `JARVIS_PUBLIC_URL=https://jarvis.example.com`

Данные (чаты, токены, голос) хранятся в Docker volume `jarvis-data` → `/app/backend/data`.

## Telegram на сервере

- **Материнское ядро** (бот) работает внутри того же процесса — отдельный порт не нужен.
- Если `api.telegram.org` недоступен с VPS, задайте `TELEGRAM_PROXY` (SOCKS5 на вашем прокси/VPN).
- Webhook Mango/АТС: в настройках указывайте `JARVIS_PUBLIC_URL`, не `127.0.0.1`.

## Рекомендуемые мощности VPS

| Профиль | vCPU | RAM | Диск | Для чего |
|--------|------|-----|------|----------|
| **Минимум** | 2 | 2 GB | 20 GB SSD | UI + чат (DeepSeek по API), Telegram polling, edge-tts озвучка |
| **Рекомендуется** | 4 | 4–8 GB | 40 GB SSD | + загрузка документов, бухгалтер, несколько пользователей по очереди |
| **С XTTS (голос Кощей)** | 4 | **8–16 GB** | **60+ GB** | Кнопка «Докачать библиотеки»: torch + TTS ~2 GB, модель HF ~1.8 GB, кэш |

### Нагрузка по компонентам

- **CPU**: стриминг LLM почти не грузит сервер (запросы уходят в DeepSeek). Локально грузят: парсинг xlsx, синтез речи (XTTS), редкие отчёты.
- **RAM**: 2 GB хватает без XTTS; с XTTS закладывайте **8 GB+**.
- **Диск**: `backend/data` (чаты, память, голос, telegram), Hugging Face cache при XTTS.
- **Сеть**: исходящий HTTPS к DeepSeek, Telegram, при озвучке — edge-tts или Hugging Face.

### Провайдеры

Подойдёт любой VPS с Ubuntu 22.04/24.04: Timeweb, Selectel, Hetzner, DigitalOcean и т.д.  
Регион: если Telegram/API режутся — прокси или VPS в EU.

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `JARVIS_HOST` | `0.0.0.0` на сервере |
| `JARVIS_PORT` | Порт приложения (8000) |
| `JARVIS_CORS_ORIGINS` | Публичный URL UI через запятую |
| `JARVIS_PUBLIC_URL` | Для webhook телефонии (документация Mango) |
| `JARVIS_DATA_DIR` | Каталог данных (в Docker уже задан) |

API-ключи DeepSeek удобнее вводить в **Настройках** UI — они сохраняются в volume.

## Обновление

```bash
cd jarvis
git pull
docker compose build --no-cache
docker compose up -d
```

## Без Docker (systemd)

```bash
cd jarvis/frontend && npm ci && npm run build
cd ../backend && python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export JARVIS_HOST=0.0.0.0 JARVIS_PORT=8000
uvicorn main:app --host 0.0.0.0 --port 8000
```

Файл `deploy/jarvis.service` — пример unit для systemd.

## Безопасность

- Не открывайте порт 8000 в интернет без reverse proxy и HTTPS.
- Ограничьте доступ по IP или Basic Auth в nginx, если интерфейс только для вас.
- Не коммитьте `.env`, токены бота, ключи API.
