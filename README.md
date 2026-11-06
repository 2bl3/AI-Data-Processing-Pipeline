# NFL Prediction Project — CYB3023 Weeks 6–8

Python collector → Redis Streams → independent validator/processor → PostgreSQL → pregame feature builder → baseline and logistic model → separate FastAPI service → terminal predictions. There is no frontend. Message contract v1.0 and stream `nfl:games:v1` are preserved.

The technical implementation and evidence are in this repository. Personal/team submission items remain: private repository URL, reviewed final commit IDs, real contribution statements, weekly AI logs, and live demonstration. See [academic deliverables](docs/academic-deliverables.md). No commits or pushes were made. Base commit before these uncommitted changes: `df83300ac8fd4cc3a946b89c4540af54c2c96a9a`; this is not the final submission identifier.

## Fresh setup in Windows PowerShell

Use Python 3.14 and Docker Desktop with Linux containers. Start Docker Desktop, then run from the repository root. Other Python versions may work but the supplied lock records the tested environment. The ZIP omits the full CSV; the first collector run retrieves it.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
# Or use requirements.txt for compatible dependency ranges.
$env:POSTGRES_PASSWORD = 'choose-a-local-development-password'
$env:POSTGRES_PORT = '55432'
$env:REDIS_HOST = '127.0.0.1'
# URL-encode special characters if your password contains them.
$env:DATABASE_URL = "postgresql://nfl:$($env:POSTGRES_PASSWORD)@127.0.0.1:55432/nfl"
docker compose up -d
docker compose exec -T redis redis-cli PING
docker compose exec -T postgres pg_isready -U nfl -d nfl
```

Port 55432 avoids a Windows bind failure observed on 5432. Wait for `accepting connections` before continuing. Redis and PostgreSQL bind to loopback and persist to Docker named volumes. The password is supplied through your environment; do not commit credentials. Environment variables are per terminal: repeat the Redis and database settings in every component terminal. The one verification run used an isolated, local-only development password; replace it for your own setup.

## Ingest, train and predict

These are separate executable processes, not functions running in one application. On the first run, omit `--offline` to retrieve metadata and CSV. With this repository's existing verified cache, use `--offline` to reproduce the recorded evaluation instead of replacing its snapshot.

```powershell
# Terminal A: collector exits after publication. --all-* explicitly overrides sample defaults.
python -m collector.collector --all-seasons --all-records
# Subsequent reproducible runs:
python -m collector.collector --offline --all-seasons --all-records

# Terminal B with DATABASE_URL and REDIS_HOST set:
python -m processor.processor --consumer worker-1
# Ctrl+C stops it. For batch demonstrations instead:
python -m processor.processor --consumer worker-1 --once

# After ingestion completes, in another terminal with DATABASE_URL:
python -m nfl.cli counts
python -m nfl.cli export
python -m nfl.cli features
python -m nfl.cli train --test-season 2024

# Terminal C with DATABASE_URL and REDIS_HOST set:
python -m uvicorn nfl.api:app --host 127.0.0.1 --port 8000

