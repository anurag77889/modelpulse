# Sprint 7 – OAuth 2.0 for Machine Clients, Scopes and Rotating Refresh Tokens

## Sprint Overview

Sprint 7 replaced the single, all-powerful login token with a small OAuth 2.0 authorization layer inside ModelPulse. Machine callers such as ML pipelines now authenticate with the **client credentials grant** and receive short-lived tokens limited to the **scopes** they were given. People who log in receive a short-lived access token plus a **rotating refresh token**, so sessions can be renewed and revoked.

The sprint also tightened the JWTs themselves (issuer, audience, unique id, token type, scope) and added the database tables behind clients and refresh tokens.

This document records why we did it, what we chose not to do, what each choice costs, and where the design stops working as the system grows.

---

# Why This Sprint Existed

Before this sprint, authentication worked like this:

- `POST /auth/login` exchanged an email and password for an HS256 JWT valid for 30 minutes.
- The token carried only `sub`, `exp` and `iat`.
- Every protected route accepted any valid token, and a token could do everything its user could.
- There were no refresh tokens, no logout and no way to revoke anything.

That was reasonable for a first release, but the main callers of `POST /models/{id}/predictions` are **services, not people**. In practice:

1. A pipeline had to store a human's email and password and log in again every 30 minutes.
2. One leaked pipeline credential exposed the whole account, including the ability to delete models.
3. A stolen token stayed valid until it expired, and nothing could end it sooner.
4. The tokens proved very little. A token minted for a different service that shared the signing key would have been accepted here.

| Problem | Change made |
| ------- | ----------- |
| Pipelines use a person's password | Client credentials grant, one revocable client per integration |
| A token can do everything | Scopes, enforced on every resource route |
| No revocation or logout | Rotating refresh tokens with reuse detection, client revocation |
| Weak tokens | `iss`, `aud`, `jti`, `typ` and `scope` claims, all required when decoding |

---

# Key Engineering Decisions

## 1. OAuth 2.0 client credentials, not API keys and not an external identity provider

The requirement was a safe way for machines to call the API. We compared five options.

| Option | What it would have given us | Why it was not chosen |
| ------ | --------------------------- | --------------------- |
| **Hashed API keys with scopes** | Most of the machine-client benefit with much less code and no token endpoint | The strongest alternative. We chose OAuth because a leaked token dies in 15 minutes while a leaked API key lives until someone notices, because client libraries already speak the standard flow, and because learning the protocol was an explicit goal. The cost is more code and more surface to get wrong. |
| **Keycloak** | Full OAuth/OIDC, single sign-on | A separate Java service with its own database. It cannot share the 0.25 vCPU / 0.5 GB task, so it needs its own ECS service, backups and upgrades. Too much operational weight for one API. |
| **Auth0 or Cognito** | Production-grade auth with no servers to run | Vendor dependency and metered billing, and machine-to-machine tokens are often the metered part. A reasonable move later; token validation lives behind one function so the switch stays small. |
| **Authorization code + Google login** | Passwordless login for people | Blocked: providers require an HTTPS redirect URL and the ALB has no domain or certificate. There is also no frontend, so nobody would use it yet. Deferred to a second phase. |
| **Refresh tokens in a Redis denylist** (the earlier roadmap idea) | Fast revocation checks | Redis is not deployed. A denylist also forgets revocations if Redis restarts, and it has no notion of a session family. |

**Decision:** build client credentials and refresh tokens inside the application, and defer authorization code until HTTPS exists.

## 2. Scopes are enforced at the route

Six scopes cover the API: `models`, `predictions` and `alerts`, each with `read` and `write`.

- `require_scopes(...)` is a FastAPI dependency attached to every resource route.
- A missing scope returns `403` with `WWW-Authenticate: Bearer error="insufficient_scope"`, as RFC 6750 describes.
- User logins receive every scope, so nothing changes for people. Clients receive only what they were registered with.
- A test calls every resource route with an unrelated scope and expects `403` each time, so a new route cannot quietly ship without a scope check.

**Tradeoff:** scopes are coarse. `models:write` covers all of the owner's models. Per-model scoping would be more precise and far more work.

## 3. Client revocation is checked on every request

A pure JWT design is stateless: the signature is the whole check. We deliberately gave that up for client tokens. On each request the dependency confirms the client is still active and still belongs to the token's user.

- **Gain:** revoking a client takes effect on its next request instead of when the token expires (up to 15 minutes later).
- **Cost:** one extra database query for client tokens (two in total with the user lookup), one for user tokens.

We judged immediate revocation worth a cheap indexed lookup at the current scale.

## 4. SHA-256, not bcrypt, for generated secrets

