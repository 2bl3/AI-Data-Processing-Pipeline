"""Explicit verified-cache adapter for reproducible offline experiments."""
from collector.collector import create_http_session, get_source, read_games
from nfl.validation import validate

def cached_games():
    with create_http_session() as session:
        manifest = get_source(session, offline=True)
    return [validate(g) for g in read_games(manifest, season=None, limit=None)]
