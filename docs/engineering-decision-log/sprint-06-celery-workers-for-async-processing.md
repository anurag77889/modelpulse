# Sprint 6 – Background Workers with Celery for Asynchronous Processing

## Sprint Overview

Sprint 6 introduced asynchronous background processing into the ML Monitor API by integrating Celery with Redis. Prior to this sprint, prediction logging, drift detection, alert generation, and cache invalidation all occurred within the API request lifecycle. While functional, this approach increased request latency and tightly coupled user-facing requests with computationally expensive background operations.

The objective of this sprint was to decouple prediction ingestion from post-processing by introducing a production-ready task queue. Prediction processing now executes asynchronously inside dedicated Celery workers, resulting in faster API responses, better scalability, improved fault tolerance, and a cleaner separation of responsibilities.

This sprint also introduced a comprehensive testing strategy covering unit tests, integration tests, and worker orchestration.

---

# Why This Sprint Existed

As the project evolved, prediction processing became responsible for several independent tasks:

- Computing prediction drift
- Generating alerts when drift thresholds were exceeded
- Invalidating cached dashboard summaries
- Preparing the system for future background workloads

Executing all of these operations synchronously caused the API request lifecycle to grow unnecessarily long. Every prediction request had to wait until all post-processing completed before returning a response.

This architecture had several drawbacks:

- Increased response latency
- Poor scalability under higher request volumes
- Tight coupling between API endpoints and background computation
- Limited fault tolerance—any processing failure directly affected user requests

To solve these issues, the system was redesigned around asynchronous task processing using Celery and Redis.

---

# Key Engineering Decisions

## 1. Chose Celery instead of FastAPI BackgroundTasks

Although FastAPI provides BackgroundTasks, they execute inside the same application process.

Celery was selected because it provides:

- Dedicated worker processes
- Independent horizontal scaling
- Automatic retries
- Task queues
- Broker abstraction
- Production-grade reliability

This decision prepares the project for larger workloads and distributed deployments.

---

## 2. Redis as the Celery Broker

Redis was already part of the project for dashboard caching.

Instead of introducing another dependency such as RabbitMQ, Redis was reused as the Celery broker and result backend.

Advantages:

- Reduced infrastructure complexity
- Simpler Docker deployment
- Lower operational overhead
- Easier local development

---

## 3. Introduced a Dedicated Prediction Processing Service

Instead of embedding business logic directly inside Celery tasks, prediction processing was extracted into its own service.

Architecture:

Prediction API
↓
Celery Task
↓
Prediction Processing Service
↓
Drift Detection
↓
Alert Creation
↓
Cache Invalidation

This separation provides:

- Better testability
- Higher code reuse
- Cleaner business logic
- Thin worker layer

The Celery task now acts only as an orchestration layer.

---

## 4. Retry Strategy with Exponential Backoff

Background processing should tolerate transient failures such as:

- Temporary database outages
- Redis connection failures
- Network interruptions

Celery tasks were configured with:

- Automatic retries
- Exponential backoff
- Retry jitter
- Maximum retry limits

This significantly improves operational resilience without requiring custom retry logic.

---

## 5. Cache Invalidation Moved to Background Processing

Before Sprint 6:

API Request
→ Save Prediction
→ Drift Detection
→ Cache Invalidation
→ Response

After Sprint 6:

API Request
→ Save Prediction
→ Queue Celery Task
→ Response

Worker
→ Drift Detection
→ Cache Invalidation

This keeps user-facing requests lightweight while ensuring dashboard data remains eventually consistent.

---

## 6. Testing at Multiple Layers

Instead of testing only API endpoints, testing responsibilities were separated into layers.

### Unit Tests

- Prediction Processing Service
- Celery Task

Dependencies were mocked using:

- unittest.mock.patch
- MagicMock
- side_effect

These tests verify orchestration logic without requiring PostgreSQL, Redis, or Celery workers.

### Integration Tests

Integration tests verify:

- Prediction API endpoints
- Authentication
- Database persistence
- Task enqueueing
- Cache behaviour

This layered testing strategy provides both speed and confidence.

---

# Challenges

## Circular Imports

Introducing Celery created a circular dependency between:

Prediction Service
↔
Celery Task
↔
Prediction Processing Service

This was resolved by lazily importing the Celery task inside the prediction service immediately before dispatching it.

---

## Environment Configuration

Docker required service hostnames such as:

postgres
redis

while local pytest execution required:

localhost

Separating development and testing environment configuration eliminated inconsistent behaviour during automated testing.

---

## Test Isolation

Initially, every pytest execution automatically initialized the database using an autouse fixture.

As unit tests were introduced, this caused unnecessary database initialization and slowed test execution.

Removing the automatic fixture allowed:

- Fast unit tests
- Isolated integration tests
- Better testing architecture

---

## Cache Testing After Asynchronous Processing

Existing cache invalidation tests assumed synchronous behaviour.

Once processing became asynchronous, these tests no longer reflected the new architecture.

The test suite was updated so that:

- API tests verify task enqueueing.
- Worker logic is tested independently.

This separation better reflects production behaviour.

---

# Lessons Learned

This sprint reinforced several important backend engineering principles.

## Thin Workers

Celery workers should coordinate work, not contain business logic.

Business logic belongs inside services that can be tested independently.

---

## Separate Responsibilities

Request handling and background computation serve different purposes.

Separating them simplifies both the codebase and testing strategy.

---

## Architecture Influences Testing

Introducing asynchronous processing required redesigning parts of the existing test suite.

Tests should validate architectural responsibilities rather than implementation details.

---

## Infrastructure Configuration Matters

Environment configuration became significantly more important once multiple execution environments existed:

- Local development
- Docker
- Testing

Keeping these environments isolated prevents difficult debugging sessions later.

---

# If We Started Again Today

If rebuilding this project from scratch, the following improvements would be incorporated earlier:

- Environment-specific configuration classes
- Docker entrypoint that automatically runs migrations
- Transaction-based integration testing for faster execution
- Domain event abstraction between services and workers
- Structured monitoring for Celery task execution

The overall architectural direction, however, would remain the same.

---

# Interview Talking Points

This sprint demonstrates understanding of several production backend concepts.

Topics worth discussing during interviews include:

- Why asynchronous processing improves API responsiveness
- Choosing Celery over FastAPI BackgroundTasks
- Redis as both cache and message broker
- Worker retries with exponential backoff
- Thin workers vs business services
- Cache invalidation strategies
- Layered testing (unit vs integration)
- Dependency injection and mocking
- Handling circular imports
- Designing fault-tolerant background processing systems

---

# Engineering Reflection

Sprint 6 represents one of the largest architectural improvements made to the project.

Rather than simply adding a background worker, the application transitioned from a synchronous request-driven system to an event-driven architecture where API requests remain lightweight and background workers handle computationally expensive processing independently.

This sprint also highlighted that introducing new infrastructure affects far more than feature development. Testing strategy, dependency management, environment configuration, and service boundaries all required thoughtful redesign.

The resulting architecture is considerably closer to how production backend systems process long-running tasks and provides a strong foundation for future features such as scheduled jobs, notifications, model retraining, and advanced analytics.
