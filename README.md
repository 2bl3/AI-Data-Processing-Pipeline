# NFL-Project
Large Scale Distributed Systems NFL Prediction Project

## Step 3: Source Metadata / JSON

Source file: games.csv

- Status code: 200 OK
- Content-Type: application/json; charset=utf-8
- SHA: edd002423fb0fd8498c1d6998932e0112e92f12d
- Download URL: https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv

An HTTP 200 response indicates that the request was successful. An unsuccessful
response could indicate that the resource could not be found, access was denied,
or the server encountered an error. Repeated requests should be limited to avoid
exceeding GitHub's public API rate limits.

## Step 4: Download and Inspect the game file / CSV
The "games.csv" file was downloaded using the "download_url" provided by
the metadata response and saved to "data/games.csv".

### Download Information

- Source version (SHA): edd002423fb0fd8498c1d6998932e0112e92f12d
- Local file: data/games.csv
- File size: 2.08 MB
- Retrieval Time: October 4, 2026 at 11:01:46 PM
- Total game records/Row Count: 7,548
- Total amount of Columns: 46

### Planned Columns

The initial processor will use the following columns from `games.csv`:

- `game_id` - unique game identifier
- `season` - NFL season number
- `game_type` - game type
- `week` - week of the season
- `gameday` - game date
- `away_team` - away team
- `away_score` - away team score
- `home_team` - home team
- `home_score` - home team score
- `overtime` - overtime indicator

## Step 5: Agree on a message contract

## Table

| Internal field | Type | Required? | Meaning | Source column |
|---|---|---|---|---|
| `game_key` | string | Yes | Unique identifier for the game | `game_id` |
| `contract_version` | string | Yes | Version of this message contract | Not from source |
| `source_version` | string | Yes | Version of the source data | Metadata `sha` |
| `season` | integer | Yes | NFL season | `season` |
| `game_type` | string | Yes | Type of game | `game_type` |
| `week` | integer | Yes | Week of the season | `week` |
| `kickoff_time` | datetime | Yes | Scheduled game date/time | `gameday`, `gametime` |
| `away_team` | string | Yes | Away team abbreviation | `away_team` |
| `home_team` | string | Yes | Home team abbreviation | `home_team` |
| `away_score` | integer/null | No | Final away-team score | `away_score` |
| `home_score` | integer/null | No | Final home-team score | `home_score` |
| `overtime` | boolean | Yes | Whether the game went to overtime | `overtime` |

## Score Representation

An unplayed game should have the value set to as "null" for both "away_score" and "home_score". Also, a missing score
will be represented as "null" since "0" is an actual score that can be achieved. 

The initial contract version is '1.0'.

## Step 6: Local Redis Setup

Redis was started locally using the Redis 7.2 Docker image.

- Redis version: 7.2
- Container ID: `98f63c976bd386f1c8121264f856b6ba8b84b7320a67b9a04a18b911f7ef8e57`
- Redis port: `6379`
- Stream name: `games`

Redis connectivity was verified using `redis-cli PING`, which returned `PONG`.