Passwords are still hashed with bcrypt. Client secrets and refresh tokens are different: we generate them with `secrets.token_urlsafe`, so they carry 256 bits of randomness. A 256-bit value cannot be brute-forced, and bcrypt's deliberate slowness (roughly a hundred milliseconds of CPU per check) would only make the token endpoint slower without adding protection. Comparisons use `hmac.compare_digest`.

**This only holds because we generate the secrets.** If users ever chose their own client secrets, the choice would need to be revisited.

## 5. Refresh tokens live in PostgreSQL, rotate on every use, and belong to families

- A refresh token is an opaque `mpr_...` value. Only its SHA-256 hash is stored.
- Each login starts a **family**. Every refresh marks the presented token used and issues a successor in the same family.
- The claim is atomic: `UPDATE ... WHERE used_at IS NULL`. Only one request can flip that column, so two concurrent refreshes cannot both win a single use.
- If a used token comes back after the grace window (next decision), we conclude someone else holds a copy and revoke the whole family. Other sessions of the same user are untouched.

PostgreSQL was chosen over Redis because it is already deployed, durable, and a natural home for family relationships.

## 6. A short grace window for refresh-token reuse

This decision came out of review, not the first draft. Strict single use has a usability cost: if a client retries a refresh after a lost response, or two browser tabs refresh together, the second request looks exactly like token theft and logs the user out.

- `REFRESH_REUSE_GRACE_SECONDS` (default 10) defines how soon after use a repeat is treated as a retry.
- Inside the window the repeat receives its **own new token in the same family**. Both branches stay valid. After the window, reuse revokes the family as before.
- Setting it to `0` restores strict single use.

**Tradeoff:** for those few seconds, a stolen copy of the old token also works. The window is short, and the stolen copy is still detected the moment it is used again after the window.

**A bug we caught while testing this:** with the grace set to `0`, two racing requests read the clock microseconds apart, so the loser's computed age could be slightly negative and still count as "within grace". Strict mode now returns early, and a two-thread race test covers it.

## 7. Stricter JWTs and a hard cutover

Access tokens now carry `iss`, `aud`, `sub`, `iat`, `exp`, `jti`, `typ` and `scope` (plus `client_id` for machine clients), and decoding **requires** all of them.

- A refresh token cannot be used as an access token, and an access token cannot be used as a refresh token.
- A token minted for another audience is refused.
- Tokens issued before this change lack the new claims and are rejected, so everyone must log in again after deploy. We accepted this because there are no real users to disrupt, and a grace period would have kept the weaker tokens alive.

Access tokens were shortened from 30 to 15 minutes. Refresh tokens last 7 days.

## 8. Clients act as their owner; only user logins can manage clients or read the profile

A client token carries its owner's user id plus its own limited scopes. That fits the current data model, and ownership checks keep working unchanged.

Two rules follow:

- **A client can never create or manage clients.** A pipeline's credentials must not be able to mint more credentials.
- **A client cannot read the owner's profile.** This was found while reviewing the branch: `GET /auth/me` accepted any valid token, so a pipeline holding only `predictions:write` could read its owner's email and username. Worse, our own test asserted that this worked. `/auth/me` now requires a user login, and the test asserts the opposite.

---

# Accepted Tradeoffs

| Choice | What we gain | What we give up |
| ------ | ------------ | --------------- |
| Revocation checked per request | Immediate revocation | A database read on every request |
| HS256 with one shared key | Simplicity | Anyone who can verify can also forge; rotation logs everyone out |
| 10-second reuse grace | Retries and double-tabs do not log users out | A 10-second window where a stolen old token works |
| Hard cutover of old tokens | No weak tokens remain valid | Everyone logs in again at deploy |
| Clients belong to a user | Fits existing ownership model | Clients stop working if their creator is deactivated |
| Coarse scopes | Easy to reason about | No per-model permissions |

---

# What Breaks at Scale

In the order we expect to hit them.

| # | What breaks | Why | Fix |
| - | ----------- | --- | --- |
| 1 | **Rate limits multiply with task count** | Redis is not deployed, so each task keeps its own in-memory counters. With 3 tasks, "5 logins a minute" is roughly 15. This is already true today. | Deploy Redis for the limiter. |
| 2 | **A database read on every request** | The `users` and `oauth_clients` lookups become the hottest queries at a few hundred requests per second. | A short-lived cache, at the cost of a revocation delay equal to its lifetime. |
| 3 | **`refresh_tokens` grows without bound** | Used and expired rows are kept so reuse detection works, and nothing deletes them. | A periodic purge of rows past their expiry (a Celery beat job once Redis exists). |
| 4 | **Write contention on `last_used_at`** | The client row is updated on every token request, so a client fetching tokens in a loop rewrites one row repeatedly. | Update it only when it is more than a minute stale. |
| 5 | **Shared egress IPs throttle themselves** | The 20 per minute token limit is keyed by IP, so many pipelines behind one NAT gateway share one bucket. | Key the limit by `client_id` as well. |
| 6 | **One shared signing key** | Every verifier can forge tokens, and rotating the key invalidates all sessions. | Asymmetric signing (RS256 or EdDSA) with a `kid` header and a published key set. This is also the natural moment to adopt Auth0, Cognito or Keycloak. |
| 7 | **Clients tied to individual users** | When the creator leaves, their pipelines stop. | An organisation entity that owns clients. |

