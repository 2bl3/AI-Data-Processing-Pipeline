"""Local HTTP boundary. No frontend; use the terminal client or any HTTP client."""
import os
from pathlib import Path
import joblib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from nfl.model import predict
from nfl.source import cached_games
from nfl.storage import Store
from nfl.validation import team

app = FastAPI(title='NFL pregame prediction API')

class Matchup(BaseModel):
    model_config = ConfigDict(extra='forbid')
    home_team: str
    away_team: str
    season: int = Field(ge=1999, le=2100)
    week: int = Field(ge=1, le=22)

def artifact():
    path = Path(os.getenv('MODEL_PATH', 'artifacts/model.joblib'))
    if not path.is_file():
        raise HTTPException(503, 'Trained model unavailable; run the train command')
    try:
        return joblib.load(path)
    except Exception as error:
        raise HTTPException(503, f'Cannot load model: {type(error).__name__}') from error

@app.get('/health')
def health():
    return {'status': 'running', 'model_available': Path(os.getenv('MODEL_PATH', 'artifacts/model.joblib')).is_file()}

@app.get('/evaluation')
def evaluation():
    return artifact()['metadata']

@app.post('/predict')
def prediction(request: Matchup):
    saved = artifact()
    try:
        home, away = team(request.home_team), team(request.away_team)
        if home == away:
            raise ValueError('Teams must differ')
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    try:
        schedule = cached_games()
    except (OSError, ValueError) as error:
        raise HTTPException(503, f'Verified schedule unavailable: {error}') from error
    matching = [g for g in schedule if (g['home_team'], g['away_team'], g['season'], g['week']) == (home, away, request.season, request.week)]
    if len(matching) != 1:
        raise HTTPException(404, 'No unique matchup in the verified snapshot; refresh the collector cache')
    try:
        if os.getenv('PREDICTION_USE_CACHE') == '1':
            history = schedule  # Explicit offline demonstration mode; production uses PostgreSQL.
        else:
            store = Store()
            try:
                history = store.games()
            finally:
                store.close()
        if not history:
            raise ValueError('History store is empty; ingest games before predicting')
    except Exception as error:
        raise HTTPException(503, f'History store unavailable: {type(error).__name__}: {error}') from error
    try:
        return predict(matching[0], history, saved)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
