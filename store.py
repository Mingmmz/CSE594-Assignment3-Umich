"""Small DB adapter: Supabase Postgres in production; explicit SQLite for practice."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

class Store:
    def __init__(self, config):
        self.url = config.get('DATABASE_URL')
        self.local_path = config.get('LOCAL_SQLITE_PATH')
        self.postgres = bool(self.url)
        if not self.postgres and not self.local_path:
            raise RuntimeError('Set DATABASE_URL for Supabase, or LOCAL_SQLITE_PATH for local practice.')

    @contextmanager
    def connect(self, initialize=False):
        if self.postgres:
            import psycopg
            from psycopg.rows import dict_row
            db = psycopg.connect(self.url, row_factory=dict_row, prepare_threshold=None,
                                  connect_timeout=10, sslmode='require')
        else:
            Path(self.local_path).parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.local_path, timeout=15)
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
        try:
            if self.postgres:
                if initialize:
                    db.execute('CREATE SCHEMA IF NOT EXISTS a3_study')
                    db.execute('REVOKE ALL ON SCHEMA a3_study FROM PUBLIC')
                db.execute('SET LOCAL search_path TO a3_study')
                db.execute("SET LOCAL statement_timeout = '15000ms'")
            else:
                db.execute('BEGIN IMMEDIATE')
            yield Connection(db, self.postgres)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self):
        with self.connect(initialize=True) as db:
            for statement in Path(__file__).with_name('schema.sql').read_text().split(';'):
                if statement.strip():
                    db.execute(statement)
            if self.postgres:
                for table in ('sessions', 'trials', 'attention_events'):
                    db.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
                # No Data API policies: participant access goes through Flask only.

class Connection:
    def __init__(self, db, postgres):
        self.db, self.postgres = db, postgres

    def execute(self, sql, args=()):
        return self.db.execute(sql.replace('?', '%s') if self.postgres else sql, args)

    def one(self, sql, args=(), lock=False):
        if lock and self.postgres:
            sql += ' FOR UPDATE'
        row = self.execute(sql, args).fetchone()
        return dict(row) if row is not None else None

    def all(self, sql, args=()):
        return [dict(row) for row in self.execute(sql, args).fetchall()]

    def lock_participant(self, code):
        if self.postgres:
            self.execute('SELECT pg_advisory_xact_lock(hashtext(?))', (code,))
