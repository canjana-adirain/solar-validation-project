# """
# load_daily_file_supabase.py
# ---------------------------
# Simple Supabase/PostgreSQL daily raw loader.

# Current scope ONLY:
#   1. Creates one upload_batch record
#   2. Reads daily Excel file
#   3. Inserts rows into raw_daily_staging
#   4. Inserts the same rows into raw_daily_history

# This version does NOT run validation checks.
# This version does NOT insert into daily_validated_data.
# This version does NOT insert into validation_issues.

# Usage:
#     python scripts/load_daily_file_supabase.py
#     python scripts/load_daily_file_supabase.py --file "Register data_Raw.xlsx"
#     python scripts/load_daily_file_supabase.py --file "input/daily_raw_files/Register data_Raw.xlsx"

# """

# from __future__ import annotations

# import argparse
# import shutil
# import sys
# from datetime import datetime
# from pathlib import Path
# from typing import Any, Optional
# # import numpy as np
# import pandas as pd
# from sqlalchemy import text

# from db import BASE_DIR, engine

# # ─────────────────────────────────────────────
# # 1. PATHS
# # ─────────────────────────────────────────────

# INPUT_DIR = BASE_DIR / "input" / "daily_raw_files"
# ARCHIVE_DIR = BASE_DIR / "archive" / "processed"
# FAILED_DIR = BASE_DIR / "failed" / "failed_files"
# LOG_DIR = BASE_DIR / "logs"

# for folder in [INPUT_DIR, ARCHIVE_DIR, FAILED_DIR, LOG_DIR]:
#     folder.mkdir(parents=True, exist_ok=True)

# LOG_FILE = LOG_DIR / f"load_daily_supabase_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# # These columns must match raw_daily_staging and raw_daily_history table columns.
# DAILY_COLS = [
#     "upload_id", "row_no", "raw_site_id", "site_name", "hw_id",
#     "inverter_name", "reading_date", "has_rsds",
#     "idc_total", "idc_1", "idc_2", "idc_3", "idc_4", "idc_5", "idc_6",
#     "vdc_avg", "vdc_1", "vdc_2", "vdc_3", "vdc_4", "vdc_5", "vdc_6",
# ]

# NUMERIC_COLS = [
#     "idc_total", "idc_1", "idc_2", "idc_3", "idc_4", "idc_5", "idc_6",
#     "vdc_avg", "vdc_1", "vdc_2", "vdc_3", "vdc_4", "vdc_5", "vdc_6",
# ]

# REQUIRED_EXCEL_COLUMNS = [
#     "Site ID", "Site", "HW ID", "Inverter", "Date", "Has RSDs",
#     "IDC", "IDC 1", "IDC 2", "IDC 3", "IDC 4", "IDC 5", "IDC 6",
#     "VDC", "VDC 1", "VDC 2", "VDC 3", "VDC 4", "VDC 5", "VDC 6",
# ]

# COLUMN_MAP = {
#     "Site ID": "raw_site_id",
#     "Site": "site_name",
#     "HW ID": "hw_id",
#     "Inverter": "inverter_name",
#     "Date": "reading_date",
#     "Has RSDs": "has_rsds",
#     "IDC": "idc_total",
#     "IDC 1": "idc_1",
#     "IDC 2": "idc_2",
#     "IDC 3": "idc_3",
#     "IDC 4": "idc_4",
#     "IDC 5": "idc_5",
#     "IDC 6": "idc_6",
#     "VDC": "vdc_avg",
#     "VDC 1": "vdc_1",
#     "VDC 2": "vdc_2",
#     "VDC 3": "vdc_3",
#     "VDC 4": "vdc_4",
#     "VDC 5": "vdc_5",
#     "VDC 6": "vdc_6",
# }


# def log(message: str) -> None:
#     """Print and save log messages."""
#     line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
#     print(line)
#     with LOG_FILE.open("a", encoding="utf-8") as f:
#         f.write(line + "\n")


# def clean_text(value: Any) -> Optional[str]:
#     """Convert empty/nan-like values to None, otherwise stripped string."""
#     if pd.isna(value):
#         return None
#     value = str(value).strip()
#     if value == "" or value.lower() == "nan":
#         return None
#     return value


