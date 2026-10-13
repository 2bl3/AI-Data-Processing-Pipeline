# NFL Game Message Contract — Version 1.0

Save this file as `contracts/message-contract.md`. The collector and processor follow this agreement so they can be built independently.

## 1. How the programs communicate

The collector reads the NFL CSV, selects the fields below, and publishes one JSON message per game. Redis holds the messages while the processor reads, checks, and saves them.

| Setting | Value | What it means |
|---|---|---|
| Redis address | `localhost:6379` | Python connects to Redis on the same computer through the published Docker port. |
| Stream name | `nfl:games:v1` | The named stream containing our game messages. |
| Entry field | `payload` | The field inside each stream entry that holds one game's JSON text. This is not a filename. |
| Consumer group | `processors` | Tracks message delivery and acknowledgments for our processors. |
| Consumer name | `worker-1` | Identifies a running processor. Use a different name for each worker connected to the same group. |
| Accepted output | `data/staging/games_clean.csv` | Valid completed games, ready for the next milestone. |
| Rejection output | `data/staging/rejections.jsonl` | One JSON line per rejected or duplicate outcome, with its reason. |

Redis also generates a unique **stream entry ID** for every published message. That ID identifies a delivery entry; `game_id` identifies the football game. The same game can be published again under a different stream ID.

The processor creates the group at stream ID `0` if the group does not exist. This lets it read games published before it started. An existing group keeps its progress when the processor restarts.

For local integration testing, run the collector, processor, and Redis on the same computer. Each teammate can run their own copy of the full pipeline. GitHub shares code, not Redis messages. If Python later runs inside another container, use a reachable Redis service name on a shared Docker network; that container's `localhost` refers to itself.

## 2. Fields in each JSON message

**Every field below must be included.** “Or null” means a missing source value is allowed, but the field still appears. Numbers must be JSON integers, not quoted strings, decimals, or booleans.

| Field | Type | Source / rule |
|---|---|---|
| `contract_version` | string | Always `"1.0"`; our message format version. |
| `source_version` | string | GitHub file SHA matching the downloaded CSV; a Git blob SHA, not a repository commit ID. |
| `source_reference` | string | HTTPS URL identifying the nflverse source file. |
| `retrieved_at` | string | CSV retrieval time in ISO 8601 format with timezone, preferably UTC. |
| `game_id` | string | CSV `game_id`; preserve the original unique game key. |
| `season` | integer | CSV `season`; 1999–2100. |
| `game_type` | string | CSV `game_type`; `REG`, `WC`, `DIV`, `CON`, or `SB`. |
| `week` | integer | CSV `week`; 1–22. |
| `gameday` | string | CSV `gameday`; valid `YYYY-MM-DD` date. |
| `gametime` | string or null | CSV `gametime`; valid 24-hour `HH:MM` time. |
| `kickoff_timezone` | string | Always `"America/New_York"`. |
| `away_team` | string | CSV `away_team`; recognized team code. |
| `home_team` | string | CSV `home_team`; recognized code, different from away team. |
| `away_rest` | integer or null | CSV `away_rest`; nonnegative rest days. |
| `home_rest` | integer or null | CSV `home_rest`; nonnegative rest days. |
| `div_game` | integer or null | CSV `div_game`; `0` or `1`. |
| `location` | string or null | CSV `location`; `Home` or `Neutral`. |
| `away_score` | integer or null | CSV `away_score`; nonnegative score. |
| `home_score` | integer or null | CSV `home_score`; nonnegative score. |
| `status` | string | Derived from scores using the rules below. |

Use the snapshot's original retrieval time and version, including when reading a cached CSV. Do not pair an old CSV with a newly fetched SHA.

## 3. Missing values and game status

