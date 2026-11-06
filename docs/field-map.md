# Source investigation and pregame field map

GitHub's contents endpoint returns JSON metadata (`sha`, `download_url`, size), not games. The second HTTPS request downloads CSV bytes. The collector computes `SHA1("blob " + byte_length + NUL + bytes)` and compares the Git blob SHA, then records status codes and UTC retrieval time. HTTP errors can mean rate limits, denied access, missing resources or upstream failures. Do not repeatedly download for tests; use `--offline` after verification.

The contract lists every transmitted field, including null rules and aliases. Redis stream IDs identify deliveries; `game_id` identifies a game. The original game key is retained even when team names are normalized.

| Candidate pregame variable | Source | Availability / use |
|---|---|---|
| Season | season | Context, chronological split |
| Week | week | Model feature |
| Home team | home_team | Context and historical lookup |
| Away team | away_team | Context and historical lookup |
| Kickoff date | gameday | Historical cutoff |
| Kickoff time | gametime | Nullable; excluded from model |
| Home rest | home_rest | Model feature; median imputation if absent |
| Away rest | away_rest | Model feature; median imputation if absent |
| Division matchup | div_game | Model feature; median imputation if absent |
| Neutral field | location | Model feature; nullable |
| Home recent win rate | Earlier completed games | Last five franchise games, tie counts as half win |
| Away recent win rate | Earlier completed games | Same rule |
| Home recent margin | Earlier completed scores | Mean margin in last five |
| Away recent margin | Earlier completed scores | Same rule |
| Home/away history counts | Earlier completed games | Two features, capped at five |
| Pregame injuries | Not in selected contract | Unavailable; not invented |
| Forecast weather at kickoff | Not in selected contract | Unavailable; actual weather is not a forecast |

The model has eleven numeric features, explicitly allowlisted in `nfl/features.py`. Neither scores, game status, IDs nor source metadata enter the estimator. Scores label completed games: home win = 1, away win = 0. Tied games contribute historical half wins but are excluded from the binary target; probabilities are conditional on a non-tied result. Scheduled/incomplete games are excluded from staging and training, but can supply verified schedule context for requests.

History crosses seasons and uses the latest five games with source dates strictly earlier than the day before the target. This conservatively excludes same-day and previous-day results without inventing final-whistle times. No-history means null rates/margins plus zero counts. Median imputation and scaling fit only training rows. The held-out season evaluation permits earlier test-game results as history for later test games, matching sequential operation; it does not refit the model on test labels.

The source is a retrospective snapshot. Rest, schedule and venue are treated as pregame facts, but historical as-of releases are unavailable. Corrections, postponements and source gaps can affect a backtest. The system cannot prove when every source cell was first published. The two-day historical result boundary is conservative, not a complete remedy for retrospective revisions. Missing future schedules produce errors rather than invented matchups.