# Terminal D, with the same virtual environment:
python -m nfl.cli evaluate
python -m nfl.cli predict --season 2026 --week 10
python -m nfl.cli predict --season 2026 --week 10 --home NYG --away WAS
```

The selected-matchup example is subject to the schedule actually present in your snapshot. If it is absent, use the whole-week command or select another known matchup; no schedule is invented. Responses identify the date, matchup, model, training cutoff and estimated probability. Historical games after the model cutoff may be replayed and are explicitly labeled. Requests on or before the cutoff are rejected. The saved 2024-split model is deliberately frozen for evaluation; it has not been retrained on the held-out seasons.

The cache can be refreshed by running the collector online. A newer snapshot can change scores, schedules and evaluation. `source_manifest.json` and the model metadata record the actual versions. Cached schedule context must be present even when prediction history comes from PostgreSQL.

For the Week 6 staging-only demonstration, leave DATABASE_URL unset and use a small sample:

```powershell
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
python -m collector.collector --offline --season 2024 --limit 5
python -m processor.processor --once --export
```

This uses the local SQLite durable ledger, generating `data/staging/games_clean.csv` and `rejections.jsonl`. Use a fresh project Redis group/store for an independent Week 6 demonstration; an already-consumed group will retain its progress. Week 7 requires PostgreSQL and setting DATABASE_URL again. Do not switch stores behind an already-consumed group and expect messages to redeliver automatically.

If Docker is unavailable, explicit offline experiments are available:

```powershell
python -m nfl.cli train --cache --test-season 2024
$env:PREDICTION_USE_CACHE = '1'
python -m uvicorn nfl.api:app --host 127.0.0.1 --port 8000
```

That mode validates the cached source directly and is not evidence of the required distributed storage path. Leave PREDICTION_USE_CACHE unset for the assignment's PostgreSQL-backed workflow.

## Verification and failure demonstrations

```powershell
python -m pytest -q
# If Windows temp/cache permissions differ across sessions, use the isolated runner:
python -m scripts.run_tests
# Real local Redis and PostgreSQL; set connection variables as above first:
$env:RUN_INTEGRATION = '1'
python -m pytest -q -s
python -m scripts.run_tests --integration
# Full publication while processor is stopped, then ingestion, queries, training, API/CLI:
python -m scripts.verify_system
```

The integration test creates and removes only its own random stream and PostgreSQL schema. The full verification script uses the project's normal stores, appends deliveries and records duplicate outcomes on reruns. It starts and stops only its own API process; port 8000 must be free. It intentionally exercises actual source connection failure, malformed JSON, duplicates, backlog, API input errors, missing model, unavailable store and service restart. Tests also cover cache corruption, field types, persistence failure before XACK, replay and target leakage. `--claim-idle-ms 0` is used in controlled recovery tests; normal workers wait 60 seconds before claiming.

See [actual execution evidence](docs/evidence), [requirements audit](docs/requirements.md), [architecture and distributed-system analysis](docs/architecture.md), [source and feature map](docs/field-map.md), [message contract](contracts/message-contract.md), [SQL queries](sql/queries.sql), and [evaluation interpretation](docs/results.md).

The features command persists `artifacts/training.csv` and a small `data/training_sample.csv`. Train writes preprocessing and estimator to `artifacts/model.joblib` and its metadata/metrics to `artifacts/evaluation.json`. Never load joblib files from untrusted sources. Prediction persistence is not required by the rubrics; requests return model-generated results without storing a new prediction table.

## API and errors

```powershell
$body = @{home_team='NYG'; away_team='WAS'; season=2026; week=10} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/predict -ContentType 'application/json' -Body $body
Invoke-RestMethod http://127.0.0.1:8000/evaluation
```

POST `/predict` requires two recognized teams, season and week, with a unique matchup in the verified snapshot. Unknown fields/types/ranges or games before the model cutoff return 422. Missing matchups return 404. Missing model, corrupted schedule or unavailable/empty history store return 503. `/health` reports process liveness and model file presence; it is not a database readiness guarantee. CLI network/API errors print an explanation and return a nonzero exit code. Set MODEL_PATH to choose a saved artifact. Collector and processor use REDIS_HOST/REDIS_PORT; the storage component uses DATABASE_URL. Defaults are localhost:6379 and the Week 6 local ledger.

## Stop and package

Stop processor and API with Ctrl+C. Collector, exporter, feature builder and trainer exit on completion.

```powershell
docker compose stop
# Or remove containers/network while retaining named data volumes:
docker compose down
python -m scripts.package_submission --team TeamName
```

Do not use `down -v` unless you deliberately intend to destroy project store volumes. ZIPs are created in `submissions/` with the required Week6/Week7/Week8 names. They contain the integrated current source, contract, schema, retrieval code, small samples, evidence and saved model, excluding the full CSV, full staging table, virtual environment and dependency caches. Add your actual repository URL, final committed identifier and personal evidence before submission. They are exports of this integrated implementation, not fabricated historical snapshots of separate weekly work.

One game travels as verified CSV bytes tied to a Git blob SHA, then as a contract JSON payload under a Redis delivery ID. The processor validates its football game ID, commits one clean game and a delivery decision, then acknowledges. The feature builder reads earlier validated games to form eleven pregame values; the trainer learns only from seasons before the split. FastAPI finds the requested snapshot matchup, constructs those same pregame values from history, loads the saved model and returns the probability the terminal prints.