- A blank nullable CSV cell becomes JSON `null`, not `0`, `"null"`, or an empty string.
- Both scores present → `completed`.
- Neither score present → `scheduled`.
- Only one score present → `incomplete`.
- A score of **zero counts as present**. Equal scores are a valid tie.
- Missing game time stays null; do not invent midnight. Date, time, and timezone together describe kickoff.
- `scheduled` means “no scores in this snapshot.” It does not prove the game was not canceled or postponed.
- An unexpected nonnumeric value in a numeric source field is a collector error: log it rather than silently turning it into null. Invalid messages can be injected separately for processor tests.

## 4. What the processor does

1. Read `payload` and parse its JSON text into a Python dictionary.
2. Reject invalid JSON, non-object messages, missing/unknown fields, unsupported contract versions, wrong types, or invalid field values.
3. Check that the retrieval timestamp has a timezone and that game dates fall in the season year or following year.
4. Trim and uppercase team codes, then apply the historical aliases below. Check that the game key's season, week, and teams agree with the message. Keep the original game key.
5. Check that status matches score availability. Only valid completed games enter the clean CSV. Log scheduled/incomplete games as rejected/excluded with a reason. Missing nullable pregame fields alone do not reject a completed game.
6. Accept each `game_id` only once. Log later valid deliveries as `duplicate`; do not overwrite the accepted game. An invalid message must not prevent a corrected message from being accepted later.
7. Save the outcome safely, **then acknowledge the Redis entry**. If saving fails, leave it unacknowledged.

Recognized canonical codes:

`ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LV LAC LA MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS`

Historical aliases: `OAK → LV`, `SD → LAC`, `STL → LA`, `LAR → LA`, `JAC → JAX`, `WSH → WAS`. These group historical locations under the same franchise; the original source/game ID retains the era-specific code.

## 5. Outputs and restart behavior

- Clean CSV: contract fields plus `stream_id`. Write null values as empty CSV cells.
- Rejection log: `stream_id`, `game_id` when available, `decision` (`rejected` or `duplicate`), and a clear `reason`.
- Keep duplicate protection and recorded stream outcomes across restarts. The processor owner chooses and documents how to persist them.
- On restart, recover pending messages, including those assigned to a crashed worker. Document how they are claimed and the idle wait used before claiming.
- Reprocessing the **same stream ID** must not add another row, outcome, or count. A **new stream ID** for an accepted game is a duplicate outcome.
- Count distinct stream IDs with safely recorded outcomes: **seen = accepted + rejected + duplicate**. Rejected excludes duplicates.
- Use one processor writing these CSV files in Week 6. Concurrent writers and database constraints come in Week 7.

Unread means not yet delivered to a worker. Pending means delivered but not acknowledged. Acknowledgment records group progress; it does not delete the stream entry. Stream length therefore does not equal backlog.

## 6. Example payload

This uses a real game from the inspected CSV. Replace the two provenance placeholders with the actual snapshot SHA and retrieval timestamp before using it as a valid test message.

```json
{
  "contract_version": "1.0",
  "source_version": "REPLACE_WITH_SNAPSHOT_SHA",
  "source_reference": "https://github.com/nflverse/nfldata/blob/master/data/games.csv",
  "retrieved_at": "REPLACE_WITH_ISO8601_RETRIEVAL_TIME",
  "game_id": "1999_01_MIN_ATL",
  "season": 1999,
  "game_type": "REG",
  "week": 1,
  "gameday": "1999-09-12",
  "gametime": null,
  "kickoff_timezone": "America/New_York",
  "away_team": "MIN",
  "home_team": "ATL",
  "away_rest": 7,
  "home_rest": 7,
  "div_game": 0,
  "location": "Home",
  "away_score": 17,
  "home_score": 14,
  "status": "completed"
}
```

## 7. Keep these boundaries clear

Scores and status are outcome/processing data, not prediction inputs for that same game. IDs and source metadata support tracing, not default model features. The later feature builder will explicitly choose pregame inputs and check that their information was available before kickoff.

The names and policies here are our proposed team choices. Both owners should agree before coding. Change the contract version when changing fields, types, or meanings; processors reject unsupported versions.
