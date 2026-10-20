"""Synthetic SQLite migration smoke test; not a substitute for legacy preservation."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_additive_migration_idempotent_on_synthetic_database(tmp_path):
    root = Path(__file__).resolve().parents[1]
    db_file = tmp_path / 'synthetic.db'
    env = dict(os.environ, DATABASE_URL='sqlite:///' + str(db_file), JWT_SECRET='synthetic-migration-test-only')
    cmd = [sys.executable, 'migrations/20261016_pin_requests.py']
    for _ in range(2):
        subprocess.run(cmd, cwd=root, env=env, check=True, capture_output=True, text=True)
    with sqlite3.connect(db_file) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {'users', 'access_requests', 'consultation_plans', 'medications'}.issubset(tables)
        assert 'pin_hash' in {r[1] for r in conn.execute('PRAGMA table_info(users)')}
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
