"""Chronological baseline and logistic regression; saved preprocessing is train-only."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import joblib
import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from nfl.features import FEATURES, check_leakage, pregame

def train(table, test_season=2024, directory='artifacts', cache=False):
    check_leakage(table)
    before = table[table.season < test_season].copy()
    after = table[table.season >= test_season].copy()
    if len(before) < 100 or len(after) < 20 or before.home_win.nunique() < 2:
        raise ValueError('Need >=100 training games, both classes, and >=20 test games')
    if before.gameday.max() >= after.gameday.min():
        raise ValueError('Chronological split overlaps')
    metrics = {}
    models = {
        'baseline': DummyClassifier(strategy='prior'),
        'logistic': make_pipeline(SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True), StandardScaler(), LogisticRegression(max_iter=2000, random_state=42))}
    for name, model in models.items():
        model.fit(before[FEATURES], before.home_win)
        probability = model.predict_proba(after[FEATURES])[:, 1]
        metrics[name] = dict(accuracy=float(accuracy_score(after.home_win, probability >= .5)),
                             brier=float(brier_score_loss(after.home_win, probability)),
                             log_loss=float(log_loss(after.home_win, probability)))
    identity = table.sort_values('game_id').to_csv(index=False).encode()
    metadata = dict(model_version='logistic-' + hashlib.sha256(identity + str(test_season).encode()).hexdigest()[:12],
                    training_cutoff=before.gameday.max(), test_start=after.gameday.min(), test_end=after.gameday.max(),
                    train_games=len(before), test_games=len(after), train_home_win_rate=float(before.home_win.mean()),
                    test_home_win_rate=float(after.home_win.mean()), test_season=test_season,
                    source_versions=sorted(table.source_version.unique().tolist()), features=FEATURES,
                    libraries={p: importlib.metadata.version(p) for p in ['pandas', 'scikit-learn', 'numpy', 'joblib']},
                    metrics=metrics, probability_note='Estimated probability conditional on a non-tied result; not certainty.',
                    command=f'python -m nfl.cli train --test-season {test_season}' + (' --cache' if cache else ''))
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    joblib.dump(dict(model=models['logistic'], metadata=metadata), directory / 'model.joblib.tmp')
    (directory / 'model.joblib.tmp').replace(directory / 'model.joblib')
    (directory / 'evaluation.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return metadata

def predict(game, history, artifact):
    import pandas as pd
    metadata = artifact['metadata']
    if game['gameday'] <= metadata['training_cutoff']:
        raise ValueError('Game must be after the saved model training cutoff')
    values, latest = pregame(game, history)
    x = pd.DataFrame([values], columns=FEATURES).replace({None: np.nan})
    probability = float(artifact['model'].predict_proba(x)[0, 1])
    return dict(game_id=game['game_id'], gameday=game['gameday'], season=game['season'], week=game['week'],
                away_team=game['away_team'], home_team=game['home_team'],
                predicted_winner=game['home_team'] if probability >= .5 else game['away_team'],
                estimated_win_probability=max(probability, 1-probability), home_win_probability=probability,
                model_version=metadata['model_version'], training_cutoff=metadata['training_cutoff'],
                schedule_source_version=game['source_version'], schedule_retrieved_at=game['retrieved_at'],
                history_latest_day=latest, probability_note=metadata['probability_note'],
                context='historical replay' if game['status'] == 'completed' else 'unscored snapshot matchup')
