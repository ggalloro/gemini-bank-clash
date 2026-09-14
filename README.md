# Gemini Bank — Microservices

A small **sample** online bank, decomposed into five services that communicate
over HTTP/JSON. Four are Python/Flask; the **ledger** is Java / Spring Boot 3.

> All data is synthetic. No real credentials, accounts, or anything sensitive.

## Architecture

```
                ┌──────────────┐
   browser ───▶ │   frontend   │  :8080  (UI only, no DB)
                └──────┬───────┘
            ┌──────────┼───────────────┬────────────────┐
            ▼          ▼               ▼                ▼
     ┌────────────┐ ┌────────────┐ ┌──────────────┐ ┌──────────────┐
     │   users    │ │   ledger   │ │  statements  │ │    fraud     │ :8084
     │   :8081    │ │   :8082    │ │    :8083     │ │   fraud.db   │ (owns held payments,
     │  users.db  │ │ ledger.db  │ │   (no DB)    │ └──────┬───────┘  calls Gemini)
     └────────────┘ └─────┬──────┘ └──────┬───────┘        │
                          │               │                ▼
                          └───── REST ────┴─────────▶ Gemini 3.7 Flash
```

- **frontend** (`:8080`) — server-rendered Jinja2 + Bootstrap 5 (via CDN). No
  database, no business logic; it orchestrates calls to the backends and stores
  the login token in the session cookie.
- **users** (`:8081`) — Python/Flask. Owns identity in `users.db`. Mints a JWT
  (HS256, `PyJWT`) on login.
- **ledger** (`:8082`) — **Java / Spring Boot 3** (Maven, `JdbcTemplate` +
  SQLite). Owns money in `ledger.db`: accounts, deposits, payments (internal +
  external), and a raw internal transaction feed.
- **statements** (`:8083`) — Python/Flask. Read-only reporting. No database of
  its own; it calls the ledger's internal API and aggregates in memory.
- **fraud** (`:8084`) — Python/Flask. Owns held payments in `fraud.db`. Uses
  Gemini 3.7 Flash to evaluate outgoing payments for fraud risk before funds move.

**Database-per-service:** no service ever opens another service's database file.
Cross-service reads go over HTTP.

**Auth:** the users service mints a JWT (HS256) signed with the shared
`TOKEN_SECRET` carrying `user_id` and `full_name`; the frontend forwards it as
`Authorization: Bearer <token>`; the Java ledger and Python fraud services validate
the signature with the same secret.

## Repository layout

```
gemini-bank-microservices/
├── docker-compose.yml
├── seed.py
├── frontend/     # Python/Flask — UI only, no DB
├── users/        # Python/Flask — identity; mints JWTs
├── ledger/       # Java / Spring Boot 3 — money
├── statements/   # Python/Flask — read-only reporting
└── fraud/        # Python/Flask — AI fraud protection; owns fraud.db
```

## Key business rules (ledger)

- A payment is rejected when the amount exceeds the account balance.
- Internal payments are atomic: the source is debited and the destination
  credited together, or neither happens.
- Amounts must be positive with at most two decimals; anything else is rejected.
- Money is held as integer cents internally and shown as 2-decimal amounts.

## Run with Docker Compose

Because the ledger is compiled Java (built in a multi-stage Dockerfile), Docker
Compose is the way to run the full stack:

```bash
docker compose up --build -d
# wait for the healthchecks to go green, then:
python seed.py            # populates synthetic users + ~60 days of data
```

Open <http://localhost:8080> and log in (see credentials below). Everything is
up and usable within ~30 seconds. Tear down with `docker compose down -v`.

`seed.py` defaults to `localhost` on the published ports, so running it on the
host works as-is.

### Running a second stack (per-service ports)

Published host ports are env vars with defaults (`FRONTEND_PORT` 8080,
`USERS_PORT` 8081, `LEDGER_PORT` 8082, `STATEMENTS_PORT` 8083); container ports
never change. To run a **second** stack side by side, apply an offset and a
distinct project name:

```bash
COMPOSE_PROJECT_NAME=gemini-bank-2 \
  FRONTEND_PORT=9080 USERS_PORT=9081 LEDGER_PORT=9082 STATEMENTS_PORT=9083 \
  docker compose up --build -d
# reachable at http://localhost:9080
```

See [`.env.example`](.env.example) for the full set of variables.

## Seed credentials

After running `seed.py`:

| Username | Full name      | Password   |
|----------|----------------|------------|
| `ana`    | Ana Ferreira   | `demo1234` |
| `bruno`  | Bruno Costa    | `demo1234` |
| `carla`  | Carla Nunes    | `demo1234` |
| `david`  | David Klein    | `demo1234` |
| `elena`  | Elena Rossi    | `demo1234` |

## Tests

The **users** service ships a pytest suite and the **ledger** service ships a
JUnit/Spring `MockMvc` suite (happy path, validation errors, insufficient funds,
atomic internal payment).

```bash
( cd users  && pip install -r requirements.txt && python -m pytest -q )
( cd ledger && mvn test )
```

## Environment variables

| Variable          | Used by              | Default                  |
|-------------------|----------------------|--------------------------|
| `TOKEN_SECRET`    | users, ledger        | `dev-secret-change-me`   |
| `USERS_URL`       | frontend, seed       | `http://localhost:8081`  |
| `LEDGER_URL`      | frontend, statements, seed | `http://localhost:8082` |
| `STATEMENTS_URL`  | frontend             | `http://localhost:8083`  |
| `USERS_DB`        | users                | `users.db`               |
| `LEDGER_DB`       | ledger               | `ledger.db`              |
| `FRONTEND_SECRET` | frontend             | `dev-frontend-secret`    |

## Safety hook

The repo ships an Antigravity `PreToolUse` safety gate at `.agents/hooks.json`
+ `.agents/hooks/block-destructive-ops.sh`. It denies irreversible shell
commands (`git push --force`, `git reset --hard`, `rm -rf /`, `chmod 777`,
`curl | bash`, …) for every agent conversation in this project.

## GitHub Workflows

This repository includes automated GitHub Actions workflows powered by Google Antigravity and Vertex AI:

1. **Antigravity Coder** ([`.github/workflows/antigravity-coder.yml`](.github/workflows/antigravity-coder.yml)):
   - **Trigger:** Triggered when a comment starting with `/implement` is posted on an issue (non-PR).
   - **Action:** Autonomous coding agent implements the issue request and creates a pull request.
2. **Antigravity PR Reviewer** ([`.github/workflows/antigravity-pr-reviewer.yml`](.github/workflows/antigravity-pr-reviewer.yml)):
   - **Trigger:** Runs automatically on pull request events (`opened`, `synchronize`, `reopened`) or via comment `/review` on a pull request.
   - **Action:** Inspects PR changes, diffs, and comments, uses skills defined locally in `.agents/skills`, and leaves automated code quality and architectural review comments directly on the PR.

### Required GitHub Environment Configuration

To run these workflows, configure the following GitHub repository variables (`vars`) and permissions:

| Name | Type | Used by | Description |
|---|---|---|---|
| `WORKLOAD_IDENTITY_PROVIDER` | Repository Variable (`vars`) | Coder, PR Reviewer | Full resource name of the Google Cloud Workload Identity Federation provider used by `google-github-actions/auth`. |
| `GOOGLE_PROJECT_ID` | Repository Variable (`vars`) | Coder, PR Reviewer | Google Cloud Project ID where Vertex AI is enabled. |
| `GITHUB_TOKEN` | Automatic Secret (`secrets`) | Coder, PR Reviewer | GitHub Actions built-in token (requires `issues: write`, `pull-requests: write`, and `contents: write` permissions enabled). |
