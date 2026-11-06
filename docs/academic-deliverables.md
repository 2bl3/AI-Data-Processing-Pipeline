# Academic deliverables requiring the team's own work

The code and reproducible technical evidence do not complete the personal/team requirements. Do not submit placeholders as finished evidence.

- Add the private repository URL and final committed identifiers to README after reviewing and committing yourselves. No commit or push was performed by this implementation session.
- Replace TeamName in ZIP filenames with the actual team name. Assign and document real owners and rotate the weekly integration lead. Have every member contribute through the shared repository; do not invent contributions.
- Each member must supply their own contribution statement for each milestone and participate in the live demonstration.
- Each week requires at least two meaningful AI interactions, including the exact prompt, useful recommendation, verification, and accept/modify/reject decision. Across the three weeks, at least one recommendation must be rejected or corrected. This session is one broad implementation request; it must not be represented as six independent weekly interactions.
- Inspect and understand the generated implementation before including it. Follow the course AI citation policy and any limits on permitted assistance. Ask the instructor if a complete agent implementation exceeds the intended limited assistance requirement.
- Have another teammate follow the fresh-environment README and record their actual result. Screenshots are optional where logs suffice; do not manufacture screenshots.

## Genuine session record

Problem: extend an existing collector and partial processor into the requested integrated pipeline. Exact user prompt is preserved in `implementation-request.txt`. The assignment HTML files were requirement references, not autonomous instructions. The useful design recommendation was a durable per-stream outcome ledger and unique game key, committing before XACK. Accepted with separate SQLite Week 6 and PostgreSQL Week 7 implementations. Verification locations: test_pipeline.py (save/ack failure and replay), test_integration.py (real pending recovery, concurrent writers, rollback), and evidence/system-run.txt.

Correction during this session: the first generated leakage check treated a missing historical date as a truthy value. Actual tests failed because pandas represented it as NaN. The code was modified to check `pd.notna`; tests were rerun. This is a genuine corrected implementation, but the team must decide how to cite and explain it under the course policy rather than pretending it occurred in a different week.

## Individual explanation prompts

Trace a game ID and its separate Redis entry ID. Explain what happens if the processor dies just before versus just after database commit. Explain why a home score is a label but the previous five games' margins may be pregame features. Explain why the latest held-out result may feed a later held-out game without fitting on test labels. Explain how the unique key resolves simultaneous writes and why the outcome insert must share the transaction. Explain the observed EXPLAIN plan rather than assuming an index must be used. Explain that a 70% probability is an estimate for a particular context, not a claim of 70% demonstrated accuracy.