---

# Challenges

## Testing a Race Honestly

The atomic claim is only meaningful if two requests really run at once. The `TestClient` cannot do that, so the race tests call the token service directly from two threads, each with its own database session, released together by a barrier. In strict mode exactly one request must win. In grace mode both must succeed with different tokens. This is what exposed the negative-age clock bug.

## Stepping Past a Time Window Without Sleeping

Tests for strict reuse now need the grace window to have passed. Sleeping 10 seconds in each test would make the suite slow, so a small helper moves the stored `used_at` back in time instead.

## A Test That Locked In a Bug

`test_me_works_for_client_tokens` asserted that a client token could read the owner's profile. It passed, which is why the problem survived until review. The test was inverted along with the fix.

## Environment Failures Look Like Code Failures

When Docker Desktop is closed, nothing answers on Redis port 6379, and every test that uses the database fixture errors at setup. A run reporting "17 passed, 45 errors" looked alarming but meant the environment was down, not the code.

---

# Lessons Learned

## A Passing Test Is Not Proof of Correct Behaviour

A test written to describe current behaviour can enshrine a mistake. Reviewing what the tests assert, not just whether they pass, caught the profile leak.

## Security Controls Have Usability Costs

Strict reuse detection is correct in theory and punishing in practice. The grace window shows the cost can be bounded and made configurable rather than ignored.

## Make "Off" Mean Off

A setting of zero must behave literally. Our first version let a zero-second grace leak through because of clock skew.

## The Hash You Pick Depends on Where the Secret Came From

bcrypt is right for human-chosen passwords and wasteful for random 256-bit secrets. The decision is about entropy, not about which algorithm sounds stronger.

## Design the Revocation Story Early

Choosing between stateless tokens and immediate revocation shapes the whole design. Deciding it up front, and writing down the cost, is cheaper than discovering it later.

---

# If We Started Again Today

- Use asymmetric signing with a `kid` header from the first token, so key rotation and external verifiers are possible without a breaking change.
- Make an organisation own clients instead of a single user.
- Ship the refresh-token purge job in the same sprint, not as a follow-up.
- Seriously consider API keys first, and add OAuth only when a second kind of consumer needed it. OAuth was the right choice for learning and for short-lived tokens, but API keys would have delivered much of the value sooner.
- Deploy Redis before adding more rate-limited endpoints, so limits are accurate from the start.

---

# Interview Talking Points

- Explain why client credentials fit machine callers and authorization code fits people, and why the second was deferred (HTTPS redirect requirement, no frontend).
- Describe how refresh-token rotation with family revocation detects theft, and why a short grace window prevents false positives from retries.
- Justify SHA-256 for generated secrets and bcrypt for passwords in terms of entropy.
- Discuss the stateless-versus-revocable tradeoff and what it costs at scale.
- Describe how a race condition was tested with real threads and two database sessions, and what the test found.
- Explain how reviewing your own tests caught a privilege leak.

---

# What Was Verified

- The full suite passes with 175 tests (115 before this sprint), and flake8, black and isort are clean.
- The two-thread race tests passed in 8 of 8 repeated runs.
- The grace-window tests fail when the grace is forced to `0`, which confirms they detect the behaviour they claim to.

---

# What Is Not Yet Verified

- The code is not deployed. Production still runs the previous release.
- Migration `b7e1c4d9a2f6` has run against the local test database only, not against RDS.
- The race tests used two threads on a local PostgreSQL, not multiple ECS tasks.
- A live run against a real local server (login, client creation, token exchange, scope denial, rotation, replay, revocation, and two rate limits) passed 11 of 11 checks, but it ran before the grace window and `/auth/me` changes. Those changes are covered by automated tests instead.

---

# Engineering Reflection

This sprint was less about adding endpoints and more about deciding who is allowed to do what, for how long, and how to take that permission back. The most valuable moments were the review findings: a profile leak that our own test endorsed, and a retry behaviour that would have logged users out. Both were cheap to fix before shipping and expensive to discover afterwards, which is the argument for writing the tradeoffs down before the push, not after.