# def parse_bool(value: Any) -> Optional[bool]:
#     """Convert Excel truthy/falsy values to Python bool for PostgreSQL."""
#     if pd.isna(value):
#         return None
#     if isinstance(value, bool):
#         return value
#     text_value = str(value).strip().lower()
#     if text_value in {"true", "yes", "y", "1"}:
#         return True
#     if text_value in {"false", "no", "n", "0"}:
#         return False
#     return None


# def get_file_to_process(cli_file: Optional[str]) -> Path:
#     """Find the file to process."""
#     if cli_file:
#         path = Path(cli_file)

#         if path.is_absolute() and path.exists():
#             return path

#         # Try relative to project root.
#         project_path = BASE_DIR / path
#         if project_path.exists():
#             return project_path

#         # Try relative to input/daily_raw_files.
#         input_path = INPUT_DIR / path.name
#         if input_path.exists():
#             return input_path

#         raise FileNotFoundError(f"File not found: {cli_file}")

#     excel_files = sorted(
#         [
#             p for p in INPUT_DIR.iterdir()
#             if p.suffix.lower() in {".xlsx", ".xls"} and not p.name.startswith("~$")
#         ]
#     )

#     if not excel_files:
#         raise FileNotFoundError(f"No Excel file found in {INPUT_DIR}")

#     return excel_files[0]


# def create_upload_batch(file_name: str) -> int:
#     """Create upload_batch record and return upload_id."""
#     with engine.begin() as conn:
#         upload_id = conn.execute(
#             text(
#                 """
#                 INSERT INTO upload_batch (file_name, file_type, uploaded_by, status)
#                 VALUES (:file_name, 'daily_raw', 'automation', 'loading')
#                 RETURNING upload_id
#                 """
#             ),
#             {"file_name": file_name},
#         ).scalar_one()

#     return int(upload_id)


# def update_upload_status(upload_id: int, status: str, remarks: str) -> None:
#     """Update status/remarks for upload_batch."""
#     with engine.begin() as conn:
#         conn.execute(
#             text(
#                 """
#                 UPDATE upload_batch
#                 SET status = :status,
#                     remarks = :remarks
#                 WHERE upload_id = :upload_id
#                 """
#             ),
#             {"status": status, "remarks": remarks, "upload_id": upload_id},
#         )


# def read_and_clean_excel(file_path: Path, upload_id: int) -> pd.DataFrame:
#     """Read daily raw Excel and convert it to DB-ready DataFrame."""
#     log(f"Reading Excel file: {file_path}")

#     df = pd.read_excel(file_path, sheet_name=0)
#     df.columns = [str(c).strip() for c in df.columns]

#     log(f"Loaded {len(df)} rows from Excel.")
#     log(f"Columns found: {list(df.columns)}")

#     missing_columns = [col for col in REQUIRED_EXCEL_COLUMNS if col not in df.columns]
#     if missing_columns:
#         raise ValueError(f"Missing required columns: {missing_columns}")

#     df["upload_id"] = upload_id
#     df["row_no"] = range(2, len(df) + 2)  # row 1 is header in Excel

#     df.rename(columns=COLUMN_MAP, inplace=True)

#     # Clean date and boolean columns.
#     df["reading_date"] = pd.to_datetime(df["reading_date"], errors="coerce").dt.date
#     df["has_rsds"] = df["has_rsds"].apply(parse_bool)

#     # Clean text columns.
#     for col in ["raw_site_id", "site_name", "hw_id", "inverter_name"]:
#         df[col] = df[col].apply(clean_text)

#     # Clean numeric columns.
#     for col in NUMERIC_COLS:
#         df[col] = pd.to_numeric(df[col], errors="coerce")

#     # Keep only DB columns in correct order.
#     df = df[DAILY_COLS].copy()

#     # Convert NaN/NaT to None for database insert.
#     df = df.astype(object).where(pd.notna(df), None)

#     if not df.empty:
#         log(f"Date range found: {df['reading_date'].min()} to {df['reading_date'].max()}")

#     return df


# def insert_dataframe(df: pd.DataFrame, table_name: str) -> None:
#     """Append DataFrame rows into a PostgreSQL table."""
#     df.to_sql(
#         table_name,
#         con=engine,
#         if_exists="append",
#         index=False,
#         method="multi",
#         chunksize=500,
#     )


# def archive_file(file_path: Path) -> Path:
#     """Move successfully processed file to archive/processed."""
#     archive_path = ARCHIVE_DIR / file_path.name

