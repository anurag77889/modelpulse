# ModelPulse

> Monitor. Detect. Alert.

Production-grade backend service for monitoring deployed ML models, detecting prediction drift, and generating timely alerts before model performance degrades in production.

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![FastAPI](https://img.shields.io/badge/FastAPI-005571.svg?style=for-the-badge&logo=fastapi)
![Postgres](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)
![Celery](https://img.shields.io/badge/celery-%23a9cc54.svg?style=for-the-badge&logo=celery&logoColor=ddf4a4)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Pytest](https://img.shields.io/badge/pytest-%23ffffff.svg?style=for-the-badge&logo=pytest&logoColor=2f9fe3)
![Postman](https://img.shields.io/badge/Postman-FF6C37?style=for-the-badge&logo=postman&logoColor=white)
![JWT](https://img.shields.io/badge/JWT-black?style=for-the-badge&logo=JSON%20web%20tokens)

[![CI Pipeline](https://github.com/anurag77889/ml-monitor-api/actions/workflows/ci.yml/badge.svg)](https://github.com/anurag77889/ml-monitor-api/actions/workflows/ci.yml)
![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

⭐ Detect prediction drift before production failures

⭐ Continuously monitor deployed ML models

⭐ Built using production backend engineering practices

## Why ML Monitor API?

Machine learning models often degrade after deployment due to data drift and changing real-world conditions. Without continuous monitoring, degraded predictions can go unnoticed, leading to business impact. ML Monitor API provides a backend service that logs predictions, tracks model health, detects anomalies, generates alerts, and exposes dashboard summaries for engineering teams.

## Highlights

- Production-grade FastAPI backend
- JWT Authentication & Authorization
- PostgreSQL + SQLAlchemy + Alembic
- Redis Cache-Aside Architecture
- Dockerized Development Environment
- Railway Deployment
- RESTful API with OpenAPI Documentation
- 90 Automated Tests — 90% Coverage

## Features

### 🔐 Authentication & Security

- JWT-based user authentication
- Secure user registration and login
- Protected API endpoints
- Ownership-based authorization

---

### 📦 Model Registry

- Register machine learning models
- Update model metadata and status
- Delete registered models
- Paginated model listing
- Retrieve detailed model information
- User-specific model isolation

---

### 📊 Prediction Monitoring

- Log model predictions through REST APIs
- Store prediction inputs and outputs
- Track prediction confidence scores
- Monitor inference latency
- Support for future ground-truth labeling
- Foundation for prediction drift analysis

---

### 🚨 Alert Management

- Automatic alert generation for model events
- List alerts with pagination
- Resolve alerts
- Track alert severity and status
- Maintain alert history for each model

---

### 📈 Model Summary Dashboard

- Aggregated model statistics
- Total prediction count
- Average confidence score
- Average inference latency
- Latest prediction timestamp
- Unresolved alert count
- Single endpoint optimized for dashboard consumption

---

### ⚡ Redis Caching

- Redis-powered caching for dashboard summaries
- Cache-Aside architecture
- Configurable cache TTL
- Automatic cache invalidation after:
  - Model updates
  - Model deletion
  - Prediction logging
  - Alert resolution
- Optimized read performance for frequently accessed dashboard data

---

### 🔄 Celery Workers

- Asynchronous background processing using Celery
- Automatic prediction post-processing
- Background drift detection
- Automatic alert generation
- Automatic Redis cache invalidation
- Automatic retry with exponential backoff

---

### 🗄 Database

- PostgreSQL persistence
- SQLAlchemy ORM
- Alembic database migrations
- Timezone-aware UTC timestamps

---

### 🧪 Testing

- Comprehensive integration test suite
- Authentication testing
- Authorization testing
- CRUD operation testing
- Prediction logging tests
- Alert management tests
- Redis cache lifecycle verification
- Dedicated Redis test database
- Automatic test isolation
- **90 automated tests passing — 90% coverage**

---

### 🐳 Deployment & Infrastructure

- Dockerized application
- Docker Compose support
- Railway deployment
- Health check endpoint

## System Architecture

<img width="362" height="582" alt="architecture drawio" src="https://github.com/user-attachments/assets/1e082fdd-49e2-40f0-b1f3-33d494c1610e" />

## Tech Stack

| Layer           | Technology          |
| :---            | :---:               |
| Backend         | Python, FastAPI, Celery    |
| Database        | PostgreSQL          |
| Caching         | Redis               |
| Authentication  | JWT                 |
| ORM             | SQLAlchemy          |
| Migration       | Alembic             |
| Testing         | Pytest              |
| Deployment      | Docker, Railway     |

## Project Structure
```
app/
    core/             → Shared logic
    routers/          → FastAPI routers
    services/         → Business logic
    models/           → SQLAlchemy models
    schemas/          → Pydantic schemas
    tasks/            → Background workers
    utils/            → Helper functions
```

## Getting Started

### Prerequisites

- Docker + Docker Compose (recommended), **or**
- Python 3.11+ with a local PostgreSQL and Redis

### Quickstart with Docker

```bash
git clone https://github.com/anurag77889/ml-monitor-api.git
cd ml-monitor-api
cp .env.example .env        # set SECRET_KEY, DATABASE_URL, REDIS_URL, CELERY_*
docker compose up --build
```

The API container runs `alembic upgrade head` on startup (see `entrypoint.sh`),
so the schema is always up to date. The Celery worker skips migrations and
waits for the API to come up.

| Service    | URL                          |
| ---------- | ---------------------------- |
| API + docs | http://localhost:8000/docs   |
| Health     | http://localhost:8000/health |

### Local development

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # point DATABASE_URL/REDIS_URL at local services
alembic upgrade head
uvicorn app.main:app --reload
```

### Running the tests

Tests need PostgreSQL and Redis. The easiest way to get them:

```bash
docker compose up -d postgres redis
pytest                             # 90 tests, coverage reported at the end
```

## Environment Variables

See [`.env.example`](.env.example) for the full template:

```
ENVIRONMENT=development | test | production
APP_NAME=
DEBUG=
TESTING=
SECRET_KEY=
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=
DATABASE_URL=
REDIS_URL=
REDIS_CACHE_TTL_SECONDS=
CELERY_BROKER_URL=
CELERY_RESULT_BACKEND=
CORS_ORIGINS=[]          # JSON list, e.g. ["https://app.example.com"]
```

Production mode refuses to start with `DEBUG=True`, `TESTING=True`, a missing
Celery broker, or a wildcard CORS origin.

## API Documentation

Interactive OpenAPI docs are served at `/docs` (Swagger UI) and `/redoc` when
`DEBUG=True`. They are intentionally not mounted in production.

Resource groups:

| Prefix                          | Purpose                          |
| ------------------------------- | -------------------------------- |
| `/auth`                         | Register, login, current user    |
| `/models`                       | Model registry CRUD + summaries  |
| `/models/{id}/predictions`      | Log and query predictions        |
| `/models/{id}/alerts`           | List, filter and resolve alerts  |

## Authentication

All protected endpoints require a JWT bearer token:

1. `POST /auth/register` — create an account (rate-limited: 3/min)
2. `POST /auth/login` — receive `{ "access_token": "...", "token_type": "bearer" }`
3. Send it on every request: `Authorization: Bearer <token>`

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword"}'
```

Tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30). Every model,
prediction and alert is scoped to its owner — cross-user access returns 403/404.

## Database Schema

| Table       | Purpose                                                              |
| ----------- | -------------------------------------------------------------------- |
| `users`     | Accounts with bcrypt-hashed passwords                                |
| `ml_models` | Registered models: owner, status, drift threshold                    |
| `predictions` | Logged predictions: input/output JSON, confidence, latency, drift score |
| `alerts`    | Generated alerts: type, severity, resolved status                    |

The schema is managed exclusively through Alembic (`alembic upgrade head`).
All timestamps are timezone-aware UTC.

## ML Monitoring Workflow

1. A client logs a prediction → `POST /models/{id}/predictions`
2. The prediction is stored and the cached dashboard summary is invalidated
   immediately
3. A Celery worker picks up the background task:
   - computes a drift score against the model's rolling baseline
   - raises a drift alert when the score crosses the model's threshold
   - refreshes the cached summary
4. `GET /models/{id}/summary` serves the pre-aggregated dashboard payload
   (cache-aside in Redis, configurable TTL)
5. Alerts are listed/filtered via `/models/{id}/alerts` and resolved
   individually or in bulk

## Roadmap

#### Sprint 1  ✅ Git Workflow + README
#### Sprint 2  ✅ Production Deployment
#### Sprint 3  ✅ PostgreSQL Migration
#### Sprint 4  ✅ Production-Grade Testing Infrastructure
#### Sprint 5  ✅ Redis Integration
#### Sprint 6  ✅ Background Workers (Celery)
#### Sprint 7  📊 Prometheus + Grafana
#### Sprint 8  🧪 Coverage gate enforced in CI
#### Sprint 9  🔒 Security Hardening
#### Sprint 10 ⚙️ Performance & Optimization
#### Sprint 11 📈 Production Polish

## Future Improvements

- Refresh tokens with server-side revocation (Redis denylist)
- API versioning (`/api/v1`) and stricter request contracts
- Unit tests for the drift-detection math; enforce a coverage floor in CI
- Prometheus metrics + Grafana dashboards
- Ground-truth feedback endpoints to close the labelling loop

## Contributing

1. Fork and create a feature branch (`feat/my-change`)
2. Install dev dependencies: `pip install -r requirements-dev.txt`
3. Add tests for any behaviour change
4. Run the same gates CI runs:

```bash
flake8 app tests alembic
black --check app tests alembic
isort --check-only app tests alembic
pytest
```

5. Open a pull request — the CI pipeline runs lint + tests on every PR

## License

Released under the [MIT License](LICENSE).
