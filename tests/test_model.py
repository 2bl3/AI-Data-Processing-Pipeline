import copy
import json
import joblib
import pytest
from fastapi.testclient import TestClient
from nfl.features import FEATURES, pregame, training_table, check_leakage
from nfl.model import train, predict
from nfl.source import cached_games
from nfl.api import app

def test_target_and_future_scores_cannot_change_features(game):
    games = cached_games()
    original, _ = pregame(game, games)
    changed = copy.deepcopy(games)
    for g in changed:
        if g['gameday'] >= game['gameday']:
            g['home_score'], g['away_score'] = 999, 0
    game['home_score'], game['away_score'] = 999, 0
    assert pregame(game, changed)[0] == original
    assert len(FEATURES) >= 8

def test_early_history_and_leakage_detection(game):
    values, latest = pregame(game, [])
    assert values['home_recent_win_rate'] is None and latest is None
    table = training_table([game])
    table['history_latest_day'] = game['gameday']
    with pytest.raises(ValueError, match='Leakage'):
        check_leakage(table)

@pytest.fixture(scope='module')
def saved(tmp_path_factory):
    directory = tmp_path_factory.mktemp('model')
    games = [g for g in cached_games() if 2022 <= g['season'] <= 2024]
    table = training_table(games)
    result = train(table, 2024, directory)
    return directory, games, result

def test_train_save_repeatable_and_metrics(saved):
    directory, games, result = saved
    assert result['train_games'] > 100 and result['test_games'] > 20
    assert result['training_cutoff'] < result['test_start']
    assert set(result['metrics']) == {'baseline', 'logistic'}
    game = next(g for g in games if g['season'] == 2024)
    first = predict(game, games, joblib.load(directory / 'model.joblib'))
    assert first == predict(game, games, joblib.load(directory / 'model.joblib'))
    assert .5 <= first['estimated_win_probability'] <= 1

def test_api_valid_invalid_model_store_and_restart(saved, monkeypatch):
    directory, games, _ = saved
    monkeypatch.setenv('MODEL_PATH', str(directory / 'model.joblib'))
    monkeypatch.setenv('PREDICTION_USE_CACHE', '1')
    g = next(g for g in games if g['season'] == 2024)
    context = {k: g[k] for k in ['home_team', 'away_team', 'season', 'week']}
    with TestClient(app) as client:
        valid = client.post('/predict', json=context)
        assert valid.status_code == 200, valid.text
        assert client.post('/predict', json={**context, 'home_team': 'BAD'}).status_code == 422
        assert client.post('/predict', json={**context, 'week': 99}).status_code == 422
        assert client.post('/predict', json={**context, 'week': 22}).status_code == 404
        monkeypatch.delenv('PREDICTION_USE_CACHE')
        monkeypatch.setenv('DATABASE_URL', str(directory / 'empty.sqlite'))
        assert client.post('/predict', json=context).status_code == 503
        monkeypatch.setenv('PREDICTION_USE_CACHE', '1')
        monkeypatch.setenv('MODEL_PATH', str(directory / 'missing.joblib'))
        assert client.post('/predict', json=context).status_code == 503
    monkeypatch.setenv('MODEL_PATH', str(directory / 'model.joblib'))
    with TestClient(app) as client:
        assert client.post('/predict', json=context).json() == valid.json()