#     # Avoid overwrite if same file name already exists.
#     if archive_path.exists():
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         archive_path = ARCHIVE_DIR / f"{file_path.stem}_{timestamp}{file_path.suffix}"

#     shutil.move(str(file_path), str(archive_path))
#     return archive_path


# def move_to_failed(file_path: Path) -> Path:
#     """Move failed file to failed/failed_files."""
#     failed_path = FAILED_DIR / file_path.name

#     # Avoid overwrite if same file name already exists.
#     if failed_path.exists():
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         failed_path = FAILED_DIR / f"{file_path.stem}_{timestamp}{file_path.suffix}"

#     shutil.move(str(file_path), str(failed_path))
#     return failed_path


# def load_daily_file(file_path: Path) -> None:
#     """Main load process: upload_batch + staging + raw history only."""
#     file_name = file_path.name
#     log("=" * 60)
#     log("DAILY RAW FILE LOAD STARTED")
#     log(f"Selected file: {file_name}")

#     upload_id: Optional[int] = None

#     try:
#         # 1. Create upload_batch record.
#         upload_id = create_upload_batch(file_name)
#         log(f"upload_batch record created. upload_id = {upload_id}")

#         # 2. Read daily Excel file.
#         daily_df = read_and_clean_excel(file_path, upload_id)

#         # 3. Insert rows into raw_daily_staging.
#         insert_dataframe(daily_df, "raw_daily_staging")
#         log(f"Inserted {len(daily_df)} rows into raw_daily_staging.")

#         # 4. Insert same rows into raw_daily_history.
#         insert_dataframe(daily_df, "raw_daily_history")
#         log(f"Inserted {len(daily_df)} rows into raw_daily_history.")
        
#         # Mark upload complete.
#         update_upload_status(
#             upload_id,
#             "completed",
#             f"{len(daily_df)} rows loaded into raw_daily_staging and raw_daily_history. Validation not run.",
#         )
#         log("upload_batch status updated to completed.")

#         # Move file to archive so it is not processed again by the auto-picker.
#         archive_path = archive_file(file_path)
#         log(f"File archived to: {archive_path}")

#         log("DAILY RAW FILE LOAD COMPLETE")
#         log("=" * 60)

#     except Exception as exc:
#         error_message = str(exc)
#         log(f"ERROR: {error_message}")

#         if upload_id is not None:
#             update_upload_status(upload_id, "failed", error_message[:1000])
#             log("upload_batch status updated to failed.")

#         try:
#             if file_path.exists():
#                 failed_path = move_to_failed(file_path)
#                 log(f"File moved to failed folder: {failed_path}")
#         except Exception as move_exc:
#             log(f"WARNING: Could not move file to failed folder: {move_exc}")

#         log("DAILY RAW FILE LOAD FAILED")
#         log("=" * 60)
#         raise


# def main() -> None:
#     parser = argparse.ArgumentParser(description="Load daily raw Excel into Supabase staging and raw history only.")
#     parser.add_argument(
#         "--file",
#         help="File name/path to process. If omitted, first Excel file in input/daily_raw_files is used.",
#     )
#     args = parser.parse_args()

#     try:
#         file_path = get_file_to_process(args.file)
#         load_daily_file(file_path)
#     except Exception as exc:
#         log(f"Script failed: {exc}")
#         sys.exit(1)


# if __name__ == "__main__":
#     main()


