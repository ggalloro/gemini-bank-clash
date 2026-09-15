# Gemini Bank — Microservices

A small **sample** online bank, decomposed into four services that communicate
over HTTP/JSON. Three are Python/Flask; the **ledger** is Java / Spring Boot 3.

> All data is synthetic. No real credentials, accounts, or anything sensitive.

## Architecture

```
                ┌──────────────┐
   browser ───▶ │   frontend   │  :8080  (UI only, no DB)
                └──────┬───────┘
            ┌──────────┼───────────────┐
            ▼          ▼               ▼
     ┌────────────┐ ┌────────────┐ ┌──────────────┐
     │   users    │ │   ledger   │ │  statements  │
     │   :8081    │ │   :8082    │ │    :8083     │
     │  users.db  │ │ ledger.db  │ │   (no DB)    │
     └────────────┘ └─────┬──────┘ └──────┬───────┘
                          └───── REST ────┘
                       (statements reads from ledger)
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

**Database-per-service:** no service ever opens another service's database file.
Cross-service reads go over HTTP.

**Auth:** the users service mints a JWT (HS256) signed with the shared
`TOKEN_SECRET` carrying `user_id` and `full_name`; the frontend forwards it as
`Authorization: Bearer <token>`; the Java ledger validates the signature with
the same secret.

## Repository layout

```
gemini-bank-clash/
├── docker-compose.yml
├── seed.py
├── frontend/     # Python/Flask — UI only, no DB
├── users/        # Python/Flask — identity; mints JWTs
├── ledger/       # Java / Spring Boot 3 — money
├── statements/   # Python/Flask — read-only reporting
├── .agents/      # Antigravity project configuration
│   ├── agents/   # Custom subagents (contract-guardian, go-modernizer, java-qa, python-qa, go-qa)
│   ├── skills/   # Standard operating procedures (service-modernization, code-review)
│   ├── hooks/    # PreToolUse guardrails (block-destructive-ops)
│   └── hooks.json
└── .github/      # CI/CD and automation
    ├── workflows/# Antigravity Coder & PR Reviewer workflows
    └── scripts/  # Runner scripts for autonomous tasks
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

### Running a second stack (per-service ports & shared volumes)

Published host ports are env vars with defaults (`FRONTEND_PORT` 8080,
`USERS_PORT` 8081, `LEDGER_PORT` 8082, `STATEMENTS_PORT` 8083); container ports
never change. In addition, SQLite database volumes (`users-data` and `ledger-data`)
are configurable via `USERS_VOLUME` and `LEDGER_VOLUME` (defaulting to
`gemini-bank_users-data` and `gemini-bank_ledger-data`).

This enables running isolated Git worktree stacks on offset ports (e.g. `9080` / `9083`)
while mounting the same pre-seeded database volumes without reseeding:

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

## Antigravity Assets: Subagents, Skills & Hooks

This repository is configured for agentic pair-programming and autonomous workflows using [Google Antigravity](https://cloud.google.com/products/gemini/antigravity). Rather than maintaining drift-prone requirements documents or giving a single AI agent root access to both application code and test assertions, this repository defines strict role boundaries, tool isolation, and codified standard operating procedures directly under `.agents/`.

### 1. Specialized Subagents (`.agents/agents/`)

Subagents run in their own isolated execution context with specialized system prompts and restricted toolsets:

| Subagent | Manifest | Role & Constraints | Invoked When |
|---|---|---|---|
| `@contract-guardian` | [`contract-guardian.md`](.agents/agents/contract-guardian.md) | **Read-only contract recorder.** Probes the running legacy Python service, captures live HTTP response bodies verbatim as golden JSON fixtures, and writes automated characterization tests in Python. **Strictly forbidden from modifying Go code.** | Phase 1 of service modernization, before any re-platforming starts. |
| `@go-modernizer` | [`go-modernizer.md`](.agents/agents/go-modernizer.md) | **Modernization engineer.** Re-implements the service in Go and containerizes it in Docker. Guided strictly by the characterization test suite until 100% of fixtures pass. **Strictly forbidden from modifying test assertions or writing temporary test runners.** | Phase 2 of service modernization, after fixtures are locked. |
| `@java-qa` | [`java-qa.md`](.agents/agents/java-qa.md) | **Java/Spring Boot QA engineer.** Specialized in building and testing the `ledger` service (`mvn test`). Executes JUnit and MockMvc suites in an isolated context. | Integration and PR verification on `main`. |
| `@python-qa` | [`python-qa.md`](.agents/agents/python-qa.md) | **Python QA engineer.** Specialized in executing pytest suites across Python services (`users`, and new services like `fraud`). | Verification of Python services and integration on `main`. |
| `@go-qa` | [`go-qa.md`](.agents/agents/go-qa.md) | **Go QA engineer.** Specialized in verifying Go services (`go test`, Docker builds, characterization assertions). | Post-modernization verification and integration on `main`. |

#### Multi-Specialist Parallel QA Verification
During multi-branch integration on `main`, the lead agent does not run monolithic, sequential test passes. Instead, it dispatches `@java-qa`, `@python-qa`, and `@go-qa` concurrently to verify their respective services in parallel:
```
                     ┌──▶ @java-qa    ──▶ ( cd ledger && mvn test )
Lead Agent (main) ───┼──▶ @python-qa  ──▶ ( cd users && pytest ) + ( cd fraud && pytest )
                     └──▶ @go-qa      ──▶ ( cd statements && pytest tests/ )
```

### 2. Standard Operating Procedures / Skills (`.agents/skills/`)

Skills are on-demand procedures loaded by Antigravity agents into their reasoning context:

* **`service-modernization`** ([`SKILL.md`](.agents/skills/service-modernization/SKILL.md)): Clean-room modernization playbook. Codifies:
  - Fast planning protocol (zero initial probing during plan formulation).
  - Strict clean-room delegation sequence (`@contract-guardian` -> `@go-modernizer`).
  - Worktree port offset conventions (`:9080` / `:9083`) and automated database volume sharing.
  - Definition of Done: 100% pass rate on characterization assertions against the offset container port.
* **`code-review`** ([`SKILL.md`](.agents/skills/code-review/SKILL.md)): Automated architectural and security guidelines. Enforces database-per-service isolation, authentication boundaries (HS256 JWT validation), and test coverage for new code paths. Used by the PR reviewer bot.

### 3. Safety Guardrails (`.agents/hooks/`)

* **`PreToolUse` Safety Gate** ([`hooks.json`](.agents/hooks.json) + [`block-destructive-ops.sh`](.agents/hooks/block-destructive-ops.sh)): Intercepts all command execution requests before they reach the shell. Automatically denies destructive or irreversible operations:
  - Force-pushing to git (`git push --force`)
  - Hard reset of working branches (`git reset --hard`)
  - Broad destructive file removals (`rm -rf /`, `rm -rf ~`, `rm -rf *`)
  - Unsafe privilege escalations (`chmod 777`)
  - Arbitrary remote script execution (`curl | bash`, `wget | sh`)

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
