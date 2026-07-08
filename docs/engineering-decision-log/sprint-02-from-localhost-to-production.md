# Sprint 02 – From Localhost to Production

**Sprint Theme:** Transforming ModelPulse from a local development project into a production-ready backend service.

## Sprint Overview

After establishing ModelPulse's product vision in Sprint 1, the next objective was to make the application accessible outside the development environment.

Until this point, the project only existed on a local machine. While the APIs worked correctly, they had never been deployed, configured for a production environment, or validated under real deployment conditions.

The objective of this sprint was not simply to deploy the application. It was to understand what it actually means to operate a backend service in production.

---

## Why This Sprint Existed

Software that only runs on a developer's laptop provides limited value.

A production backend must be able to:

* run consistently inside a container,
* receive production configuration through environment variables,
* expose health endpoints,
* recover from deployment failures,
* and remain accessible after deployment.

The goal of this sprint was to bridge the gap between development and production.

---

## Key Engineering Decisions

### Decision 1 — Containerize the Application with Docker

Instead of relying on local machine configuration, ModelPulse was packaged inside a Docker container.

This ensured that the application would execute in a consistent environment regardless of where it was deployed.

This decision also established a reproducible deployment workflow for future environments.

---

### Decision 2 — Deploy Using Railway

Railway was selected because it provides a straightforward deployment workflow while still exposing many production concepts such as:

* environment variables,
* deployment logs,
* health checks,
* service configuration,
* and production debugging.

This allowed production concepts to be learned without introducing unnecessary operational complexity.

---

### Decision 3 — Treat Health Checks as a First-Class Feature

Instead of viewing `/health` as another endpoint, it was designed as a production monitoring endpoint.

A healthy service should communicate whether the application is operational, allowing deployment platforms to determine if traffic can safely be routed to the service.

This decision reinforced the idea that backend systems must communicate operational status, not just business data.

---

### Decision 4 — Separate Development Configuration from Production Configuration

The application was designed to receive its configuration through environment variables instead of relying on hardcoded values.

This made it possible to deploy the same application into multiple environments without changing the application code.

---

## Challenges

The largest challenge during this sprint was learning that deployment success does not necessarily mean application success.

Although the deployment process completed successfully, Railway's health checks continued to fail.

Investigation revealed that the application imported the SlowAPI limiter module instead of the configured Limiter instance.

The application could start, but every health check failed because the middleware expected a configured limiter object.

Correcting the import resolved the production issue without requiring changes to the deployment platform itself.

This became the first real production debugging experience of the project.

---

## Lessons Learned

* Deploying an application is only one step of releasing software.
* Production debugging begins after deployment, not before it.
* Health endpoints are operational infrastructure rather than application features.
* Docker provides consistency between development and production environments.
* Environment variables allow the same application to run safely across multiple deployment environments.
* Reading production logs is often the fastest path to identifying deployment failures.

---

## If We Started Again Today

If this sprint were repeated today, production readiness would be considered from the beginning of the project instead of being treated as the final deployment step.

Health checks, containerization, deployment configuration, and environment management would be planned alongside application development rather than after it.

---

## Interview Talking Points

One of the biggest lessons from this sprint was understanding that successful deployment does not guarantee a healthy production service.

During deployment, Railway reported failing health checks even though the container had started successfully. By investigating the production logs instead of guessing, I identified an incorrect SlowAPI limiter import that caused every health request to fail. Correcting the application initialization resolved the deployment issue and reinforced the importance of structured production debugging.

---

## Engineering Reflection

This sprint fundamentally changed my understanding of backend engineering.

Before this sprint, success meant seeing the application work locally.

After this sprint, success meant confidently deploying, monitoring, debugging, and operating the application in a production environment.

The mindset shifted from **"building an API"** to **"operating a backend service."**
