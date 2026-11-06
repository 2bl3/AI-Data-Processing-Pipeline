
"""
NFL Game Data Collector
CYB3023 - NFL Data Pipeline

Responsibilities:
1. Retrieve GitHub file metadata
2. Cache the historical games CSV
3. Parse and standardize game records
4. Publish records to a Redis Stream
"""

import argparse
import csv
import hashlib
import json
import logging
import os
import tempfile

from datetime import datetime, timezone
from pathlib import Path

import requests
import redis

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# --------------------------------------------------
# Configuration
# --------------------------------------------------

API_URL = (
    "https://api.github.com/repos/nflverse/nfldata/"
    "contents/data/games.csv"
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

CSV_PATH = DATA_DIR / "games.csv"
MANIFEST_PATH = DATA_DIR / "source_manifest.json"

STREAM_NAME = "nfl:games:v1"
CONTRACT_VERSION = "1.0"
SOURCE_REFERENCE = "https://github.com/nflverse/nfldata/blob/master/data/games.csv"
KICKOFF_TIMEZONE = "America/New_York"

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

HTTP_TIMEOUT = (5, 30)
MAX_RETRIES = 3


# --------------------------------------------------
# Logging and HTTP setup
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


def create_http_session():
    """Create an HTTP client with bounded retries."""

    session = requests.Session()

    retry_policy = Retry(
        total=MAX_RETRIES,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(max_retries=retry_policy)

    session.mount("https://", adapter)

    return session


# --------------------------------------------------
# GitHub metadata
# --------------------------------------------------

def fetch_metadata(session):
    """Request information about the source CSV."""

    logger.info("Requesting GitHub metadata")

    response = session.get(
        API_URL,
        timeout=HTTP_TIMEOUT,
        headers={"Accept": "application/vnd.github+json"},
    )

    logger.info(
        "GitHub metadata HTTP status: %s",
        response.status_code
    )

    response.raise_for_status()

    metadata = response.json()

    if not isinstance(metadata, dict) or not metadata.get("sha") or not metadata.get("download_url"):
        raise ValueError("GitHub metadata is missing required fields")

    return metadata, response.status_code


# --------------------------------------------------
# Cache management
# --------------------------------------------------

def load_manifest():
    """Read the previously saved source manifest."""

    if not MANIFEST_PATH.exists():
        return None

    try:
        with MANIFEST_PATH.open("r", encoding="utf-8") as file:
            manifest = json.load(file)
            if not isinstance(manifest, dict):
                raise ValueError("Manifest must be a JSON object")
            return manifest

    except (OSError, ValueError) as error:
        logger.warning("Unable to read manifest: %s", error)
        return None


def git_blob_sha(content):
    """Calculate the Git blob SHA-1 for downloaded bytes."""

    header = f"blob {len(content)}\0".encode("utf-8")
    return hashlib.sha1(header + content).hexdigest()


def save_json_atomic(path, data):
    """Write JSON using a temporary file before replacement."""

    temporary_path = path.with_name(path.name + ".tmp")

    try:
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

        os.replace(temporary_path, path)

    finally:
        temporary_path.unlink(missing_ok=True)


def download_csv(session, metadata):
    """Download and verify a new CSV snapshot."""

    logger.info("Downloading games.csv")

    response = session.get(
        metadata["download_url"],
        timeout=HTTP_TIMEOUT,
    )

    logger.info(
        "CSV download HTTP status: %s",
        response.status_code
    )

    response.raise_for_status()

    content = response.content

    actual_sha = git_blob_sha(content)

    if actual_sha != metadata["sha"]:
        raise ValueError(
            "Downloaded CSV does not match GitHub metadata SHA"
        )

    if not content.startswith(b"game_id,"):
        raise ValueError("Downloaded file has an unexpected CSV header")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Write to a temporary file before replacing the cache.
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=DATA_DIR,
            prefix="games_",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)

        os.replace(temporary_path, CSV_PATH)

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    manifest = {
        "filename": "games.csv",
        "source_api": API_URL,
        "source_sha": actual_sha,
        "download_url": metadata["download_url"],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "metadata_http_status": 200,
        "csv_http_status": response.status_code,
        "size_bytes": len(content),
    }

    save_json_atomic(MANIFEST_PATH, manifest)

    logger.info("Cached CSV with source SHA: %s", actual_sha)

    return manifest


def get_source(session, offline=False):
    """Use an intact cache or download the current source."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest()

    if offline:
        if manifest is None or not CSV_PATH.exists():
            raise FileNotFoundError("No cached source is available")

        content = CSV_PATH.read_bytes()

        if git_blob_sha(content) != manifest.get("source_sha"):
            raise ValueError("Cached CSV failed its SHA verification")

        logger.info("Offline mode: using verified cached CSV")
        return manifest

    metadata, metadata_status = fetch_metadata(session)

    if manifest and CSV_PATH.exists():
        if manifest.get("source_sha") == metadata["sha"]:
            cached_sha = git_blob_sha(CSV_PATH.read_bytes())

            if cached_sha == metadata["sha"]:
                logger.info("Source unchanged; using cached CSV")
                return manifest

    manifest = download_csv(session, metadata)
    manifest["metadata_http_status"] = metadata_status

    save_json_atomic(MANIFEST_PATH, manifest)

    return manifest


# --------------------------------------------------
# CSV parsing and message standardization
# --------------------------------------------------

def optional_integer(value):
    """Parse a nullable CSV integer; never convert bad values to null."""

    if value is None or value.strip() in ("", "NA"):
        return None

    return int(value.strip())


def optional_text(value):
    """Represent a missing optional CSV string as JSON null."""

    if value is None or value.strip() in ("", "NA"):
        return None

    return value.strip()


def standardize_game(row, manifest):
    """Convert a source CSV row to exactly the v1.0 contract fields."""

    game_id = row["game_id"].strip()

    if not game_id:
        raise ValueError("Missing game_id")

    home_score = optional_integer(row["home_score"])
    away_score = optional_integer(row["away_score"])

    if home_score is not None and away_score is not None:
        status = "completed"
    elif home_score is None and away_score is None:
        status = "scheduled"
    else:
        status = "incomplete"

    # Keep missing nullable fields as None (serialized as JSON null).
    return {
        "contract_version": CONTRACT_VERSION,
        "source_version": manifest["source_sha"],
        "source_reference": SOURCE_REFERENCE,
        "retrieved_at": manifest["retrieved_at"],
        "game_id": game_id,
        "season": int(row["season"]),
        "game_type": row["game_type"].strip(),
        "week": int(row["week"]),
        "gameday": row["gameday"].strip(),
        "gametime": optional_text(row["gametime"]),
        "kickoff_timezone": KICKOFF_TIMEZONE,
        "away_team": row["away_team"].strip(),
        "home_team": row["home_team"].strip(),
        "away_rest": optional_integer(row["away_rest"]),
        "home_rest": optional_integer(row["home_rest"]),
        "div_game": optional_integer(row["div_game"]),
        "location": optional_text(row["location"]),
        "away_score": away_score,
        "home_score": home_score,
        "status": status,
    }


def read_games(manifest, season=None, limit=5):
    """Read games from the verified snapshot with its own provenance."""

    required_columns = {
        "game_id", "season", "game_type", "week", "gameday", "gametime",
        "away_team", "home_team", "away_rest", "home_rest", "div_game",
        "location", "away_score", "home_score",
    }

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if not required_columns.issubset(reader.fieldnames or []):
            missing = sorted(required_columns - set(reader.fieldnames or []))
            raise ValueError(f"CSV missing required columns: {', '.join(missing)}")

        selected = 0

        for row_number, row in enumerate(reader, start=2):
            if season is not None and row["season"] != str(season):
                continue

            try:
                game = standardize_game(row, manifest)
            except (ValueError, TypeError, KeyError, AttributeError) as error:
                logger.error(
                    "Invalid source CSV row %s (game_id=%r): %s",
                    row_number, row.get("game_id"), error,
                )
                raise ValueError(f"Invalid CSV row {row_number}: {error}") from error

            yield game
            selected += 1

            if limit is not None and selected >= limit:
                break


# --------------------------------------------------
# Redis Streams publishing
# --------------------------------------------------

def connect_redis():
    """Create a Redis client and verify connectivity."""

    client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )

    client.ping()

    logger.info("Connected to Redis")

    return client


def publish_game(client, game):
    """Publish a standardized game to the Redis Stream."""

    payload = json.dumps(game)

    message_id = client.xadd(
        STREAM_NAME,
        {"payload": payload},
    )

    return message_id


# --------------------------------------------------
# Main collector workflow
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Collect NFL games and publish to Redis"
    )

    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--season", type=int, default=2024)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all-seasons", action="store_true", help="Ignore the season filter")
    parser.add_argument("--all-records", action="store_true", help="Ignore the development record limit")

    args = parser.parse_args()

    if args.limit <= 0:
        parser.error("--limit must be greater than zero")

    session = create_http_session()

    try:
        manifest = get_source(
            session,
            offline=args.offline,
        )

        logger.info(
            "Processing source version: %s",
            manifest["source_sha"],
        )

        client = None

        if not args.dry_run:
            client = connect_redis()

        count = 0

        for game in read_games(
            manifest=manifest,
            season=None if args.all_seasons else args.season,
            limit=None if args.all_records else args.limit,
        ):
            if args.dry_run:
                print(json.dumps(game, indent=2))

            else:
                message_id = publish_game(client, game)

                logger.info(
                    "Published game %s as message %s",
                    game["game_id"],
                    message_id,
                )

            count += 1

        logger.info("Collector finished: %s games", count)

    except (
        requests.RequestException,
        redis.RedisError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        logger.error("Collector failed: %s", error)
        raise SystemExit(1)

    finally:
        session.close()


if __name__ == "__main__":
    main()
