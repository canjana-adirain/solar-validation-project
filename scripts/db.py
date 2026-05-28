"""
db.py
-----
Shared Supabase/PostgreSQL database connection helper.

Create a .env file in the project root with:
SUPABASE_DB_URL=postgresql+psycopg2://USER:PASSWORD@HOST:PORT/postgres
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

DB_URL = os.getenv("SUPABASE_DB_URL")

if not DB_URL:
    raise RuntimeError(
        "SUPABASE_DB_URL is missing. Create a .env file using .env.example."
    )

engine = create_engine(DB_URL, echo=False, pool_pre_ping=True)
