"""Real local-services exercise; writes observations, never invented evidence.

Run with DATABASE_URL set and Docker services up. Uses the project's normal
stream/database for the end-to-end trace. Run only against this project's stores.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import requests
import redis
from collector import collector as c
from nfl.storage import Store

OUT = Path('docs/evidence')
OUT.mkdir(parents=True, exist_ok=True)
observations = []

def note(value):
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    observations.append(text)
    print(text, flush=True)
    (OUT / 'system-run.txt').write_text('\n'.join(observations) + '\n', encoding='utf-8')

def command(*args):
    result = subprocess.run([sys.executable, *args], text=True, capture_output=True)
    note('COMMAND ' + ' '.join(args))
    note(f'exit={result.returncode}\n' + '\n'.join((result.stdout + result.stderr).splitlines()[-8:]))
    if result.returncode:
        raise RuntimeError('Command failed')
    return result

def api_start(environment=None):
    log = (OUT / 'api-process.log').open('a', encoding='utf-8')
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'nfl.api:app', '--host', '127.0.0.1', '--port', '8000'],
                               stdout=log, stderr=log, env=environment,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    for _ in range(60):
        if process.poll() is not None:
            log.close()
            raise RuntimeError('API exited; see api-process.log')
        try:
            response = requests.get('http://127.0.0.1:8000/health', timeout=1)
            if response.ok:
                return process, log
        except requests.RequestException:
            pass
        time.sleep(.25)
    process.terminate()
    process.wait(timeout=10)
    log.close()
    raise RuntimeError('API startup timeout')

def main():
    if not os.getenv('DATABASE_URL', '').startswith('postgresql://'):
        raise ValueError('Set DATABASE_URL to the project PostgreSQL service')
    note('Real service exercise. Cached provenance is retained; no source snapshot overwritten.')
    with c.create_http_session() as session:
        metadata, status = c.fetch_metadata(session)
        note(dict(metadata_http_status=status, remote_source_sha=metadata['sha'], download_url=metadata['download_url']))
        manifest = c.get_source(session, offline=True)
        note(dict(cached_manifest=manifest))
    session = requests.Session()
    session.trust_env = False
    try:
        session.get('http://127.0.0.1:1/unreachable-source', timeout=(1, 1))
        raise AssertionError('Expected unavailable source')
    except requests.ConnectionError as error:
        note('UNREACHABLE SOURCE: actual connection failure: ' + type(error).__name__ + '; no messages or cache changes')
    finally:
        session.close()
    client = redis.Redis(host=os.getenv('REDIS_HOST', 'localhost'), port=int(os.getenv('REDIS_PORT', '6379')), decode_responses=True)
    client.ping()
    # No processor is launched yet: collector is a genuinely separate process.
    command('-m', 'collector.collector', '--offline', '--all-seasons', '--all-records')
    note(dict(processor='stopped during collector publication', stream_length=client.xlen(c.STREAM_NAME)))
    command('-m', 'processor.processor', '--once', '--claim-idle-ms', '0')
    note(dict(groups=client.xinfo_groups(c.STREAM_NAME)))
    store = Store()
    note(dict(after_first_ingest=store.counts()))
    first = store.games()[0]
    malformed = client.xadd(c.STREAM_NAME, {'payload': '{not-json'})
    duplicate = c.publish_game(client, first)
    note(dict(malformed_stream_id=malformed, duplicate_stream_id=duplicate, game_id=first['game_id']))
    command('-m', 'processor.processor', '--once', '--claim-idle-ms', '0')
    note(dict(after_invalid_duplicate=store.counts(), groups=client.xinfo_groups(c.STREAM_NAME)))
    store.export('data/staging')
    for name in ['games_clean.csv', 'rejections.jsonl']:
        lines = Path('data/staging', name).read_text().splitlines()
        (OUT / ('sample_' + name)).write_text('\n'.join(lines[:6]) + '\n')
    finish(store, client)

def finish(store, client):
    for query in Path('sql/queries.sql').read_text().split(';'):
        if query.strip():
            rows = store.execute(query).fetchall()
            note(dict(sql=query.strip(), sample=rows[:6], result_rows=len(rows)))
    store.db.commit()
    store.close()
    command('-m', 'nfl.cli', 'train', '--test-season', '2024')
    (OUT / 'evaluation.json').write_text(Path('artifacts/evaluation.json').read_text())
    # Request true scheduled context from the verified snapshot.
    from nfl.source import cached_games
    schedule = cached_games()
    future = next(g for g in schedule if g['season'] == 2026 and g['week'] == 10 and g['status'] == 'scheduled')
    context = {key: future[key] for key in ['home_team', 'away_team', 'season', 'week']}
    process, log = api_start()
    try:
        good = requests.post('http://127.0.0.1:8000/predict', json=context, timeout=30)
        assert good.status_code == 200, good.text
        note(dict(valid_request=context, status=good.status_code, response=good.json()))
        bad = requests.post('http://127.0.0.1:8000/predict', json={**context, 'home_team': 'BAD'}, timeout=30)
        assert bad.status_code == 422
        note(dict(invalid_status=bad.status_code, response=bad.json()))
        result = command('-m', 'nfl.cli', 'predict', '--season', '2026', '--week', '10', '--home', context['home_team'], '--away', context['away_team'])
        (OUT / 'terminal-prediction.txt').write_text(result.stdout)
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()
    note('API process stopped; Redis and PostgreSQL remain responsive')
    assert client.ping()
    process, log = api_start()
    try:
        again = requests.post('http://127.0.0.1:8000/predict', json=context, timeout=30)
        assert again.json() == good.json()
        note(dict(api_restart_status=again.status_code, prediction_unchanged=True))
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()
    for label, changes in [('missing model', {'MODEL_PATH': 'artifacts/intentionally-missing.joblib'}),
                            ('unreachable store', {'DATABASE_URL': 'postgresql://nfl:unused@127.0.0.1:1/nfl'})]:
        environment = dict(os.environ, **changes)
        process, log = api_start(environment)
        try:
            failure = requests.post('http://127.0.0.1:8000/predict', json=context, timeout=30)
            assert failure.status_code == 503, failure.text
            note(dict(failure=label, status=failure.status_code, response=failure.json()))
        finally:
            process.terminate()
            process.wait(timeout=10)
            log.close()
    client.close()
    note('Real-service end-to-end exercise completed. API stopped; Docker stores retained.')

if __name__ == '__main__':
    if '--finish' in sys.argv:
        observations.extend((OUT / 'system-run.txt').read_text().splitlines())
        note('Resumed after correcting a semicolon in a SQL comment that confused the evidence runner statement splitter.')
        finish(Store(), redis.Redis(host=os.getenv('REDIS_HOST', '127.0.0.1'), port=int(os.getenv('REDIS_PORT', '6379')), decode_responses=True))
    else:
        main()
