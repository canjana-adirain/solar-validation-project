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

# So Python already knows where the file lives, and it stores that path in __file__. We can use that to find the project root and load the .env file from there.
# so the base directory is  "C:\Users\Design-Engineer\Downloads\supabase_solar_validation_project"
BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

DB_URL = os.getenv("SUPABASE_DB_URL")

if not DB_URL:
    raise RuntimeError(
        "SUPABASE_DB_URL is missing. Create a .env file using .env.example."
    )

engine = create_engine(DB_URL, echo=False, pool_pre_ping=True)
