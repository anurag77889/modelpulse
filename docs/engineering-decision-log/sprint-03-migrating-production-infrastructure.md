# Sprint 03 – Building Production Reliability

**Sprint Theme:** Migrating ModelPulse to a production-grade database architecture while learning how disciplined engineering decisions create reliable software.

## Sprint Overview

Sprint 3 began with a seemingly straightforward objective: replace SQLite with PostgreSQL so that ModelPulse could support production workloads more reliably.

At first, this appeared to be a simple database migration.

Instead, it became the most educational sprint of the project.

During the migration we discovered that production reliability is not achieved by changing technologies alone. It is achieved by questioning assumptions, validating every deployment step, and ensuring that infrastructure evolves in a controlled and reproducible manner.

This sprint fundamentally changed how engineering decisions were made throughout the project.

---

## Why This Sprint Existed

SQLite had served its purpose during the early stages of development, but ModelPulse was no longer just a local project.

As the application moved toward production, the database needed to provide:

* improved concurrency,
* better scalability,
* production-grade reliability,
* version-controlled schema evolution,
* and a deployment process that could be reproduced consistently.

The goal of this sprint was not simply to "use PostgreSQL."

The goal was to build confidence that ModelPulse could evolve safely as the product grows.

---

## Key Engineering Decisions

### Decision 1 — Adopt PostgreSQL as the Production Database

The database was migrated from SQLite to PostgreSQL to better support concurrent workloads and future production growth.

The decision was based on long-term operational requirements rather than immediate performance needs.

---

### Decision 2 — Establish a Single Source of Truth for Database Configuration

Instead of allowing Alembic and the application to maintain separate database configurations, Alembic was redesigned to consume the application's configuration.

This eliminated configuration drift and ensured that both the application and migration system always targeted the same database.

---

### Decision 3 — Replace Implicit Schema Creation with Version-Controlled Migrations

One of the most important discoveries of the sprint was that the project relied on SQLAlchemy's `create_all()` rather than actual Alembic migration files.

Although Alembic had already been configured, no migration history existed.

Instead of continuing with implicit table creation, the project adopted proper migration scripts as the official mechanism for evolving the database schema.

This established a reproducible and production-ready migration workflow.

---

### Decision 4 — Validate Every Production Change Before Declaring Success

Every infrastructure change was verified through smoke testing after deployment.

Success was defined by real application behavior rather than deployment status.

Production was considered healthy only after registration, authentication, health checks, and database operations succeeded successfully.

---

## Challenges

This sprint contained multiple engineering challenges that changed how future problems will be approached.

The first assumption was that updating Railway with the PostgreSQL connection string would automatically prepare the production database.

It did not.

The second assumption was that because `alembic upgrade head` completed successfully, the production database had been migrated correctly.

Further investigation revealed that no migration files actually existed.

Alembic was installed but was not managing the database schema.

This discovery fundamentally changed the migration strategy.

Instead of relying on assumptions, every deployment step was validated using deployment logs, migration history, database inspection, and production smoke testing.

Only after generating the initial migration, committing it, deploying it, and executing the migration inside Railway did the production database become fully operational.

---

## Lessons Learned

* Building a project is very different from building a production-grade product.
* Installing a technology does not mean it is being used correctly.
* Successful deployment does not guarantee successful infrastructure migration.
* Every engineering assumption should be verified with evidence.
* Database schema changes should be version-controlled from the beginning of a project.
* Production debugging is a systematic investigation rather than a process of guessing.

One realization from this sprint became a personal engineering principle:

> **"The machine has failed, and now the human has to figure out why it failed."**

---

## If We Started Again Today

If ModelPulse were started again today, Alembic migrations would be introduced from the first day of development instead of relying on automatic table creation.

Production deployment, migration strategy, smoke testing, and infrastructure verification would be planned together rather than being treated as separate activities.

The project would begin with operational discipline instead of adopting it later.

---

## Interview Talking Points

One of the most valuable experiences during this sprint was migrating a deployed FastAPI application from SQLite to PostgreSQL.

During deployment, it became clear that although Alembic was configured, the project had never actually been using migration scripts. The database schema relied on SQLAlchemy's automatic table creation instead of version-controlled migrations.

The solution involved generating the initial migration, centralizing Alembic configuration around the application's settings, redeploying the application, applying migrations inside the production environment, and validating the deployment through production smoke testing.

This experience reinforced the importance of verifying assumptions instead of relying on successful command execution alone.

---

## Engineering Reflection

Sprint 3 permanently changed how I think about backend engineering.

At the beginning of the sprint, I believed production infrastructure was mostly about changing technologies.

By the end of the sprint, I understood that production reliability comes from disciplined engineering practices:

* verify assumptions,
* version infrastructure,
* investigate failures using evidence,
* and never declare success until the real user workflow succeeds.

The project became more than a deployed backend.

It became a production system with an engineering process behind it.
