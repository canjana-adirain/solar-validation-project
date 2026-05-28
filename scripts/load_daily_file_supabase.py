"""
load_daily_file_supabase.py
---------------------------
Simple Supabase/PostgreSQL daily raw loader.

Current scope ONLY:
  1. Creates one upload_batch record
  2. Reads daily Excel file
  3. Inserts rows into raw_daily_staging
  4. Inserts the same rows into raw_daily_history

This version does NOT run validation checks.
This version does NOT insert into daily_validated_data.
This version does NOT insert into validation_issues.

Usage:
    python scripts/load_daily_file_supabase.py
    python scripts/load_daily_file_supabase.py --file "Register data_Raw.xlsx"
    python scripts/load_daily_file_supabase.py --file "input/daily_raw_files/Register data_Raw.xlsx"

"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from sqlalchemy import text

from db import BASE_DIR, engine

# ─────────────────────────────────────────────
# 1. PATHS
# ─────────────────────────────────────────────

INPUT_DIR = BASE_DIR / "input" / "daily_raw_files"
ARCHIVE_DIR = BASE_DIR / "archive" / "processed"
FAILED_DIR = BASE_DIR / "failed" / "failed_files"
LOG_DIR = BASE_DIR / "logs"

for folder in [INPUT_DIR, ARCHIVE_DIR, FAILED_DIR, LOG_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / f"load_daily_supabase_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# These columns must match raw_daily_staging and raw_daily_history table columns.
DAILY_COLS = [
    "upload_id", "row_no", "raw_site_id", "site_name", "hw_id",
    "inverter_name", "reading_date", "has_rsds",
    "idc_total", "idc_1", "idc_2", "idc_3", "idc_4", "idc_5", "idc_6",
    "vdc_avg", "vdc_1", "vdc_2", "vdc_3", "vdc_4", "vdc_5", "vdc_6",
]

NUMERIC_COLS = [
    "idc_total", "idc_1", "idc_2", "idc_3", "idc_4", "idc_5", "idc_6",
    "vdc_avg", "vdc_1", "vdc_2", "vdc_3", "vdc_4", "vdc_5", "vdc_6",
]

REQUIRED_EXCEL_COLUMNS = [
    "Site ID", "Site", "HW ID", "Inverter", "Date", "Has RSDs",
    "IDC", "IDC 1", "IDC 2", "IDC 3", "IDC 4", "IDC 5", "IDC 6",
    "VDC", "VDC 1", "VDC 2", "VDC 3", "VDC 4", "VDC 5", "VDC 6",
]

COLUMN_MAP = {
    "Site ID": "raw_site_id",
    "Site": "site_name",
    "HW ID": "hw_id",
    "Inverter": "inverter_name",
    "Date": "reading_date",
    "Has RSDs": "has_rsds",
    "IDC": "idc_total",
    "IDC 1": "idc_1",
    "IDC 2": "idc_2",
    "IDC 3": "idc_3",
    "IDC 4": "idc_4",
    "IDC 5": "idc_5",
    "IDC 6": "idc_6",
    "VDC": "vdc_avg",
    "VDC 1": "vdc_1",
    "VDC 2": "vdc_2",
    "VDC 3": "vdc_3",
    "VDC 4": "vdc_4",
    "VDC 5": "vdc_5",
    "VDC 6": "vdc_6",
}


def log(message: str) -> None:
    """Print and save log messages."""
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def clean_text(value: Any) -> Optional[str]:
    """Convert empty/nan-like values to None, otherwise stripped string."""
    if pd.isna(value):
        return None
    value = str(value).strip()
    if value == "" or value.lower() == "nan":
        return None
    return value


def parse_bool(value: Any) -> Optional[bool]:
    """Convert Excel truthy/falsy values to Python bool for PostgreSQL."""
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    text_value = str(value).strip().lower()
    if text_value in {"true", "yes", "y", "1"}:
        return True
    if text_value in {"false", "no", "n", "0"}:
        return False
    return None


def get_file_to_process(cli_file: Optional[str]) -> Path:
    """Find the file to process."""
    if cli_file:
        path = Path(cli_file)

        if path.is_absolute() and path.exists():
            return path

        # Try relative to project root.
        project_path = BASE_DIR / path
        if project_path.exists():
            return project_path

        # Try relative to input/daily_raw_files.
        input_path = INPUT_DIR / path.name
        if input_path.exists():
            return input_path

        raise FileNotFoundError(f"File not found: {cli_file}")

    excel_files = sorted(
        [
            p for p in INPUT_DIR.iterdir()
            if p.suffix.lower() in {".xlsx", ".xls"} and not p.name.startswith("~$")
        ]
    )

    if not excel_files:
        raise FileNotFoundError(f"No Excel file found in {INPUT_DIR}")

    return excel_files[0]


def create_upload_batch(file_name: str) -> int:
    """Create upload_batch record and return upload_id."""
    with engine.begin() as conn:
        upload_id = conn.execute(
            text(
                """
                INSERT INTO upload_batch (file_name, file_type, uploaded_by, status)
                VALUES (:file_name, 'daily_raw', 'automation', 'loading')
                RETURNING upload_id
                """
            ),
            {"file_name": file_name},
        ).scalar_one()

    return int(upload_id)


def update_upload_status(upload_id: int, status: str, remarks: str) -> None:
    """Update status/remarks for upload_batch."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE upload_batch
                SET status = :status,
                    remarks = :remarks
                WHERE upload_id = :upload_id
                """
            ),
            {"status": status, "remarks": remarks, "upload_id": upload_id},
        )


def read_and_clean_excel(file_path: Path, upload_id: int) -> pd.DataFrame:
    """Read daily raw Excel and convert it to DB-ready DataFrame."""
    log(f"Reading Excel file: {file_path}")

    df = pd.read_excel(file_path, sheet_name=0)
    df.columns = [str(c).strip() for c in df.columns]

    log(f"Loaded {len(df)} rows from Excel.")
    log(f"Columns found: {list(df.columns)}")

    missing_columns = [col for col in REQUIRED_EXCEL_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    df["upload_id"] = upload_id
    df["row_no"] = range(2, len(df) + 2)  # row 1 is header in Excel

    df.rename(columns=COLUMN_MAP, inplace=True)

    # Clean date and boolean columns.
    df["reading_date"] = pd.to_datetime(df["reading_date"], errors="coerce").dt.date
    df["has_rsds"] = df["has_rsds"].apply(parse_bool)

    # Clean text columns.
    for col in ["raw_site_id", "site_name", "hw_id", "inverter_name"]:
        df[col] = df[col].apply(clean_text)

    # Clean numeric columns.
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Keep only DB columns in correct order.
    df = df[DAILY_COLS].copy()

    # Convert NaN/NaT to None for database insert.
    df = df.astype(object).where(pd.notna(df), None)

    if not df.empty:
        log(f"Date range found: {df['reading_date'].min()} to {df['reading_date'].max()}")

    return df


def insert_dataframe(df: pd.DataFrame, table_name: str) -> None:
    """Append DataFrame rows into a PostgreSQL table."""
    df.to_sql(
        table_name,
        con=engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=500,
    )


def archive_file(file_path: Path) -> Path:
    """Move successfully processed file to archive/processed."""
    archive_path = ARCHIVE_DIR / file_path.name

    # Avoid overwrite if same file name already exists.
    if archive_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = ARCHIVE_DIR / f"{file_path.stem}_{timestamp}{file_path.suffix}"

    shutil.move(str(file_path), str(archive_path))
    return archive_path


def move_to_failed(file_path: Path) -> Path:
    """Move failed file to failed/failed_files."""
    failed_path = FAILED_DIR / file_path.name

    # Avoid overwrite if same file name already exists.
    if failed_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        failed_path = FAILED_DIR / f"{file_path.stem}_{timestamp}{file_path.suffix}"

    shutil.move(str(file_path), str(failed_path))
    return failed_path


def load_daily_file(file_path: Path) -> None:
    """Main load process: upload_batch + staging + raw history only."""
    file_name = file_path.name
    log("=" * 60)
    log("DAILY RAW FILE LOAD STARTED")
    log(f"Selected file: {file_name}")

    upload_id: Optional[int] = None

    try:
        # 1. Create upload_batch record.
        upload_id = create_upload_batch(file_name)
        log(f"upload_batch record created. upload_id = {upload_id}")

        # 2. Read daily Excel file.
        daily_df = read_and_clean_excel(file_path, upload_id)

        # 3. Insert rows into raw_daily_staging.
        insert_dataframe(daily_df, "raw_daily_staging")
        log(f"Inserted {len(daily_df)} rows into raw_daily_staging.")

        # 4. Insert same rows into raw_daily_history.
        insert_dataframe(daily_df, "raw_daily_history")
        log(f"Inserted {len(daily_df)} rows into raw_daily_history.")

        # Mark upload complete.
        update_upload_status(
            upload_id,
            "completed",
            f"{len(daily_df)} rows loaded into raw_daily_staging and raw_daily_history. Validation not run.",
        )
        log("upload_batch status updated to completed.")

        # Move file to archive so it is not processed again by the auto-picker.
        archive_path = archive_file(file_path)
        log(f"File archived to: {archive_path}")

        log("DAILY RAW FILE LOAD COMPLETE")
        log("=" * 60)

    except Exception as exc:
        error_message = str(exc)
        log(f"ERROR: {error_message}")

        if upload_id is not None:
            update_upload_status(upload_id, "failed", error_message[:1000])
            log("upload_batch status updated to failed.")

        try:
            if file_path.exists():
                failed_path = move_to_failed(file_path)
                log(f"File moved to failed folder: {failed_path}")
        except Exception as move_exc:
            log(f"WARNING: Could not move file to failed folder: {move_exc}")

        log("DAILY RAW FILE LOAD FAILED")
        log("=" * 60)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Load daily raw Excel into Supabase staging and raw history only.")
    parser.add_argument(
        "--file",
        help="File name/path to process. If omitted, first Excel file in input/daily_raw_files is used.",
    )
    args = parser.parse_args()

    try:
        file_path = get_file_to_process(args.file)
        load_daily_file(file_path)
    except Exception as exc:
        log(f"Script failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