"""
load_daily_file_supabase.py
---------------------------
Loads daily raw Excel into Supabase/PostgreSQL.

FIXES APPLIED:
  1. uploaded_by — person's name stored in upload_batch
  2. Duplicate prevention — same dates+sites replaced, not duplicated
  3. String monitoring — after loading, inserts per-string analysis
     into daily_string_monitoring table

Usage:
    python scripts/load_daily_file_supabase.py
    python scripts/load_daily_file_supabase.py --file "Register data_Raw.xlsx"
    python scripts/load_daily_file_supabase.py --uploaded-by "Shivam"
    
    let me know if my understanding of how everything is working is correct or not
    1. we ccreated the database on supabase that means that it is already hosted on the cloud and we can access it from anywhere
    2. Now we created the scripts in python to load the data into the database and we are using sqlalchemy to connect to the database and perform the operations. Supabse gives use the connection string that we add in .env that connects the python to database
    3. we have added the program to the github repo and created the frontend interface on streamlit to upload the file and trigger the load_daily_file function that will load the data into the database
    4. so we have to put our python scripts somehere or dors it require my system to work 24/7 or nothing of this sought is neededa as code is preset on the github and streamlit trigger that code and upload the data to database and run checks?
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from sqlalchemy import text

from db import BASE_DIR, engine

# ─────────────────────────────────────────────
# 1. PATHS
# ─────────────────────────────────────────────

INPUT_DIR   = BASE_DIR / "input" / "daily_raw_files"
ARCHIVE_DIR = BASE_DIR / "archive" / "processed"
FAILED_DIR  = BASE_DIR / "failed" / "failed_files"
LOG_DIR     = BASE_DIR / "logs"

for folder in [INPUT_DIR, ARCHIVE_DIR, FAILED_DIR, LOG_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / f"load_daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# ─────────────────────────────────────────────
# 2. COLUMN DEFINITIONS
# ─────────────────────────────────────────────

DAILY_COLS = [
    "upload_id", "row_no", "raw_site_id", "site_name", "hw_id",
    "inverter_name", "reading_date", "has_rsds",
    "idc_total", "idc_1", "idc_2", "idc_3", "idc_4", "idc_5", "idc_6",
    "vdc_avg",   "vdc_1", "vdc_2", "vdc_3", "vdc_4", "vdc_5", "vdc_6",
]

NUMERIC_COLS = [
    "idc_total", "idc_1", "idc_2", "idc_3", "idc_4", "idc_5", "idc_6",
    "vdc_avg",   "vdc_1", "vdc_2", "vdc_3", "vdc_4", "vdc_5", "vdc_6",
]

REQUIRED_EXCEL_COLUMNS = [
    "Site ID", "Site", "HW ID", "Inverter", "Date", "Has RSDs",
    "IDC", "IDC 1", "IDC 2", "IDC 3", "IDC 4", "IDC 5", "IDC 6",
    "VDC", "VDC 1", "VDC 2", "VDC 3", "VDC 4", "VDC 5", "VDC 6",
]

COLUMN_MAP = {
    "Site ID":  "raw_site_id", "Site":     "site_name",
    "HW ID":    "hw_id",       "Inverter": "inverter_name",
    "Date":     "reading_date","Has RSDs": "has_rsds",
    "IDC":      "idc_total",
    "IDC 1":"idc_1","IDC 2":"idc_2","IDC 3":"idc_3",
    "IDC 4":"idc_4","IDC 5":"idc_5","IDC 6":"idc_6",
    "VDC":      "vdc_avg",
    "VDC 1":"vdc_1","VDC 2":"vdc_2","VDC 3":"vdc_3",
    "VDC 4":"vdc_4","VDC 5":"vdc_5","VDC 6":"vdc_6",
}

# ─────────────────────────────────────────────
# 3. HELPERS
# ─────────────────────────────────────────────

def log(message: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def clean_text(value: Any) -> Optional[str]:
    if pd.isna(value): return None
    value = str(value).strip()
    return None if value == "" or value.lower() == "nan" else value

def parse_bool(value: Any) -> Optional[bool]:
    if pd.isna(value): return None
    if isinstance(value, bool): return value
    v = str(value).strip().lower()
    if v in {"true","yes","y","1"}: return True
    if v in {"false","no","n","0"}: return False
    return None

def get_file_to_process(cli_file: Optional[str]) -> Path:
    if cli_file:
        path = Path(cli_file)
        if path.is_absolute() and path.exists(): return path
        p = BASE_DIR / path
        if p.exists(): return p
        p2 = INPUT_DIR / path.name
        if p2.exists(): return p2
        raise FileNotFoundError(f"File not found: {cli_file}")
    files = sorted([p for p in INPUT_DIR.iterdir()
                    if p.suffix.lower() in {".xlsx",".xls"} and not p.name.startswith("~$")])
    if not files: raise FileNotFoundError(f"No Excel file found in {INPUT_DIR}")
    return files[0]

# ─────────────────────────────────────────────
# 4. DB OPERATIONS
# ─────────────────────────────────────────────

def create_upload_batch(file_name: str, uploaded_by: str) -> int:
    """Create upload_batch record with uploader name. Returns upload_id."""
    with engine.begin() as conn:
        upload_id = conn.execute(text("""
            INSERT INTO upload_batch (file_name, file_type, uploaded_by, status)
            VALUES (:file_name, 'daily_raw', :uploaded_by, 'loading')
            RETURNING upload_id
        """), {"file_name": file_name, "uploaded_by": uploaded_by}).scalar_one()
    return int(upload_id)

def update_upload_status(upload_id: int, status: str, remarks: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE upload_batch SET status=:status, remarks=:remarks
            WHERE upload_id=:upload_id
        """), {"status": status, "remarks": remarks, "upload_id": upload_id})

