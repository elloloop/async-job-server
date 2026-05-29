# CLAUDE.md

## How I expect you to write code

**No shortcuts. "Simple" never means "sloppy."** A small diff that hardcodes,
duplicates, or skips a test isn't simpler — it's deferred cost.

1. **Fix causes, not symptoms.** Find the root cause before fixing. If you're
   applying a workaround, say so explicitly and explain why. Never swallow an
   exception or silence an error to make a problem disappear.

2. **Think about consequences.** Before changing shared or widely-used code,
   trace its callers and the invariants they rely on. A fix that's locally
   correct but breaks something elsewhere — now or later — is not a fix.

3. **SOLID, sensibly.** One responsibility per class/widget/function. Separate
   pure logic from I/O so it can be tested. Inject dependencies that cross a
   boundary so they're mockable. Don't add abstractions for things that don't
   cross a boundary.

4. **DRY about knowledge, not appearance.** Don't duplicate a rule or decision.
   Code that merely looks similar but changes for different reasons stays
   separate. When unsure, prefer duplication over a premature/wrong abstraction.

5. **No hardcoded values.** No magic numbers or strings inline — give them
   names. Environment/tenant/feature-specific values go in typed config in
   application code, never scattered literals, never the database.

6. **Readable & maintainable.** Clear names, short flat functions, early
   returns over deep nesting. Comments explain *why*, not *what*. Match the
   existing style of the file you're editing.

7. **Testable, and prove it.** Ship a test for behavior you add or change. If
   something is hard to test, that's a design smell — restructure until it
   isn't. "Works but can't be tested" means it isn't done.

A change is done only when: the cause (not a symptom) is fixed, no new hardcoded
values, a test covers it, and the analyzer/formatter are clean.

## Project facts

> Keep these current as the repo evolves; only write what you've confirmed.

- **Setup command:** `poetry install` (via `make install`)
- **Analyze/lint command:** `poetry run ruff check async_jobs/ tests/` (and `poetry run mypy async_jobs/`) — or `make lint` / `make type-check`
- **Test command (all):** `make test` (runs `test-unit` then `test-integration`); unit only: `poetry run pytest tests/unit/`
- **Test command (single file/test):** `poetry run pytest tests/unit/test_foo.py::TestClass::test_case -v`
- **Format command:** `poetry run black async_jobs/ tests/` (then `poetry run ruff check --fix`) — or `make format`; CI gate is `black --check`
- **Run an app:** `poetry run python examples/example_app.py` (FastAPI), plus `examples/run_scheduler.py` and `examples/run_worker.py --queue <url> --handlers-module <mod>`; full stack via `docker-compose up`
- **Repo layout:** `async_jobs/` is the library package (config, store, service, scheduler, worker, fastapi_router, registry, handlers, http_client, ddl, models, errors); `tests/unit` + `tests/integration`; `examples/` runnable demos; `Dockerfile.{scheduler,worker,test}` + `docker-compose.yml` for local stack
- **State management / data layer:** PostgreSQL is the job store (single `jobs` table, see `async_jobs/ddl.py`) accessed via async `asyncpg` pools; SQS (AWS, LocalStack-emulated locally) is the message transport; deadline/lease-based scheduling; multi-tenant with per-tenant quotas; config comes from `AsyncJobsConfig.from_env()` reading `ASYNC_JOBS_*` env vars
- **Generated files NOT to hand-edit:** `poetry.lock` (regenerate via Poetry); coverage artifacts (`coverage.xml`, `.ruff_cache/`, `.pytest_cache/`)
- **Other gotchas:** Python 3.11, async-first (`pytest asyncio_mode = "auto"`); line length 100 for both Black and Ruff; integration tests need Docker (LocalStack + Postgres) and run only `tests/integration/test_e2e_flow.py`; the DDL in `ddl.py` is the schema source of truth (no migration tool); SQS endpoint overridden locally via `AWS_ENDPOINT_URL`
