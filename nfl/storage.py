"""Transactional ledger; CSV/JSONL are reproducible exports."""
import csv
import json
import os
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parent.parent

class Store:
    def __init__(self, url=None):
        self.url = url or os.getenv('DATABASE_URL') or str(ROOT / 'data/staging/ledger.sqlite')
        self.pg = self.url.startswith(('postgresql://', 'postgres://'))
        if self.pg:
            import psycopg
            self.db = psycopg.connect(self.url, connect_timeout=5, autocommit=True)
            with self.db.transaction():
                self.db.execute((ROOT / 'sql/schema.sql').read_text())
        else:
            Path(self.url).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(self.url, timeout=30)
            self.db.execute('PRAGMA synchronous=FULL')
            with self.db:
                self.db.execute('CREATE TABLE IF NOT EXISTS games (game_id TEXT PRIMARY KEY, season INTEGER, gameday TEXT, home_team TEXT, away_team TEXT, payload TEXT NOT NULL)')
                self.db.execute('CREATE TABLE IF NOT EXISTS outcomes (stream_id TEXT PRIMARY KEY, game_id TEXT, decision TEXT, reason TEXT, payload TEXT)')

    def execute(self, sql, values=()):
        return self.db.execute(sql.replace('?', '%s') if self.pg else sql, values)

    def record(self, stream_id, game, reason=''):
        """Commit game and outcome together before caller acknowledges."""
        with self.db.transaction() if self.pg else self.db:
            if self.pg:
                self.execute('SELECT pg_advisory_xact_lock(hashtextextended(?, 0))', (stream_id,))
            old = self.execute('SELECT decision FROM outcomes WHERE stream_id=?', (stream_id,)).fetchone()
            if old:
                return old[0]
            decision = 'rejected'
            if not reason:
                inserted = self.execute('INSERT INTO games(game_id,season,gameday,home_team,away_team,payload) VALUES (?,?,?,?,?,?) ON CONFLICT(game_id) DO NOTHING RETURNING game_id',
                                        (game['game_id'], game['season'], game['gameday'], game['home_team'], game['away_team'], json.dumps(game))).fetchone()
                decision = 'accepted' if inserted else 'duplicate'
                reason = 'valid completed game' if inserted else 'game_id already accepted'
            self.execute('INSERT INTO outcomes(stream_id,game_id,decision,reason,payload) VALUES (?,?,?,?,?)',
                         (stream_id, game.get('game_id') if isinstance(game, dict) and isinstance(game.get('game_id'), str) else None,
                          decision, reason, json.dumps(game)))
        return decision

    def games(self):
        rows = self.execute('SELECT payload FROM games ORDER BY gameday,game_id').fetchall()
        return [json.loads(r[0]) if isinstance(r[0], str) else r[0] for r in rows]

    def counts(self):
        result = dict(self.execute('SELECT decision,COUNT(*) FROM outcomes GROUP BY decision').fetchall())
        return dict(seen=sum(result.values()), **{k: result.get(k, 0) for k in ['accepted', 'rejected', 'duplicate']})

    def export(self, directory):
        """Single exporter only; ledger is authoritative after interrupted exports."""
        from nfl.validation import FIELDS
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        rows = self.execute('SELECT stream_id,game_id,decision,reason,payload FROM outcomes ORDER BY stream_id').fetchall()
        csv_path, log_path = directory / 'games_clean.csv', directory / 'rejections.jsonl'
        with csv_path.with_suffix('.tmp').open('w', newline='', encoding='utf-8') as accepted, log_path.with_suffix('.tmp').open('w', encoding='utf-8') as rejected:
            writer = csv.DictWriter(accepted, fieldnames=FIELDS + ['stream_id'])
            writer.writeheader()
            for sid, gid, decision, reason, payload in rows:
                if decision == 'accepted':
                    game = json.loads(payload) if isinstance(payload, str) else payload
                    writer.writerow(dict(game, stream_id=sid))
                else:
                    rejected.write(json.dumps(dict(stream_id=sid, game_id=gid, decision=decision, reason=reason)) + '\n')
            for handle in (accepted, rejected):
                handle.flush()
                os.fsync(handle.fileno())
        os.replace(csv_path.with_suffix('.tmp'), csv_path)
        os.replace(log_path.with_suffix('.tmp'), log_path)

    def close(self):
        self.db.close()
