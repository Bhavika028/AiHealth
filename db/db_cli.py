"""
PulseSync AI - Database CLI Management Utility
Commands to inspect tables, seed data, run raw SQL, and test connection strings
"""

import sys
import os
import argparse
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import engine, init_db, get_db_info, SessionLocal, DATABASE_URL
from backend.seed_data import seed_database

def main():
    parser = argparse.ArgumentParser(description="PulseSync AI Database Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # init
    subparsers.add_parser("init", help="Initialize all database tables")

    # seed
    subparsers.add_parser("seed", help="Seed database with sample clinical test records")

    # status
    subparsers.add_parser("status", help="Show database dialect, connection, and row counts")

    # query
    query_parser = subparsers.add_parser("query", help="Execute a raw SQL SELECT query")
    query_parser.add_argument("sql", type=str, help="SQL string to execute")

    args = parser.parse_args()

    if args.command == "init":
        print(f"[*] Initializing database schema on {DATABASE_URL}...")
        init_db()
        print("[+] Tables initialized successfully.")
    elif args.command == "seed":
        print("[*] Running database seed...")
        seed_database()
    elif args.command == "status":
        info = get_db_info()
        print("\n--- DATABASE STATUS ---")
        print(f"Status:   {info['status']}")
        print(f"Dialect:  {info['dialect']}")
        print(f"URL:      {info.get('active_url', info.get('url', 'N/A'))}")
        print(f"Tables ({info['tables_count']}):")
        for tbl, cnt in info["row_counts"].items():
            print(f"  - {tbl:<24} : {cnt} rows")
        print("-----------------------\n")
    elif args.command == "query":
        with engine.connect() as conn:
            try:
                res = conn.execute(text(args.sql))
                rows = res.fetchall()
                print(f"\n--- QUERY RESULTS ({len(rows)} rows) ---")
                for r in rows:
                    print(dict(r._mapping))
                print("---------------------------------------\n")
            except Exception as e:
                print(f"[!] Query Error: {e}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
