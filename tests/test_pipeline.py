import copy
import json
from unittest.mock import Mock
import pytest
import requests
from collector import collector as c
from nfl.storage import Store
from nfl.validation import validate
from processor.processor import process_entry

@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(c, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(c, 'CSV_PATH', tmp_path / 'games.csv')
    monkeypatch.setattr(c, 'MANIFEST_PATH', tmp_path / 'source_manifest.json')
    content = b'game_id,season\nexample,2024\n'
    meta = dict(sha=c.git_blob_sha(content), download_url='https://example.org/games.csv')
    session = Mock()
    response = Mock(status_code=200, content=content)
    response.json.return_value = meta
    session.get.return_value = response
    return session, meta

def test_metadata_cache_reuse_and_corruption(cache):
    session, meta = cache
    assert c.fetch_metadata(session)[0] == meta
    manifest = c.download_csv(session, meta)
    session.get.reset_mock()
    assert c.get_source(session) == manifest
    assert session.get.call_count == 1
    assert c.get_source(session, offline=True) == manifest
    c.CSV_PATH.write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='SHA'):
        c.get_source(session, offline=True)
    c.get_source(session)
    assert c.CSV_PATH.read_bytes().startswith(b'game_id,')

def test_missing_cache_and_unreachable(cache):
    session, _ = cache
    with pytest.raises(FileNotFoundError):
        c.get_source(session, offline=True)
    session.get.side_effect = requests.ConnectionError('injected unreachable source')
    with pytest.raises(requests.ConnectionError):
        c.get_source(session)

def test_invalid_download_and_numeric_data(cache):
    session, meta = cache
    meta['sha'] = 'a' * 40
    with pytest.raises(ValueError, match='SHA'):
        c.download_csv(session, meta)
    with pytest.raises(ValueError):
        c.optional_integer('garbage')
    assert c.optional_integer('0') == 0
    assert c.optional_integer('NA') is None

def test_corrupt_manifest_and_bad_metadata(cache):
    session, _ = cache
    c.MANIFEST_PATH.write_text('[]')
    assert c.load_manifest() is None
    c.MANIFEST_PATH.write_text('{')
    assert c.load_manifest() is None
    session.get.return_value.json.return_value = []
    with pytest.raises(ValueError, match='metadata'):
        c.fetch_metadata(session)

@pytest.mark.parametrize('field,value', [('season', True), ('week', '1'), ('home_score', -1), ('home_team', 'XYZ'), ('gametime', '29:00'), ('gameday', '2024-02-30'), ('source_version', 'bad'), ('retrieved_at', '2024-01-01'), ('status', 'scheduled'), ('div_game', 2), ('location', 'Elsewhere'), ('game_id', '2024_01_KC_KC')])
def test_invalid_contract(game, field, value):
    game[field] = value
    with pytest.raises(ValueError):
        validate(game)

def test_fields_ties_and_nulls(game):
    for payload in [[], {**game, 'extra': 1}, {k: v for k, v in game.items() if k != 'week'}]:
        with pytest.raises(ValueError):
            validate(payload)
    game.update(home_score=0, away_score=0, home_rest=None, gametime=None)
    assert validate(game)['status'] == 'completed'

def test_record_replay_restart_and_export(game, tmp_path):
    path = str(tmp_path / 'ledger.sqlite')
    store = Store(path)
    client = Mock()
    fields = dict(payload=json.dumps(game))
    assert process_entry(client, store, '1-0', fields, tmp_path) == 'accepted'
    store.close()
    store = Store(path)
    assert process_entry(client, store, '1-0', fields, tmp_path) == 'accepted'
    assert process_entry(client, store, '2-0', fields, tmp_path) == 'duplicate'
    assert process_entry(client, store, '3-0', {'payload': '{'}, tmp_path) == 'rejected'
    assert store.counts() == dict(seen=3, accepted=1, rejected=1, duplicate=1)
    assert len((tmp_path / 'games_clean.csv').read_text().splitlines()) == 2
    assert len((tmp_path / 'rejections.jsonl').read_text().splitlines()) == 2
    store.close()

def test_no_ack_when_save_or_export_fails(game, tmp_path):
    client, store = Mock(), Mock()
    store.record.side_effect = OSError('disk failure')
    with pytest.raises(OSError):
        process_entry(client, store, '1-0', dict(payload=json.dumps(game)))
    client.xack.assert_not_called()
    store = Store(str(tmp_path / 'ledger.sqlite'))
    store.export = Mock(side_effect=OSError('export failure'))
    with pytest.raises(OSError):
        process_entry(client, store, '1-0', dict(payload=json.dumps(game)), tmp_path)
    client.xack.assert_not_called()
    assert store.counts()['accepted'] == 1
    store.close()

def test_scheduled_and_incomplete_exclusion(game, tmp_path):
    store = Store(str(tmp_path / 'ledger.sqlite'))
    game.update(home_score=None, away_score=None, status='scheduled')
    assert process_entry(Mock(), store, '1-0', dict(payload=json.dumps(game))) == 'rejected'
    game.update(home_score=3, status='incomplete')
    assert process_entry(Mock(), store, '2-0', dict(payload=json.dumps(game))) == 'rejected'
    assert store.games() == []
    store.close()
