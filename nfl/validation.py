"""The v1.0 wire contract, independent of collector implementation."""
import re
from datetime import date, datetime

FIELDS = ('contract_version source_version source_reference retrieved_at game_id season '
          'game_type week gameday gametime kickoff_timezone away_team home_team away_rest '
          'home_rest div_game location away_score home_score status').split()
TEAMS = set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LV LAC LA MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split())
ALIASES = dict(OAK='LV', SD='LAC', STL='LA', LAR='LA', JAC='JAX', WSH='WAS')

def team(value):
    if not isinstance(value, str):
        raise ValueError('team must be text')
    value = value.strip().upper()
    value = ALIASES.get(value, value)
    if value not in TEAMS:
        raise ValueError(f'unrecognized team: {value}')
    return value

def validate(payload):
    if not isinstance(payload, dict) or set(payload) != set(FIELDS):
        raise ValueError('payload must be an object with exactly the contract fields')
    g = payload.copy()
    nullable = {'gametime', 'location', 'away_rest', 'home_rest', 'div_game', 'away_score', 'home_score'}
    integers = {'season', 'week', 'away_rest', 'home_rest', 'div_game', 'away_score', 'home_score'}
    for key in FIELDS:
        value = g[key]
        if value is None and key in nullable:
            continue
        if key in integers:
            if type(value) is not int or value < 0:
                raise ValueError(f'{key} must be a nonnegative integer')
        elif not isinstance(value, str) or not value:
            raise ValueError(f'{key} must be nonempty text')
    if g['contract_version'] != '1.0':
        raise ValueError('unsupported contract version')
    if not re.fullmatch(r'[0-9a-f]{40}', g['source_version']):
        raise ValueError('source_version must be a Git blob SHA')
    if not g['source_reference'].startswith('https://'):
        raise ValueError('source_reference must be HTTPS')
    if datetime.fromisoformat(g['retrieved_at']).utcoffset() is None:
        raise ValueError('retrieved_at requires timezone')
    if not 1999 <= g['season'] <= 2100 or not 1 <= g['week'] <= 22:
        raise ValueError('season or week out of range')
    if g['game_type'] not in {'REG', 'WC', 'DIV', 'CON', 'SB'}:
        raise ValueError('invalid game_type')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', g['gameday']):
        raise ValueError('gameday must be YYYY-MM-DD')
    if date.fromisoformat(g['gameday']).year not in {g['season'], g['season'] + 1}:
        raise ValueError('gameday outside season')
    if g['gametime'] is not None and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', g['gametime']):
        raise ValueError('gametime must be HH:MM')
    if g['kickoff_timezone'] != 'America/New_York':
        raise ValueError('invalid kickoff timezone')
    if g['div_game'] not in {None, 0, 1} or g['location'] not in {None, 'Home', 'Neutral'}:
        raise ValueError('invalid division flag or location')
    g['away_team'], g['home_team'] = team(g['away_team']), team(g['home_team'])
    if g['away_team'] == g['home_team']:
        raise ValueError('teams must differ')
    match = re.fullmatch(r'(\d{4})_(\d{2})_([A-Z]+)_([A-Z]+)', g['game_id'])
    if not match or (int(match[1]), int(match[2]), team(match[3]), team(match[4])) != (g['season'], g['week'], g['away_team'], g['home_team']):
        raise ValueError('game_id disagrees with season, week or teams')
    scores = [g['home_score'] is not None, g['away_score'] is not None]
    expected = 'completed' if all(scores) else 'incomplete' if any(scores) else 'scheduled'
    if g['status'] != expected:
        raise ValueError('status disagrees with score availability')
    return g
