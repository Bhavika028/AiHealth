"""Run from project root: python migrations/20261016_pin_requests.py.
Uses the same additive metadata migration as startup; safe to run repeatedly.
Adds nullable user PIN fields and access_requests; leaves legacy PINs unset.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.database import init_db
if __name__=='__main__':
    init_db()
    print('Additive PIN/access-request migration completed.')
