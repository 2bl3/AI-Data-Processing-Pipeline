# Audit and implementation plan

The two supplied HTML documents contain the standalone Week 6 instructions and the combined Weeks 6–8 instructions. There is no separate third HTML supplied. The combined document defines both later milestones. The user requests terminal interaction and explicitly retains the required API.

Initial audit: collector implements metadata, verified cache, bounded retries, contract mapping and publishing. Processor only checks a few fields and acknowledges without persistence. PostgreSQL, features, models, API, tests, failure evidence and submission packaging were missing. README describes an obsolete proposed contract; `contracts/message-contract.md` is authoritative v1.0.

Implementation sequence:
1. Preserve collector and contract; implement exhaustive validation, durable outcome ledger, staging export and pending recovery.
2. Add PostgreSQL schema, transactional idempotency, query examples and concurrency tests.
3. Build chronological features from validated records with conservative date boundaries; train baseline and classifier.
4. Serve saved model through FastAPI and terminal client; exercise failures and document actual results.
5. Package milestone exports; identify personal academic deliverables without fabricating them.

## Rubric mapping

| Week / points | Requirement | Implementation / evidence |
|---|---|---|
| 6 / 20 | Architecture, investigation, field map, contract | architecture.md, field-map.md, existing message-contract.md |
| 6 / 20 | Collector and provenance | collector/collector.py; collector tests; source_manifest.json |
| 6 / 20 | Separate stream consumer and safe acknowledgment | processor/processor.py; durable ledger and recovery tests |
| 6 / 20 | Validation, duplicates, staging | nfl/validation.py, nfl/storage.py; tests |
| 6 / 20 | Four failures, AI log, individual explanation | evidence and academic-deliverables.md; personal evidence outstanding |
| 7 / 25 | PostgreSQL constraints, idempotency, transaction | sql/schema.sql, nfl/storage.py; integration tests |
| 7 / 15 | Redis comparison and concurrency | architecture.md; integration tests |
| 7 / 20 | Queries, EXPLAIN, index, partition plan | sql/queries.sql; architecture.md; observed index scan in evidence/system-run.txt |
| 7 / 25 | Eight features, leakage prevention | nfl/features.py; leakage tests; feature definitions |
| 7 / 15 | Reproducibility and individual evidence | README; academic-deliverables.md |
| 8 / 25 | Chronological baseline/classifier evaluation | nfl/model.py; generated evaluation.json |
| 8 / 20 | Model provenance and reproducibility | saved metadata; explicit feature allowlist |
| 8 / 20 | Separate API and input handling | nfl/api.py, nfl/cli.py; API tests |
| 8 / 20 | Integration, failures, distributed analysis | tests; evidence; architecture.md |
| 8 / 15 | Documentation and individual demonstration | README; personal deliverables remain |

Implementation entries indicate locations, not a claim that unexecuted tests passed. See evidence for actual execution status.

## Final completion status

| Milestone | Technical status | Outstanding human requirements |
|---|---|---|
| Week 6 | Implemented and tested: collector, separate Redis processor, full v1.0 validation, durable outcomes/exports, duplicates, restart recovery, all four failures | Real owners/contributions, weekly AI interactions, teammate fresh-run demonstration, repository URL/final commit |
| Week 7 | Implemented and tested: PostgreSQL constraints/transaction, concurrent writers, three queries and observed EXPLAIN, partition design, eleven pregame features and leakage check | Weekly AI interactions, individual statements and live feature trace |
| Week 8 | Implemented and tested: chronological baseline/classifier, saved model/provenance, separate API and terminal client, invalid/unavailable/restart demonstrations | Weekly AI interactions, individual statements, reviewed final commit and live demonstration |

Final automated run: 25 passed, with one upstream TestClient deprecation warning. The real-service exercise used Docker Redis 7.2 and PostgreSQL 17. All technical metrics and sample output are in results.md. The ZIPs are reviewable technical exports; personal/team requirements prevent describing them as fully submission-ready.
