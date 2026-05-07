"""Check row counts on Supabase — read-only."""
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("DATABASE_URL")
if not url:
    print("ERROR: DATABASE_URL not set in .env")
    sys.exit(1)

tables = ["sessions", "exercises", "working_sets", "warmup_sets"]

try:
    conn = psycopg2.connect(url, connect_timeout=10)
    cur = conn.cursor()
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  {table}: {count}")
    cur.close()
    conn.close()
except psycopg2.ProgrammingError as e:
    print(f"Table missing or schema not applied: {e}")
    sys.exit(1)
except psycopg2.OperationalError as e:
    print(f"Connection error: {e}")
    sys.exit(1)
