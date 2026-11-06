"""Independent Redis consumer: python -m processor.processor."""
import argparse
import json
import logging
import os
import redis
from nfl.storage import Store
from nfl.validation import validate

STREAM_NAME = 'nfl:games:v1'
GROUP_NAME = 'processors'
log = logging.getLogger(__name__)

def process_entry(client, store, stream_id, fields, export_dir=None):
    game = None
    try:
        game = json.loads(fields['payload'])
        game = validate(game)
        reason = '' if game['status'] == 'completed' else f"excluded {game['status']} game"
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        reason = str(error)
    decision = store.record(stream_id, game, reason)
    if export_dir:
        store.export(export_dir)
    client.xack(STREAM_NAME, GROUP_NAME, stream_id)
    log.info('stream_id=%s game_id=%s decision=%s reason=%s', stream_id,
             game.get('game_id') if isinstance(game, dict) else None, decision, reason)
    return decision

def run(client, store, consumer='worker-1', idle_ms=60000, once=False, export_dir=None):
    try:
        client.xgroup_create(STREAM_NAME, GROUP_NAME, id='0', mkstream=True)
    except redis.ResponseError as error:
        if 'BUSYGROUP' not in str(error):
            raise
    while True:
        cursor = '0-0'
        while True:
            reply = client.xautoclaim(STREAM_NAME, GROUP_NAME, consumer, idle_ms, cursor, count=100)
            cursor, entries = reply[:2]
            for sid, fields in entries:
                process_entry(client, store, sid, fields, export_dir)
            if cursor == '0-0':
                break
        messages = client.xreadgroup(GROUP_NAME, consumer, {STREAM_NAME: '>'}, count=100, block=1000)
        for _, entries in messages:
            for sid, fields in entries:
                process_entry(client, store, sid, fields, export_dir)
        if once and not messages:
            return

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--consumer', default='worker-1')
    parser.add_argument('--claim-idle-ms', type=int, default=60000)
    parser.add_argument('--export', action='store_true', help='single-writer CSV export')
    args = parser.parse_args()
    if args.claim_idle_ms < 0:
        parser.error('claim idle must be nonnegative')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    client = redis.Redis(host=os.getenv('REDIS_HOST', 'localhost'), port=int(os.getenv('REDIS_PORT', '6379')), decode_responses=True, socket_connect_timeout=5, socket_timeout=10)
    store = None
    try:
        client.ping()
        store = Store()
        run(client, store, args.consumer, args.claim_idle_ms, args.once, 'data/staging' if args.export else None)
    except KeyboardInterrupt:
        log.info('Stopped; unacknowledged entries remain pending')
    except Exception as error:
        log.error('Processor stopped; failed delivery remains pending: %s', error)
        raise SystemExit(1)
    finally:
        if store:
            log.info('Outcomes: %s', store.counts())
            store.close()
        client.close()

if __name__ == '__main__':
    main()
