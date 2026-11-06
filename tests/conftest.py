import pytest
from nfl.source import cached_games

@pytest.fixture
def game():
    return next(g for g in cached_games() if g['season'] == 2024 and g['status'] == 'completed')
