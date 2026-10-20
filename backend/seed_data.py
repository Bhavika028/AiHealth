"""Compatibility initialization command. Sample clinical data is never inserted."""
from .database import init_db

def seed_database():
    init_db()
    print('Database initialized. Register accounts in the portal; no sample records were inserted.')

if __name__=='__main__':
    seed_database()
