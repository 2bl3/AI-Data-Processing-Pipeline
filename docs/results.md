# Actual execution results

The November 5, 2026 exercise used the existing verified November 3 snapshot, Git blob SHA `32e734a73d6403841a9742af3ae6f8ee2b98b38f`. GitHub metadata returned HTTP 200 and a newer SHA during the exercise. The training run deliberately retained the cached snapshot rather than mixing provenance. Full machine observations are in `evidence/system-run.txt`.

## Model evaluation

Training: 6,692 non-tied games from seasons before 2024, through February 11, 2024. Home wins comprise 56.62%. Held-out evaluation: 689 non-tied games in seasons 2024 onward through November 2, 2026, with 53.70% home wins. Ties are excluded from the binary evaluation. Sixteen tied completed games remain valid in storage and can contribute historical features. Model version: `logistic-67e898fa4058`.

| Model | Held-out accuracy | Brier score | Log loss |
|---|---:|---:|---:|
| Training-prior baseline | 0.537010 | 0.249482 | 0.692131 |
| Logistic regression | 0.624093 | 0.224817 | 0.639834 |

Accuracy counts correct binary winners. Brier score measures squared probability error, so lower is better. Log loss also rewards good probabilities and strongly penalizes confident mistakes. Logistic regression improves these metrics over this baseline on this split, but this does not establish reliability for future seasons. The model uses eleven simple pregame features and no injuries, weather forecasts, roster or quarterback inputs. It has not been probability-calibrated on an independent validation split. No hyperparameter search or selection against the held-out set was performed. The saved model remains trained only through the stated cutoff; the terminal prediction below uses later available historical results as features, without fitting on those later labels.

## Full pipeline and API

- A separate collector process published all 7,548 source games while the processor was stopped.
- A separate processor process accepted 7,397 completed games and excluded 151 scheduled games.
- One malformed JSON entry and one duplicate were injected. Final counts: seen 7,550 = accepted 7,397 + rejected 152 + duplicate 1. Redis group pending = 0, unread lag = 0.
- Real-service integration tests independently exercised delivered-but-unacknowledged recovery, two concurrent storage writers and transaction rollback.
- The live API accepted a valid request, rejected an invalid team with 422, returned 503 for a missing model and unreachable PostgreSQL store, and returned identical prediction content after restart.
- The observed EXPLAIN used `games_season_day`: index scan, 285 rows, 30 shared buffer hits, about 0.097 ms execution in that run. Timing is environment-specific. See the actual plan in system-run.txt.

Actual terminal output from the HTTP client:

```text
2026_10_WAS_NYG | 2026-11-12 | WAS at NYG | winner NYG | estimated probability 62.6% | logistic-67e898fa4058 | trained through 2024-02-11 | unscored snapshot matchup
```

This is an estimated probability conditional on a non-tied result, not certainty or demonstrated per-game accuracy. It reflects the supplied snapshot's schedule and available history, not a live injury or odds feed.

## Failure experiment table

| Action | Expected | Actual / pending | Decision |
|---|---|---|---|
| Request inaccessible local upstream URL | Request fails without publishing | Actual ConnectTimeout; cache unchanged; no new delivery | Fail explicitly, permit verified offline mode |
| Stop processor, publish full cache | Collector proceeds and backlog grows | 7,548 stream entries before consumer starts; drained to lag 0 | Redis buffers independent producer/consumer processes |
| Inject malformed JSON | Persist rejection, then ACK | Rejection reason recorded; pending 0 after drain | Invalid payload never becomes clean game |
| Publish accepted game again under new Redis ID | Persist duplicate, no extra game | Duplicate count 1; clean count remains 7,397 | Football game ID controls deduplication |
| Deliver to crashed worker before save | Entry remains pending and can be claimed | Real integration: pending 1 → 0 after XAUTOCLAIM | Default idle wait 60s; test uses 0 |
| Fail save/export before XACK | Entry not acknowledged | Automated tests verify xack never called | Retry from durable outcome if commit already succeeded |
| Fail related outcome insert | Roll back related game insertion | Real PostgreSQL test verifies game absent | Transaction protects related updates |
| Stop/restart API, remove model, break store URL | Stores continue; clear errors | Restart identical; missing model/store 503 | No fabricated fallback predictions |

## Corrections and remaining limitations

The first test run exposed a pandas NaN handling bug, corrected before the successful rerun. The first real PostgreSQL attempt exposed misuse of a connection context that closed the connection; explicit transaction contexts corrected it. Windows rejected port 5432, so PostgreSQL uses host port 55432. An evidence-runner SQL splitter initially treated a comment semicolon as a statement boundary; that comment was corrected and verification resumed without republishing the dataset. These are real debugging outcomes, not claims that every first attempt passed.

Features use a retrospective snapshot, not archived as-of source releases. First-valid-game-wins deduplication does not automatically apply later score corrections. Refreshing data for a revised training run should use a separately rebuilt store/group or an explicitly designed correction migration. One host remains a single failure domain. CSV export is single-writer and not an atomic pair of files; replay or an explicit export repairs snapshots from the authoritative committed ledger. `--once` does not wait for younger pending entries to age into eligibility. The feature builder scans history in memory and is intended for this small dataset, not a large league-wide event archive.

Final automated run: **25 passed**, including real Redis/PostgreSQL integration, with one upstream Starlette TestClient deprecation warning. See `evidence/tests.txt` for exact output. A prior final-run attempt hit Windows permissions in the system temp directory; the supplied runner creates isolated workspace temp paths. Pytest discovery is restricted to tests so saved evidence text is not collected as doctests. Required personal academic evidence is explicitly incomplete in academic-deliverables.md. Technical exports do not certify team participation or replace the instructor's demonstration.
