"""Minimal Supabase connection test — no data read or written."""
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("DATABASE_URL")
if not url:
    print("ERROR: DATABASE_URL not set in .env")
    sys.exit(1)

# Mask password for display
try:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    safe = url.replace(parsed.password, "***") if parsed.password else url
    print(f"Connecting to: {safe}")
except Exception:
    print("Connecting...")

try:
    conn = psycopg2.connect(url, connect_timeout=10)
    cur = conn.cursor()
    cur.execute("SELECT 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    print(f"OK — connection successful (SELECT 1 returned {row[0]})")
except psycopg2.OperationalError as e:
    print(f"FAIL — connection error: {e}")
    sys.exit(1)