def read_and_clean_excel(file_path: Path, upload_id: int) -> pd.DataFrame:
    """Read daily Excel and return DB-ready DataFrame."""
    log(f"Reading: {file_path.name}")
    df = pd.read_excel(file_path, sheet_name=0)
    df.columns = [str(c).strip() for c in df.columns]
    log(f"Loaded {len(df)} rows.")

    missing = [c for c in REQUIRED_EXCEL_COLUMNS if c not in df.columns]
    if missing: raise ValueError(f"Missing required columns: {missing}")

    df["upload_id"] = upload_id
    df["row_no"]    = range(2, len(df) + 2)
    df.rename(columns=COLUMN_MAP, inplace=True)

    df["reading_date"] = pd.to_datetime(df["reading_date"], errors="coerce").dt.date
    df["has_rsds"]     = df["has_rsds"].apply(parse_bool)
    for col in ["raw_site_id", "site_name", "hw_id", "inverter_name"]:
        df[col] = df[col].apply(clean_text)
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[DAILY_COLS].copy()
    df = df.astype(object).where(pd.notna(df), None)

    if not df.empty:
        log(f"Date range  : {df['reading_date'].min()} → {df['reading_date'].max()}")
        log(f"Unique sites: {df['site_name'].nunique()} | Unique dates: {df['reading_date'].nunique()}")
    return df

def delete_existing_rows(df: pd.DataFrame) -> None:
    """
    DUPLICATE PREVENTION — bulk delete by dates + sites.
    Deletes matching rows from staging and history before inserting fresh data.
    Re-uploading the same file replaces data instead of duplicating it.
    """
    unique_dates = [str(d) for d in df["reading_date"].dropna().unique().tolist()]
    unique_sites = df["site_name"].dropna().unique().tolist()

    if not unique_dates:
        log("No valid dates — skipping duplicate check.")
        return

    log(f"Removing existing rows for {len(unique_dates)} date(s) and {len(unique_sites)} site(s)...")

    date_ph = ", ".join([f":d{i}" for i in range(len(unique_dates))])
    site_ph = ", ".join([f":s{i}" for i in range(len(unique_sites))])
    params  = {**{f"d{i}": d for i,d in enumerate(unique_dates)},
               **{f"s{i}": s for i,s in enumerate(unique_sites)}}

    sql = f"""DELETE FROM {{table}}
              WHERE reading_date IN ({date_ph})
                AND site_name    IN ({site_ph})"""

    with engine.begin() as conn:
        r1 = conn.execute(text(sql.format(table="raw_daily_staging")), params)
        r2 = conn.execute(text(sql.format(table="raw_daily_history")),  params)
        r3 = conn.execute(text(sql.format(table="daily_string_monitoring")), params)

    log(f"Deleted {r1.rowcount} from staging, {r2.rowcount} from history, {r3.rowcount} from string monitoring.")

def insert_dataframe(df: pd.DataFrame, table_name: str) -> None:
    df.to_sql(table_name, con=engine, if_exists="append",
              index=False, method="multi", chunksize=500)

# ─────────────────────────────────────────────
# 5. STRING MONITORING LOGIC
# (from AMP_DSD_ASSET_MGMT notebook)
# ─────────────────────────────────────────────

