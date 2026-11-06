"""Pregame features with conservative two-calendar-day result availability."""
from datetime import date, timedelta
import pandas as pd

FEATURES = ['week', 'home_rest', 'away_rest', 'div_game', 'neutral',
            'home_recent_win_rate', 'away_recent_win_rate',
            'home_recent_margin', 'away_recent_margin',
            'home_history_games', 'away_history_games']

def pregame(game, history):
    boundary = date.fromisoformat(game['gameday']) - timedelta(days=1)
    # Games on the previous day are also excluded: no final-whistle timestamps exist.
    past = [g for g in history if g['status'] == 'completed' and date.fromisoformat(g['gameday']) < boundary]
    result = {key: game[key] for key in ['week', 'home_rest', 'away_rest', 'div_game']}
    result['neutral'] = None if game['location'] is None else int(game['location'] == 'Neutral')
    used = []
    for side in ['home', 'away']:
        name = game[f'{side}_team']
        recent = sorted([g for g in past if name in (g['home_team'], g['away_team'])], key=lambda g: (g['gameday'], g['game_id']))[-5:]
        margins = [(g['home_score'] - g['away_score']) * (1 if name == g['home_team'] else -1) for g in recent]
        result[f'{side}_recent_win_rate'] = sum(1 if m > 0 else .5 if m == 0 else 0 for m in margins) / len(margins) if margins else None
        result[f'{side}_recent_margin'] = sum(margins) / len(margins) if margins else None
        result[f'{side}_history_games'] = len(recent)
        used.extend(g['gameday'] for g in recent)
    return result, max(used) if used else None

def training_table(games):
    rows = []
    for game in sorted(games, key=lambda g: (g['gameday'], g['game_id'])):
        if game['status'] != 'completed' or game['home_score'] == game['away_score']:
            continue
        values, latest = pregame(game, games)
        rows.append(dict(values, game_id=game['game_id'], gameday=game['gameday'], season=game['season'],
                         source_version=game['source_version'], history_latest_day=latest,
                         home_win=int(game['home_score'] > game['away_score'])))
    table = pd.DataFrame(rows)
    check_leakage(table)
    return table

def check_leakage(table):
    if table.empty:
        raise ValueError('No completed non-tied games for training')
    for row in table.to_dict('records'):
        latest = row.get('history_latest_day')
        if pd.notna(latest) and latest and date.fromisoformat(latest) >= date.fromisoformat(row['gameday']) - timedelta(days=1):
            raise ValueError('Leakage: history is not safely before kickoff')
    if set(FEATURES) & {'home_score', 'away_score', 'home_win', 'status'}:
        raise ValueError('Outcome in feature allowlist')
