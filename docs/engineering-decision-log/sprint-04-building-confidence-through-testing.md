# Sprint 4 — Testing Infrastructure & Quality Engineering

## Sprint Overview

Sprint 4 focused on transforming the ML Monitor API from a functional backend into a backend that could be trusted. Until this point, the project had features, authentication, deployment, and production configuration, but there was no reliable way to verify that changes wouldn't break existing functionality.

The goal of this sprint was to build a professional testing ecosystem consisting of isolated test infrastructure, migration-driven database management, comprehensive integration tests, rate limiting verification, and continuous integration through GitHub Actions.

By the end of the sprint, every major workflow of the application was automatically tested, every GitHub push triggered the test suite, and the project had a repeatable quality assurance process similar to what is used in production engineering teams.

---

# Why This Sprint Existed

As the project grew, manual testing became increasingly unreliable.

Every new feature required repeating the same manual verification process:

- Register a user
- Login
- Create a model
- Log predictions
- Generate alerts
- Verify permissions

This approach was slow, error-prone, and impossible to scale.

More importantly, deploying new changes without automated verification meant there was always a risk of introducing regressions into production.

Sprint 4 existed to solve that problem by making testing an integrated part of the development workflow rather than a task performed after development.

---

# Key Engineering Decisions

## 1. Moved from SQLite Testing to PostgreSQL Testing

Originally, the test suite used SQLite because it was simple to configure.

However, production uses PostgreSQL.

Testing on SQLite meant the application could pass every test locally while still failing in production due to database differences.

The decision was made to create a dedicated PostgreSQL test database (`modelpulse_test`) so the testing environment matched production as closely as possible.

**Engineering Principle**

> Test against the same database engine that production uses.

---

## 2. Introduced Environment-Specific Configuration

Instead of allowing tests to accidentally connect to the development database, a dedicated testing configuration was introduced.

Separate environments now exist for:

- Development
- Testing
- Production

This ensured that automated tests could never modify development data.

**Engineering Principle**

> Environment isolation prevents accidental cross-contamination between systems.

---

## 3. Chose Alembic Migrations as the Source of Truth

Initially the test suite relied on:

```python
Base.metadata.create_all()
```

Although convenient, this bypassed migrations completely.

The project moved to:

```python
alembic upgrade head
```

before every test.

This decision ensured every schema used in testing exactly matched the schema created in production deployments.

**Engineering Principle**

> Migrations—not ORM models—define the production database.

---

## 4. Used Dedicated Fixtures Instead of Repeated Setup Code

Common workflows such as:

- User registration
- Authentication
- Model creation
- Prediction logging

were converted into reusable pytest fixtures.

Instead of every test recreating the same setup, fixtures became reusable building blocks that significantly reduced duplication and improved readability.

**Engineering Principle**

> Reuse setup logic to keep tests focused on behavior rather than preparation.

---

## 5. Disabled Rate Limiting During Most Tests

Rate limiting was interfering with unrelated integration tests.

Instead of removing the middleware, the limiter was disabled globally during testing and selectively re-enabled for dedicated rate limiting tests.

This preserved fast execution while still validating production behavior.

**Engineering Principle**

> Disable infrastructure concerns when they interfere with unrelated tests, but verify them independently.

---

## 6. Used GitHub Actions as the Automated Quality Gate

Local testing alone was not sufficient.

Every push and pull request now automatically:

- installs dependencies
- starts PostgreSQL
- runs Alembic migrations
- executes the full test suite

This guarantees that code cannot be merged without passing the automated verification process.

**Engineering Principle**

> Every code change should be validated automatically before integration.

---

# Challenges

## SQLite vs PostgreSQL Differences

Initially the test suite relied on SQLite because it was easier to configure.

Once PostgreSQL testing was introduced, several assumptions broke due to differences between database engines.

This reinforced the importance of testing with production-equivalent infrastructure.

---

## Configuration Management

Separating development and testing environments required careful handling of:

- DATABASE_URL
- SECRET_KEY
- TESTING flag