def build_string_monitoring(df: pd.DataFrame, upload_id: int) -> pd.DataFrame:
    """
    Converts the wide daily DataFrame into per-string monitoring rows.
    For each inverter, calculates:
      - Average value per string (current and voltage)
      - Max current and max voltage across all strings per inverter
      - Deviation % from the best-performing string
      - is_anomaly flag (current deviation <= -10% OR voltage deviation <= -5%)
      - current_category label

    Returns a DataFrame ready to insert into daily_string_monitoring.
    """
    log("Building string monitoring data...")

    # We need raw_site_id for the monitoring table
    # Restore it from the df (it's already renamed)
    id_vars = ["upload_id", "raw_site_id", "site_name", "hw_id", "inverter_name", "reading_date"]

    # IDC and VDC string columns
    idc_cols = [c for c in ["idc_1","idc_2","idc_3","idc_4","idc_5","idc_6"] if c in df.columns]
    vdc_cols = [c for c in ["vdc_1","vdc_2","vdc_3","vdc_4","vdc_5","vdc_6"] if c in df.columns]

    # Only keep rows where at least one IDC or VDC value exists
    value_cols = idc_cols + vdc_cols
    df_valid   = df[id_vars + value_cols].copy()

    # Convert all value cols to numeric
    for col in value_cols:
        df_valid[col] = pd.to_numeric(df_valid[col], errors="coerce")

    # ── Melt to long format ──────────────────
    # IDC strings
    idc_long = df_valid[id_vars + idc_cols].melt(
        id_vars=id_vars, value_vars=idc_cols,
        var_name="string_col", value_name="value"
    )
    idc_long["measurement_type"] = "Current"
    idc_long["string_number"]    = idc_long["string_col"].str.extract(r"(\d+)").astype(float)

    # VDC strings
    vdc_long = df_valid[id_vars + vdc_cols].melt(
        id_vars=id_vars, value_vars=vdc_cols,
        var_name="string_col", value_name="value"
    )
    vdc_long["measurement_type"] = "Voltage"
    vdc_long["string_number"]    = vdc_long["string_col"].str.extract(r"(\d+)").astype(float)

    melted = pd.concat([idc_long, vdc_long], ignore_index=True)
    melted.drop(columns=["string_col"], inplace=True)
    melted["value"] = pd.to_numeric(melted["value"], errors="coerce")
    melted.dropna(subset=["value","string_number"], inplace=True)

    # ── Average per site/hw/inverter/string/type ──
    group_keys = ["upload_id","raw_site_id","site_name","hw_id","inverter_name","reading_date","string_number","measurement_type"]
    avg_df = melted.groupby(group_keys)["value"].mean().reset_index()
    avg_df.rename(columns={"value": "avg_value"}, inplace=True)

    # ── Max current and max voltage per inverter ──
    inv_keys = ["upload_id","raw_site_id","site_name","hw_id","inverter_name","reading_date"]

    max_curr = avg_df[avg_df["measurement_type"]=="Current"].groupby(inv_keys)["avg_value"].max().reset_index()
    max_curr.rename(columns={"avg_value":"max_current"}, inplace=True)

    max_volt = avg_df[avg_df["measurement_type"]=="Voltage"].groupby(inv_keys)["avg_value"].max().reset_index()
    max_volt.rename(columns={"avg_value":"max_voltage"}, inplace=True)

    # ── Merge max values back ──
    result = avg_df.merge(max_curr, on=inv_keys, how="left")
    result = result.merge(max_volt, on=inv_keys, how="left")

    # ── Deviation % ──
    def calc_deviation(row):
        if row["measurement_type"] == "Current":
            ref = row["max_current"]
        else:
            ref = row["max_voltage"]
        if pd.isna(ref) or ref == 0:
            return 0.0
        return round(((row["avg_value"] - ref) / ref) * 100, 4)

    result["deviation_percent"] = result.apply(calc_deviation, axis=1)

    # ── is_anomaly flag ──
    result["is_anomaly"] = False
    curr_mask = result["measurement_type"] == "Current"
    volt_mask = result["measurement_type"] == "Voltage"
    result.loc[curr_mask & (result["deviation_percent"] <= -10), "is_anomaly"] = True
    result.loc[volt_mask & (result["deviation_percent"] <= -5),  "is_anomaly"] = True

    # ── current_category ──
    conditions = [
        (result["measurement_type"] == "Current") & (result["deviation_percent"] == 0),
        (result["measurement_type"] == "Current") & (result["deviation_percent"] < 0)   & (result["deviation_percent"] > -10),
        (result["measurement_type"] == "Current") & (result["deviation_percent"] <= -10) & (result["deviation_percent"] > -20),
        (result["measurement_type"] == "Current") & (result["deviation_percent"] <= -20) & (result["deviation_percent"] > -30),
        (result["measurement_type"] == "Current") & (result["deviation_percent"] <= -30),
    ]
    choices = [
        "Ignore",
        "Producing Less",
        "1 String Down or No Anomaly",
        "1 String Down and 1 String Producing Less",
        "2 Strings Down or No Anomaly",
    ]
    result["current_category"] = np.select(conditions, choices, default="N/A")

    # ── Final column selection ──
    final_cols = [
        "upload_id", "raw_site_id", "site_name", "hw_id",
        "inverter_name", "reading_date", "string_number",
        "measurement_type", "avg_value", "max_current",
        "max_voltage", "deviation_percent", "is_anomaly", "current_category"
    ]
    result = result[final_cols].copy()
    result["string_number"] = result["string_number"].astype(int)
    result = result.astype(object).where(pd.notna(result), None)

    log(f"String monitoring built — {len(result)} rows.")
    return result

