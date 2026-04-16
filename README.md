# 🚗 car-price-bot

> **AI Car Price Estimator** — full ML pipeline from raw web data to a Telegram bot that tells you whether a used car is fairly priced in under 3 seconds.

---

## Architecture

```mermaid
flowchart LR
    A[Scraper\nhttpx + BS4] -->|raw rows| B[(PostgreSQL\nraw_listings)]
    B --> C[Celery Worker\ndaily at 02:00]
    C -->|clean + encode| D[(PostgreSQL\nclean_listings)]
    C -->|fit| E[CatBoost Model\nmodels/car_model.joblib]
    E --> F[Telegram Bot\npython-telegram-bot v21]
    G[User] -- /predict\n/stats\n/top_deals\n/chart --> F
    F --> G
```

---

## Tech Stack

| Layer        | Technology                        |
|--------------|-----------------------------------|
| Scraping     | `httpx` + `BeautifulSoup4`        |
| Database     | PostgreSQL 15 + SQLAlchemy        |
| Task queue   | Celery + Redis                    |
| ML model     | CatBoost + scikit-learn           |
| Bot          | python-telegram-bot v21 (async)   |
| Charts       | matplotlib                        |
| Infrastructure | Docker + docker-compose         |
| Python       | 3.11+                             |

---

## Quick Start

### 1. Clone & configure

```bash
git clone <repo>
cd car-price-bot
cp .env.example .env
# edit .env — set your TELEGRAM_TOKEN
```

### 2. Run everything

```bash
docker-compose up --build
```

This starts:
- `postgres` — database on port 5432
- `redis` — broker on port 6379
- `bot` — Telegram bot
- `worker` — Celery worker (runs ML training on demand)
- `beat` — Celery beat (retrains model daily at 02:00 UTC)

### 3. Seed data (first time)

```bash
# scrape listings (runs inside container or locally)
python scraper/run.py --pages 10

# train the model
python ml/train.py
```

After training, the bot is fully operational.

---

## Bot Commands

| Command      | Description                                                   |
|--------------|---------------------------------------------------------------|
| `/start`     | Welcome message + list of commands                           |
| `/stats`     | DB record count, avg prices per top-5 brands                 |
| `/predict`   | Step-by-step dialog → estimated fair price                   |
| `/top_deals` | Top 10 underpriced listings (real price ≥20% below predicted)|
| `/chart`     | PNG scatter plot: price vs mileage                           |

---

## Manual Commands

```bash
# scraper only
python scraper/run.py --pages 5

# train model only
python ml/train.py

# celery worker
celery -A tasks.celery_app worker --loglevel=info

# celery beat scheduler
celery -A tasks.celery_app beat --loglevel=info

# bot only (no docker)
python bot/main.py
```

---

## Project Structure

```
car-price-bot/
├── scraper/
│   ├── parser.py       # httpx + BS4, UA rotation, null-safe parsing
│   └── run.py          # CLI entry point, dedup by URL
├── db/
│   ├── models.py       # RawListing + CleanListing ORM models
│   └── session.py      # engine + SessionLocal + init_db()
├── ml/
│   ├── preprocess.py   # clean_df(), encode_df(), IQR outlier removal
│   ├── train.py        # full training pipeline, logs MAE + R²
│   └── predict.py      # load_model() + predict_price()
├── bot/
│   ├── main.py         # Application setup + polling
│   └── handlers/
│       ├── start.py
│       ├── stats.py
│       ├── predict.py  # ConversationHandler, 6-step dialog
│       ├── top_deals.py
│       └── chart.py
├── tasks/
│   └── celery_app.py   # Celery + beat schedule
├── models/             # .gitignore — generated at runtime
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
└── README.md
```

---

## Environment Variables

| Variable       | Description                              | Example                                         |
|----------------|------------------------------------------|-------------------------------------------------|
| `DATABASE_URL` | PostgreSQL connection string             | `postgresql://cars:cars@postgres:5432/cars`     |
| `REDIS_URL`    | Redis connection string                  | `redis://redis:6379/0`                          |
| `TELEGRAM_TOKEN` | Bot token from @BotFather             | `12345:ABCdef...`                               |
| `TARGET_URL`   | Base URL to scrape                       | `https://www.autoscout24.com/lst`               |
| `SCRAPE_PAGES` | Number of pages to scrape (default: 5)  | `10`                                            |

---

## Success Metrics

| Metric                       | Target          |
|------------------------------|-----------------|
| Model MAE on test set        | < 15% of median |
| Bot `/predict` response time | < 3 seconds     |
| Listings in DB at demo       | ≥ 500           |
| Celery daily retraining      | ✓ no crash      |
# auto-parser