Misconfigured environments caused tests to connect to incorrect databases until environment-specific configuration was properly introduced.

---

## Alembic Configuration

Migrating from `create_all()` to Alembic required updating both application startup and testing infrastructure.

Several iterations were required before migrations consistently used the testing database rather than the development database.

---

## GitHub Actions PostgreSQL Authentication

The CI pipeline initially failed because local database credentials were embedded in environment configuration.

This highlighted the difference between local development and ephemeral CI environments and led to cleaner environment separation.

---

## Mixing Migration Management with ORM Metadata

One of the most valuable debugging sessions of the sprint occurred when the test fixture used:

```python
alembic upgrade head
```

for setup but:

```python
Base.metadata.drop_all()
```

for teardown.

The first test passed successfully, but every subsequent test failed with:

```
relation "users" does not exist
```

The root cause was that SQLAlchemy removed the application tables while Alembic still believed the database was already at the latest migration.

The solution was to replace:

```python
Base.metadata.drop_all()
```

with:

```python
alembic downgrade base
```

ensuring schema creation and cleanup were both managed by the same migration system.

This became one of the most important engineering lessons of the sprint.

---

# Lessons Learned

- Testing infrastructure is part of the product, not just a development convenience.

- Production databases should always be represented accurately inside the testing environment.

- Migrations are the authoritative definition of database schema.

- Shared state between tests creates unreliable and unpredictable test suites.

- Infrastructure features such as rate limiting should be tested independently from business logic.

- Continuous Integration is valuable only when it mirrors the production environment.

- Debugging should begin with forming and validating hypotheses rather than making random code changes.

---

# If We Started Again Today

If rebuilding the project from scratch:

- PostgreSQL testing would be implemented from the beginning.
- Alembic migrations would be used from the first test.
- Environment separation would exist before writing application code.
- GitHub Actions would be configured during the first sprint instead of after the project matured.
- Fixtures would be designed before writing integration tests.
- `.env` and `.env.test` would never be committed to the repository.

These changes would eliminate much of the migration work encountered later in development.

---

# Interview Talking Points

### Why did you replace SQLite with PostgreSQL for testing?

Because SQLite and PostgreSQL behave differently. Since production uses PostgreSQL, testing against the same database engine provides much higher confidence that production behavior matches local testing.

---

### Why did you replace `create_all()` with Alembic?

`create_all()` creates tables directly from ORM models and ignores migration history.

Alembic ensures the database schema created during testing is identical to the schema used in production deployments.

---

### What was the most difficult debugging issue?

The test suite passed the first test but failed every subsequent test because schema creation used Alembic while teardown used SQLAlchemy metadata.

Alembic believed the database was already migrated even though the tables had been removed.

The fix was to manage both setup and teardown entirely through Alembic.

---

### Why disable rate limiting during testing?

Rate limiting is an infrastructure concern rather than business logic.

Disabling it keeps unrelated integration tests deterministic while dedicated tests verify that rate limiting itself behaves correctly.

---

### Why add GitHub Actions?

Local testing depends on developer discipline.

GitHub Actions ensures every push automatically validates formatting, database migrations, and the complete integration test suite before changes are merged.

---

# Engineering Reflection

Sprint 4 fundamentally changed how the project was developed.

Previously, confidence came from manually clicking through API endpoints and hoping existing functionality still worked.

After Sprint 4, confidence came from automation.

The most significant shift was learning that testing is not simply writing assertions—it is designing reliable systems that create isolated environments, verify production behavior, and provide immediate feedback whenever regressions occur.

Perhaps the biggest lesson of the sprint was learning to debug infrastructure through hypothesis-driven reasoning rather than trial and error. Solving issues involving migrations, database state, GitHub Actions, and rate limiting required understanding how multiple systems interacted rather than focusing on individual pieces of code.

Sprint 4 transformed the ML Monitor API from a backend application into a professionally engineered backend system with repeatable quality assurance, reliable deployments, and production-grade testing practices.
