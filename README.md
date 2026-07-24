# ML Monitor API

> Monitor. Detect. Alert.

Production-grade backend service for monitoring deployed ML models, detecting prediction drift, and generating timely alerts before model performance degrades in production.

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![FastAPI](https://img.shields.io/badge/FastAPI-005571.svg?style=for-the-badge&logo=fastapi)
![Postgres](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Pytest](https://img.shields.io/badge/pytest-%23ffffff.svg?style=for-the-badge&logo=pytest&logoColor=2f9fe3)
![Postman](https://img.shields.io/badge/Postman-FF6C37?style=for-the-badge&logo=postman&logoColor=white)
![JWT](https://img.shields.io/badge/JWT-black?style=for-the-badge&logo=JSON%20web%20tokens)
  
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
- 72 Automated Integration Tests
- Clean Layered Architecture


## Features

### 🔐 Authentication & Security

- JWT-based user authentication
- Secure user registration and login
- Password hashing with bcrypt
- Protected API endpoints
- Ownership-based authorization for resources

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

### 🗄 Database

- PostgreSQL persistence
- SQLAlchemy ORM
- Alembic database migrations
- Clean repository pattern for data access

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
- **72 automated tests passing**

---

### 🐳 Deployment & Infrastructure

- Dockerized application
- Docker Compose support
- Railway deployment
- Health check endpoint

## System Architecture

## Tech Stack

### Backend
 - Python
 - FastAPI

### Database
 - PostgreSQL

### Caching
 - Redis

### Authentication
 - JWT

### ORM
 - SQLAlchemy

### Migration
 - Alembic

### Testing
 - Pytest

### Deployment
 - Docker
 - Railway

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

## Environment Variables
```
APP_NAME=
DEBUG=
SECRET_KEY=
ALGORITHM=
ACCESS_TOKEN_EXPIRE_MINUTES=
DATABASE_URL=
REDIS_URL=
REDIS_CACHE_TTL_SECONDS=
```
## Running with Docker

## API Documentation

## Authentication

## Database Schema

## ML Monitoring Workflow

## Screenshots

## Roadmap

#### Sprint 1  ✅ Git Workflow + README
#### Sprint 2  ✅ Production Deployment
#### Sprint 3  ✅ PostgreSQL Migration
#### Sprint 4  ✅ Production-Grade Testing Infrastructure 
#### Sprint 5  ✅ Redis Integration
#### Sprint 6  🔄 Background Workers (Celery/Dramatiq)
#### Sprint 7  📊 Prometheus + Grafana
#### Sprint 8  🧪 Testing (80%+ Coverage)
#### Sprint 9  🔒 Security Hardening
#### Sprint 10  ⚙️ Performance & Optimization
#### Sprint 11 📈 Production Polish

## Future Improvements

## Contributing

## License
