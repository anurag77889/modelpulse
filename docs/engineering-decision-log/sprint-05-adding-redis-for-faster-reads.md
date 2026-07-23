# Sprint 5 Engineering Decision Log

## Redis Caching & Cache Invalidation

---

# Sprint Overview

Sprint 5 focused on improving the performance and scalability of the ML Monitor API by introducing Redis as a caching layer. Until this sprint, every request to the Model Summary endpoint executed multiple database queries to compute statistics such as prediction counts, unresolved alerts, latest prediction information, and average latency. While this approach ensured fresh data, it also meant that identical requests repeatedly performed the same expensive operations.

To solve this, a cache-aside architecture was implemented using Redis. The summary endpoint first attempts to retrieve precomputed data from Redis. On a cache miss, the application computes the summary from PostgreSQL, stores it in Redis with a configurable Time-To-Live (TTL), and returns the response. Additionally, every operation capable of changing summary data now invalidates the cached entry, ensuring that users never receive stale information.

The sprint concluded with comprehensive integration tests validating the entire cache lifecycle—from cache creation and invalidation to regeneration—bringing the project to **72 passing integration tests**.

---

# Why This Sprint Existed

As applications scale, the majority of requests are often read-heavy rather than write-heavy. Continuously recalculating dashboard statistics for every request unnecessarily increases database load, slows response times, and reduces overall scalability.

The objective of this sprint was not merely to make the endpoint faster, but to introduce a production-grade caching strategy that balanced performance with data consistency.

The goals were:

* Reduce unnecessary database queries.
* Improve response time for frequently accessed dashboard data.
* Keep cached data synchronized with the database.
* Design a caching solution that could easily be extended to future endpoints.
* Verify cache correctness through automated integration tests rather than relying solely on implementation.

---

# Key Engineering Decisions

## 1. Adopted the Cache-Aside Pattern

Instead of updating Redis whenever database records changed (write-through caching), the project adopted the Cache-Aside pattern.

The application flow became:

1. Request arrives.
2. Check Redis.
3. If cached data exists, return it immediately.
4. Otherwise, compute the summary from PostgreSQL.
5. Store the result in Redis.
6. Return the newly generated response.

### Why?

* Simpler implementation.
* Easy to reason about.
* Widely adopted in backend systems.
* Only caches data that is actually requested.
* Keeps Redis independent from database write operations.

---

## 2. Cached Only Expensive Aggregated Data

Rather than caching every API response, caching was intentionally limited to the Model Summary endpoint.

This endpoint performs multiple aggregate queries including:

* Total predictions
* Average confidence
* Average latency
* Latest prediction timestamp
* Unresolved alerts

These statistics are requested frequently while changing relatively infrequently, making them ideal cache candidates.

### Why?

Caching highly dynamic CRUD endpoints provides little benefit while increasing invalidation complexity. Aggregated dashboard data offers a significantly better performance-to-complexity ratio.

---

## 3. Used TTL-Based Expiration

Every cached summary is stored with a configurable Redis TTL.

If no invalidation occurs, Redis automatically removes stale entries after the configured duration.

### Why?

TTL acts as a safety mechanism.

Even if an invalidation were accidentally missed in the future, cached data would eventually expire automatically instead of remaining stale indefinitely.

---

## 4. Explicit Cache Invalidation on Data Changes

Whenever an operation modifies data that contributes to the summary, the corresponding cache entry is deleted.

Invalidation occurs after:

* Model updates
* Model deletion
* Prediction logging
* Alert resolution

### Why?

This guarantees that the next summary request always rebuilds the cache using the latest database state.

Instead of trying to update cached values incrementally, deleting the cache keeps the logic simple, reliable, and less error-prone.

---

## 5. Dedicated Redis Database for Testing

Testing uses a separate Redis database (`/15`) instead of the development database.

Each test automatically clears Redis before and after execution.

### Why?

This prevents test pollution and ensures:

* deterministic test execution
* isolated environments
* repeatable integration tests
* protection against accidentally deleting development cache

---

## 6. Verified Behaviour Through Integration Tests

Rather than mocking Redis, integration tests interact with a real Redis instance.

The tests validate the complete cache lifecycle:

* cache creation
* cache hits
* cache invalidation
* cache regeneration
* fresh data after regeneration

### Why?

Mocking Redis only proves that Redis functions were called.

Integration testing proves that the application behaves correctly from an end-user perspective.

---

# Challenges

### Determining the Appropriate Cache Strategy

Initially, several caching approaches were considered, including write-through caching and updating cached values after every database modification.

After evaluating the complexity involved in maintaining partially updated cache entries, explicit cache invalidation combined with cache-aside retrieval proved to be significantly simpler and more maintainable.

---

### Test Environment Isolation

Redis introduces shared state across application executions.

Without proper isolation, cached data from one test could affect another.

This was solved by:

* using a dedicated Redis test database
* automatically clearing Redis before and after every test
* ensuring the test environment loaded the correct configuration before Redis initialization

---

### Verifying Cache Correctness

Initially, testing only checked whether Redis keys existed.

This approach was expanded to verify that:

* cache entries were created
* cache entries were removed after writes
* regenerated summaries reflected updated database state

This resulted in much stronger behavioural verification.

---

# Lessons Learned

* Performance optimizations must never compromise correctness.
* Cache invalidation is often simpler than incremental cache updates.
* Automated integration tests provide significantly greater confidence than mocked implementations.
* Environment configuration and initialization order become increasingly important as infrastructure components are introduced.
* Performance improvements should always be measurable, testable, and maintainable rather than simply adding new technology.

---

# If We Started Again Today

Several improvements could be made if the sprint were implemented from scratch.

* Introduce reusable cache key helper functions instead of manually constructing cache keys.
* Abstract cache operations behind a dedicated caching service for easier expansion.
* Add cache hit/miss metrics for observability.
* Introduce Redis health monitoring.
* Benchmark response times before and after caching to quantify performance improvements.
* Expand caching to additional dashboard endpoints where aggregation costs justify it.

---

# Interview Talking Points

During interviews, this sprint demonstrates understanding beyond simply "using Redis."

Key discussion points include:

* Why Cache-Aside was selected over write-through caching.
* Why dashboard summaries benefit more from caching than CRUD endpoints.
* How cache invalidation guarantees consistency.
* Why TTL acts as a fallback rather than the primary consistency mechanism.
* Why integration testing provides stronger guarantees than mocked cache tests.
* How dedicated Redis databases improve testing reliability.
* Trade-offs between simplicity, consistency, and performance when designing caching systems.

---

# Engineering Reflection

This sprint represented the project's first major step beyond CRUD functionality into infrastructure engineering.

Rather than viewing Redis as simply another technology to integrate, the focus shifted toward solving a practical engineering problem: reducing database work while maintaining correctness.

The most valuable outcome was not the reduction in response time itself, but the architectural thinking that accompanied the implementation. Decisions around cache strategy, invalidation, testing, and environment isolation required balancing simplicity, reliability, and maintainability.

Perhaps the most important takeaway from this sprint is that performance optimization is not about adding caching everywhere. Effective caching comes from understanding application behaviour, identifying expensive read patterns, choosing an appropriate consistency model, and validating that the system continues to return correct data under all expected operations.

Sprint 5 transformed the ML Monitor API from a purely database-driven application into a service capable of leveraging infrastructure components thoughtfully, while reinforcing the importance of testing and engineering discipline alongside performance improvements.
