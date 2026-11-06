"""Opt-in real Docker services. Isolated schemas/stream names; no user data deletion."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import uuid
import pytest

pytestmark = pytest.mark.skipif(os.getenv('RUN_INTEGRATION') != '1', reason='Set RUN_INTEGRATION=1 with local Redis/PostgreSQL running')

def test_real_delivery_pending_concurrency_rollback(game, monkeypatch):
    import psycopg
    from psycopg import sql
    import redis
    from nfl.storage import Store
    from collector import collector
    from processor import processor
    suffix = uuid.uuid4().hex
    stream, schema = 'nfl:test:' + suffix, 'test_' + suffix
    url = os.environ['DATABASE_URL']
    admin = psycopg.connect(url, autocommit=True, connect_timeout=5)
    admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    test_url = url + ('&' if '?' in url else '?') + 'options=-csearch_path%3D' + schema
    monkeypatch.setattr(processor, 'STREAM_NAME', stream)
    monkeypatch.setattr(collector, 'STREAM_NAME', stream)
    client = redis.Redis(host=os.getenv('REDIS_HOST', 'localhost'), port=int(os.getenv('REDIS_PORT', '6379')), decode_responses=True)
    store = Store(test_url)
    try:
        client.xgroup_create(stream, processor.GROUP_NAME, id='0', mkstream=True)
        # Collector publishes while processor is stopped. Entries are unread, not pending.
        sid = collector.publish_game(client, game)
        assert client.xlen(stream) == 1
        assert client.xpending(stream, processor.GROUP_NAME)['pending'] == 0
        entries = client.xreadgroup(processor.GROUP_NAME, 'crashed-worker', {stream: '>'})
        assert entries[0][1][0][0] == sid
        assert client.xpending(stream, processor.GROUP_NAME)['pending'] == 1
        # Restart worker claims delivered but unacknowledged entry.
        processor.run(client, store, consumer='restarted-worker', idle_ms=0, once=True)
        assert client.xpending(stream, processor.GROUP_NAME)['pending'] == 0
        assert store.counts()['accepted'] == 1
        duplicate = collector.publish_game(client, game)
        malformed = client.xadd(stream, {'payload': '{'})
        processor.run(client, store, idle_ms=0, once=True)
        assert store.counts() == dict(seen=3, accepted=1, duplicate=1, rejected=1)
        # Concurrent storage writers race on one new game: unique key accepts exactly one.
        other = game.copy()
        other['game_id'] += '_concurrency_storage_test'
        def write(index):
            writer = Store(test_url)
            try:
                return writer.record('concurrent-' + str(index), other)
            finally:
                writer.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(write, [1, 2])) == ['accepted', 'duplicate']
        # Inject failure between related inserts. PostgreSQL rolls back game insertion.
        original = store.execute
        rollback = game.copy()
        rollback['game_id'] += '_rollback_test'
        def fail(sql_text, values=()):
            if sql_text.startswith('INSERT INTO outcomes'):
                raise RuntimeError('injected outcome failure')
            return original(sql_text, values)
        store.execute = fail
        with pytest.raises(RuntimeError):
            store.record('rollback-stream', rollback)
        store.execute = original
        assert original('SELECT game_id FROM games WHERE game_id=?', (rollback['game_id'],)).fetchone() is None
        store.db.commit()
        print('REAL SERVICES: unread backlog=1; crash pending=1; recovered pending=0; malformed=rejected; duplicate=duplicate; concurrent=accepted+duplicate; related update rollback=verified')
    finally:
        store.close()
        client.delete(stream)
        client.close()
        admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        admin.close()
