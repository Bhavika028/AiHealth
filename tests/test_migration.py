"""Migrate a copy of the shipped database twice; preserve all original records."""
import os,sqlite3,subprocess,sys
from pathlib import Path

def test_original_database_migrates_without_record_loss(tmp_path):
 root=Path(__file__).resolve().parents[1];target=tmp_path/'legacy.db'
 target.write_bytes((root/'pulsesync.db').read_bytes())
 def snapshot():
  with sqlite3.connect(target) as db:
   names=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
   return {n:([r[1] for r in db.execute(f'PRAGMA table_info("{n}")')],db.execute(f'SELECT * FROM "{n}" ORDER BY rowid').fetchall()) for n in names}
 before=snapshot()
 env={**os.environ,'DATABASE_URL':'sqlite:///'+str(target),'JWT_SECRET':'migration-test-only'}
 for _ in range(2):subprocess.run([sys.executable,'migrations/20261016_pin_requests.py'],cwd=root,env=env,check=True,capture_output=True)
 with sqlite3.connect(target) as db:
  for name,(columns,rows) in before.items():
   fields=','.join('"'+col+'"' for col in columns)
   assert db.execute(f'SELECT {fields} FROM "{name}" ORDER BY rowid').fetchall()==rows,name
  assert 'pin_hash' in [r[1] for r in db.execute('PRAGMA table_info(users)')]
  assert db.execute('SELECT count(*) FROM users WHERE pin_hash IS NOT NULL').fetchone()[0]==0
  assert db.execute('SELECT count(*) FROM access_requests').fetchone()[0]==0

  assert 'instructions' in [r[1] for r in db.execute('PRAGMA table_info(medications)')]
  assert db.execute('SELECT count(*) FROM consultation_plans').fetchone()[0]==0
  assert db.execute('SELECT count(*) FROM outpatient_appointments').fetchone()[0]==0
