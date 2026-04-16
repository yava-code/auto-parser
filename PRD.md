# PRD — AI Car Price Estimator

**Status:** Draft  
**Owner:** Barусama  
**Last updated:** 2026-04-16  
**Version:** 0.1

---

## 1. Problem

Secondhand car marketplaces (AutoScout24, OLX, Otomoto и т.д.) не дают покупателю понять — адекватная ли цена у конкретного объявления. Продавцы ставят что хотят, покупатели переплачивают или тратят часы на ручное сравнение.

**Цель:** инструмент, который автоматически собирает объявления, обучает регрессионную модель на реальных данных и позволяет пользователю проверить любой лот в Telegram — буквально за 10 секунд.

---

## 2. Аудитория

| Сегмент | Боль |
|---|---|
| Покупатель б/у авто | не знает рыночной цены |
| Перекупщик / арбитражник | ищет недооценённые лоты |
| Рекрутер / заказчик на Upwork | смотрит портфолио |

Основной юзер для MVP — **технически грамотный одиночка**, который хочет не переплатить за машину.

---

## 3. Цели и метрики

### Цели
- Показать полный ML-цикл: scraping → база → обучение → инференс
- Задеплоить рабочий Telegram-бот, который отвечает на `/predict`
- Использовать как якорный проект в портфолио (GitHub + demo GIF)

### Метрики успеха
| Метрика | Цель |
|---|---|
| MAE модели на тесте | < 15% от медианной цены |
| Время ответа бота на `/predict` | < 3 сек |
| Количество записей в базе при демо | ≥ 500 |
| Celery-задача переобучения работает без краша | ✓ |

---

## 4. Scope

### In scope (MVP)
- Парсер одного сайта с пагинацией → CSV / PostgreSQL
- Celery-задача ежедневного переобучения модели
- XGBoost / CatBoost регрессия с сохранением в `.joblib`
- Telegram-бот: `/start`, `/stats`, `/predict`, `/top_deals`
- График (matplotlib) — зависимость цены от пробега, отправляется в чат

### Out of scope (v1)
- Веб-интерфейс (только бот)
- Поддержка нескольких стран одновременно
- Авторизация / личный кабинет
- Мобильное приложение
- Продакшн-деплой с HTTPS (только локальный Docker-запуск)

---

## 5. Функциональные требования

### 5.1 Scraper
- Обходит пагинацию до конца (или лимит N страниц)
- Собирает: марка, модель, год, пробег (км), объём двигателя (л), топливо, КПП, цена (€)
- Сохраняет сырые данные в таблицу `raw_listings`
- Запускается руками (`python scraper/run.py`) или через Celery

### 5.2 База данных (PostgreSQL)
- `raw_listings` — как пришло с сайта
- `clean_listings` — после preprocessing: nulls заполнены, выбросы удалены, категориальные признаки закодированы
- Миграции через `alembic` (или plain SQL — на усмотрение)

### 5.3 ML Pipeline
- Запускается как Celery beat задача раз в сутки
- Шаги: load → clean → encode → split → fit → evaluate → save
- Модель: `CatBoost` (primary) или `XGBoost` (fallback)
- Артефакт: `models/car_model.joblib` + `models/encoder.joblib`
- Логирует MAE и R² в консоль / файл

### 5.4 Telegram Bot
| Команда | Что делает |
|---|---|
| `/start` | Приветствие + список команд |
| `/stats` | Кол-во записей в БД, средняя цена по топ-5 маркам |
| `/predict` | Пошаговый диалог: год → пробег → объём → топливо → КПП → предсказание |
| `/top_deals` | Топ-10 объявлений, где реальная цена ниже predicted на ≥ 20% |
| `/chart` | PNG-график цена vs пробег, отправляется как фото |

### 5.5 Non-functional
- Все сервисы запускаются через `docker-compose up`
- Secrets хранятся в `.env`, не коммитятся
- README содержит: архитектурную схему, скриншоты бота, команду запуска

---

## 6. Архитектура (high-level)

```
[Scraper] ──► [PostgreSQL raw_listings]
                      │
              [Celery Worker]
                      │
              [ML Training Script]
                      │
              [models/*.joblib]
                      │
              [Telegram Bot] ◄── [Пользователь]
                      │
              [PostgreSQL clean_listings]
```

Celery broker: **Redis** (самый простой вариант для локального запуска).

---

## 7. Стек

| Слой | Технология |
|---|---|
| Парсинг | `httpx` + `BeautifulSoup4` |
| БД | `PostgreSQL 15` + `SQLAlchemy` |
| Task queue | `Celery` + `Redis` |
| ML | `CatBoost`, `scikit-learn`, `pandas` |
| Бот | `python-telegram-bot` v21 |
| Графики | `matplotlib` |
| Инфра | `Docker`, `docker-compose` |
| Python | 3.11+ |

---

## 8. Структура проекта

```
car-price-bot/
├── scraper/
│   ├── run.py
│   └── parser.py
├── db/
│   ├── models.py
│   └── session.py
├── ml/
│   ├── train.py
│   ├── predict.py
│   └── preprocess.py
├── bot/
│   ├── main.py
│   └── handlers/
├── tasks/
│   └── celery_app.py
├── models/           # .gitignore
├── docker-compose.yml
├── .env.example
├── requirements.txt
└── README.md
```

---

## 9. Этапы (Milestones)

| # | Этап | Что готово |
|---|---|---|
| M1 | Data Layer | Парсер работает, данные в PostgreSQL |
| M2 | ML | Celery обучает модель, MAE < 15% |
| M3 | Bot MVP | `/predict` и `/stats` работают |
| M4 | Polish | `/top_deals`, `/chart`, docker-compose, README |

---

## 10. Риски

| Риск | Митигация |
|---|---|
| Сайт блокирует парсер | rate limiting + User-Agent rotation, или сменить сайт |
| Мало данных → плохая модель | парсить ≥ 1000 объявлений, добавить синтетику если надо |
| Celery крашится | supervisor или просто cron как fallback для MVP |
