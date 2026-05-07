"""Apply schema.sql to Supabase — creates tables only, no data inserted."""
import os
import sys
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("DATABASE_URL")
if not url:
    print("ERROR: DATABASE_URL not set in .env")
    sys.exit(1)

schema_path = Path(__file__).parent.parent / "src/traininglogs/db/schema.sql"
if not schema_path.exists():
    print(f"ERROR: schema.sql not found at {schema_path}")
    sys.exit(1)

sql = schema_path.read_text()

try:
    conn = psycopg2.connect(url, connect_timeout=10)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql)
    cur.close()
    conn.close()
    print("OK — schema applied. Tables created: sessions, exercises, working_sets, warmup_sets")
except psycopg2.Error as e:
    print(f"FAIL: {e}")
    sys.exit(1)