# ─────────────────────────────────────────────
# 6. FILE HANDLING
# ─────────────────────────────────────────────

def archive_file(file_path: Path) -> Path:
    dest = ARCHIVE_DIR / file_path.name
    if dest.exists():
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = ARCHIVE_DIR / f"{file_path.stem}_{ts}{file_path.suffix}"
    shutil.move(str(file_path), str(dest))
    return dest

def move_to_failed(file_path: Path) -> Path:
    dest = FAILED_DIR / file_path.name
    if dest.exists():
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = FAILED_DIR / f"{file_path.stem}_{ts}{file_path.suffix}"
    shutil.move(str(file_path), str(dest))
    return dest

# ─────────────────────────────────────────────
# 7. MAIN LOAD FUNCTION
# ─────────────────────────────────────────────

def load_daily_file(file_path: Path, uploaded_by: str = "team_user") -> int:
    """
    Full pipeline:
      1. Create upload_batch record (with uploader name)
      2. Read and clean Excel
      3. Delete existing rows for same dates+sites (no duplicates)
      4. Insert into raw_daily_staging
      5. Insert into raw_daily_history
      6. Build and insert string monitoring data
      7. Mark upload_batch as completed
      8. Archive file
    Returns upload_id.
    """
    file_name = file_path.name
    upload_id: Optional[int] = None

    log("=" * 60)
    log("DAILY RAW FILE LOAD STARTED")
    log(f"File       : {file_name}")
    log(f"Uploaded by: {uploaded_by}")

    try:
        # Step 1 — Register upload
        upload_id = create_upload_batch(file_name, uploaded_by)
        log(f"upload_batch created — upload_id = {upload_id}")

        # Step 2 — Read Excel
        daily_df = read_and_clean_excel(file_path, upload_id)

        # Step 3 — Remove existing matching rows
        delete_existing_rows(daily_df)

        # Step 4 — Insert into staging
        insert_dataframe(daily_df, "raw_daily_staging")
        log(f"Inserted {len(daily_df)} rows → raw_daily_staging.")

        # Step 5 — Insert into history
        insert_dataframe(daily_df, "raw_daily_history")
        log(f"Inserted {len(daily_df)} rows → raw_daily_history.")

        # Step 6 — String monitoring
        monitoring_df = build_string_monitoring(daily_df, upload_id)
        if not monitoring_df.empty:
            insert_dataframe(monitoring_df, "daily_string_monitoring")
            log(f"Inserted {len(monitoring_df)} rows → daily_string_monitoring.")

        # Step 7 — Mark completed
        update_upload_status(
            upload_id, "completed",
            f"{len(daily_df)} rows loaded by {uploaded_by}. "
            f"{len(monitoring_df)} string monitoring rows inserted. Duplicates replaced."
        )
        log("upload_batch → completed.")

        # Step 8 — Archive file
        archive_path = archive_file(file_path)
        log(f"Archived → {archive_path}")

        log("DAILY RAW FILE LOAD COMPLETE")
        log("=" * 60)
        return upload_id

    except Exception as exc:
        err = str(exc)
        log(f"ERROR: {err}")
        if upload_id is not None:
            update_upload_status(upload_id, "failed", err[:1000])
        try:
            if file_path.exists():
                move_to_failed(file_path)
                log("File moved to failed folder.")
        except Exception as e:
            log(f"WARNING: Could not move file: {e}")
        log("DAILY RAW FILE LOAD FAILED")
        log("=" * 60)
        raise

# ─────────────────────────────────────────────
# 8. CLI ENTRY POINT
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file",        help="Filename to process.")
    parser.add_argument("--uploaded-by", default="automation",
                        help="Name of person uploading.")
    args = parser.parse_args()
    try:
        file_path = get_file_to_process(args.file)
        load_daily_file(file_path, uploaded_by=args.uploaded_by)
    except Exception as exc:
        log(f"Script failed: {exc}")
        sys.exit(1)

if __name__ == "__main__":
    main()
