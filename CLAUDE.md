# CLAUDE.md

> Контекст для Claude Code. Читается автоматически при каждой сессии.

---

## Project Overview

**car-price-bot** — портфолио-проект: парсер б/у автомобилей + ML-регрессия цены + Telegram-бот.  
Цель: показать полный data pipeline от сырых данных до инференса в production-like окружении.

Документ с требованиями: `PRD.md`

---

## Tech Stack

- **Python 3.11**
- **PostgreSQL 15** — хранение сырых и чистых данных
- **SQLAlchemy** — ORM (без магии, plain `Session`)
- **Celery + Redis** — фоновое обучение модели
- **CatBoost** — основная регрессионная модель
- **scikit-learn** — preprocessing, метрики
- **pandas** — всё что связано с табличными данными
- **python-telegram-bot v21** — async бот
- **matplotlib** — графики
- **Docker + docker-compose** — запуск всего стека

---

## Directory Layout

```
car-price-bot/
├── scraper/       # httpx + BS4, обход пагинации
├── db/            # SQLAlchemy models + session factory
├── ml/            # train.py, predict.py, preprocess.py
├── bot/           # telegram bot + handlers/
├── tasks/         # celery_app.py + scheduled tasks
├── models/        # *.joblib артефакты (в .gitignore)
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

---

## Common Commands

```bash
# поднять всё
docker-compose up --build

# только бот (без перестройки)
docker-compose up bot

# запустить парсер вручную
python scraper/run.py

# обучить модель вручную
python ml/train.py

# запустить celery worker
celery -A tasks.celery_app worker --loglevel=info

# celery beat (расписание)
celery -A tasks.celery_app beat --loglevel=info
```

---

## Code Style

- Короткие имена переменных — `df`, `res`, `enc`, `feat`, `idx`. Не `dataframe`, не `result_dataframe`.
- Комментарии только на **зачем**, не на **что**.
- Никаких type hints везде — только там где реально помогает читаемости.
- Никаких `processData`, `executeAction` — называй по смыслу: `fetch_page`, `clean_df`, `run_training`.
- Не оборачивай каждую строчку в try/except. Пусть падает с нормальным трейсбеком.
- Не городи классы там где хватит функции.

---

## Architecture Decisions

**Почему Celery, а не cron?**  
Показывает навык работы с task queues — это то, что спрашивают на Upwork. Для MVP можно запустить как fallback через cron, но интерфейс должен быть через Celery.

**Почему CatBoost, а не sklearn?**  
Нативно работает с категориальными фичами (марка, топливо, КПП) без ручного OHE. Быстрее обучается на табличных данных.

**Почему два артефакта (`car_model.joblib` + `encoder.joblib`)?**  
Модель и энкодер сохраняются раздельно — так бот может загружать их независимо и не падает если одно обновилось, а другое нет.

**Telegram bot — async**  
`python-telegram-bot` v21 требует async. Не смешивай sync/async без необходимости.

---

## Environment Variables (`.env`)

```
DATABASE_URL=postgresql://user:pass@localhost:5432/cars
REDIS_URL=redis://localhost:6379/0
TELEGRAM_TOKEN=your_bot_token
TARGET_URL=https://example-cars.com/listings
```

Никогда не хардкодить в код. Всегда через `os.getenv()`.

---

## Key Data Models

```python
# raw_listings — как пришло с сайта
id, url, brand, model, year, mileage_km, engine_l,
fuel_type, transmission, price_eur, scraped_at

# clean_listings — после preprocessing
id, raw_id, brand_enc, model_enc, year, mileage_km,
engine_l, fuel_enc, trans_enc, price_eur
```

---

## Gotchas

- Парсер должен **не падать** при отсутствии поля в объявлении — пишет `None`, идёт дальше.
- `models/` в `.gitignore`. При деплое или демо генерируются заново через `python ml/train.py`.
- Celery beat и worker — **два отдельных процесса**. В docker-compose это два отдельных сервиса.
- При предикте бот загружает модель **один раз** при старте, не на каждый запрос.
- Не используй `bot.run_polling()` внутри `asyncio.run()` если уже есть event loop (типичная ошибка с ptb v21).

---

## Portfolio Context

Проект записывается через OBS как demo. Важно:
- README должен содержать архитектурную схему (ASCII или mermaid)
- В боте должны быть скриншот-worthy команды: `/predict` с пошаговым диалогом и `/chart` с реальным графиком
- Код должен выглядеть **написанным руками**, не AI-generated — никаких `# ===` dividers, никаких type hints на каждой строке
