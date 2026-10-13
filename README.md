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
