# # Reads raw_daily_staging, runs validation checks, writes to
# # daily_validated_data and validation_issues.

# from __future__ import annotations

# from datetime import datetime
# from typing import Any
# import pandas as pd
# from sqlalchemy import text
# from db import BASE_DIR, engine

# LOG_DIR  = BASE_DIR / "logs"
# LOG_DIR.mkdir(parents=True, exist_ok=True)
# LOG_FILE = LOG_DIR / f"validate_daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


# def log(message: str) -> None:
#     line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
#     print(line)
#     with LOG_FILE.open("a", encoding="utf-8") as f:
#         f.write(line + "\n")

# def read_staging() -> pd.DataFrame:
#     """Load all rows from raw_daily_staging into a DataFrame."""
#     with engine.connect() as conn:
#         df = pd.read_sql(text("SELECT * FROM raw_daily_staging"), conn)
#     log(f"Loaded {len(df)} rows from raw_daily_staging.")
#     return df


# def load_sites_lookup() -> dict:
#     """
#     Returns a dict: { site_name (lowercase): site_id }
#     Lowercased so the check is case-insensitive.
#     """
#     with engine.connect() as conn:
#         rows = conn.execute(text("SELECT site_id, site_name FROM sites")).fetchall()

#     lookup = {row.site_name.strip().lower(): row.site_id for row in rows}
#     log(f"Loaded {len(lookup)} sites from sites table.")
#     return lookup



# def insert_issue(
#     upload_id:     int,
#     row_no:        int,
#     site_id:       Any,       # int or None (None if site not found)
#     site_name:     str,
#     hw_id:         str,
#     inverter_name: str,
#     reading_date:  Any,
#     mppt_no:       Any,       # int or None
#     issue_type:    str,
#     severity:      str,
#     issue_message: str,
# ) -> None:
#     """Write one validation issue row to the validation_issues table."""
#     with engine.begin() as conn:
#         conn.execute(text("""
#             INSERT INTO validation_issues
#                 (upload_id, row_no, site_id, site_name, hw_id,
#                  inverter_name, reading_date, mppt_no,
#                  issue_type, severity, issue_message)
#             VALUES
#                 (:upload_id, :row_no, :site_id, :site_name, :hw_id,
#                  :inverter_name, :reading_date, :mppt_no,
#                  :issue_type, :severity, :issue_message)
#         """), {
#             "upload_id":     upload_id,
#             "row_no":        row_no,
#             "site_id":       site_id,       # NULL when site not found
#             "site_name":     site_name,
#             "hw_id":         hw_id,
#             "inverter_name": inverter_name,
#             "reading_date":  reading_date,
#             "mppt_no":       mppt_no,       # NULL when not applicable
#             "issue_type":    issue_type,
#             "severity":      severity,
#             "issue_message": issue_message,
#         })


# def check_site_exists(staging_df: pd.DataFrame, sites_lookup: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
#     """
#     Splits staging_df into:
#       - passed_df : rows where site_name IS found in sites table
#       - failed_df : rows where site_name is NOT found → SITE_NOT_FOUND error

#     Also writes failed rows to validation_issues table.
#     """
#     passed_rows = []
#     failed_rows = []

#     for _, row in staging_df.iterrows():
#         site_key = str(row["site_name"] or "").strip().lower()

#         if site_key and site_key in sites_lookup:
#             # Site found — attach the official site_id for downstream checks
#             row = row.copy()
#             row["site_id"] = sites_lookup[site_key]
#             passed_rows.append(row)
#         else:
#             # Site NOT found — log the issue
#             # site_id is None because we couldn't resolve it
#             failed_rows.append(row)
#             insert_issue(
#                 upload_id     = int(row["upload_id"]),
#                 row_no        = int(row["row_no"]),
#                 site_id       = None,
#                 site_name     = str(row["site_name"]),
#                 hw_id         = str(row["hw_id"]),
#                 inverter_name = str(row["inverter_name"]),
#                 reading_date  = row["reading_date"],
#                 mppt_no       = None,   # not relevant for this check
#                 issue_type    = "SITE_NOT_FOUND",
#                 severity      = "error",
#                 issue_message = f"Site '{row['site_name']}' not found in sites table.",
#             )

#     passed_df = pd.DataFrame(passed_rows) if passed_rows else pd.DataFrame()
#     failed_df = pd.DataFrame(failed_rows) if failed_rows else pd.DataFrame()

#     log(f"CHECK 1 — Site exists: {len(passed_df)} passed, {len(failed_df)} failed.")
#     return passed_df, failed_df


# def run_validation() -> None:
#     log("=" * 60)
#     log("VALIDATION STARTED")

#     # 1. Read staging
#     staging_df = read_staging()
#     if staging_df.empty:
#         log("raw_daily_staging is empty — nothing to validate.")
#         return

#     # 2. Load lookups
#     sites_lookup = load_sites_lookup()

#     # 3. Run CHECK 1
#     passed_df, failed_df = check_site_exists(staging_df, sites_lookup)

#     # Summary
#     log(f"Total rows     : {len(staging_df)}")
#     log(f"Passed CHECK 1 : {len(passed_df)}")
#     log(f"Failed CHECK 1 : {len(failed_df)}")
#     log("VALIDATION COMPLETE")
#     log("=" * 60)


# if __name__ == "__main__":
#     run_validation()



from __future__ import annotations
 
import argparse
import sys
from datetime import datetime
from typing import Optional
 
import pandas as pd
from sqlalchemy import text
 
from db import BASE_DIR, engine
 
# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
 
LOG_DIR  = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"validate_daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
 
 
def log(message: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
 
 
# ─────────────────────────────────────────────
# STEP 1 — READ raw_daily_staging (fallback only)
# ─────────────────────────────────────────────
 
def read_staging() -> pd.DataFrame:
    """
    Load all rows from raw_daily_staging into a DataFrame.
    Only used when validate_daily_data.py is run standalone (CLI).
    When called from load_daily_file_supabase.py, daily_df is passed
    directly and this function is skipped entirely.
    """
    log("Reading from raw_daily_staging (standalone mode)...")
    with engine.connect() as conn:
        df = pd.read_sql(text("SELECT * FROM raw_daily_staging"), conn)
    log(f"Loaded {len(df)} rows from raw_daily_staging.")
    return df
 
 
# ─────────────────────────────────────────────
# STEP 2 — LOAD LOOKUP: sites table
# ─────────────────────────────────────────────
 
def load_sites_lookup() -> dict:
    """
    Queries the sites table ONCE and returns a dict:
        { site_name_lowercased: site_id }
 
    Lowercased so the check is case-insensitive.
    e.g. "IKEA - West Sac" and "ikea - west sac" both match.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT site_id, site_name FROM sites")
        ).fetchall()
 
    lookup = {row.site_name.strip().lower(): row.site_id for row in rows}
    log(f"Loaded {len(lookup)} sites from sites table.")
    return lookup
 
 
# ─────────────────────────────────────────────
# STEP 3 — CHECK 1: site_name exists in sites
# ─────────────────────────────────────────────
 
def check_site_exists(
    staging_df: pd.DataFrame,
    sites_lookup: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    FIX 1 — Vectorized check (no iterrows loop):
        Uses pandas .map() to check all 22k rows at once.
 
    FIX 2 — Bulk insert (no per-row DB calls):
        All failed rows are written to validation_issues in a
        single to_sql() call instead of one INSERT per row.
 
    Returns:
        passed_df  — rows where site_name was found in sites table.
                     Has a new 'site_id' column attached for use
                     in downstream checks (Check 2, Check 5, etc.)
        failed_df  — rows where site_name was NOT found.
                     Already written to validation_issues.
    """
    # ── Vectorized site lookup ───────────────────────────────
    # Create a normalised key column for matching
    staging_df = staging_df.copy()
    staging_df["_site_key"] = staging_df["site_name"].str.strip().str.lower()
 
    # .map() looks up every key in the dict in one go — no Python loop
    # Rows not in the dict get NaN
    staging_df["site_id"] = staging_df["_site_key"].map(sites_lookup)
 
    # Split into passed and failed
    passed_df = staging_df[staging_df["site_id"].notna()].copy()
    failed_df = staging_df[staging_df["site_id"].isna()].copy()
 
    # ── Bulk insert all failures in ONE DB call ──────────────
    if not failed_df.empty:
        issues_df = pd.DataFrame({
            "upload_id":     failed_df["upload_id"],
            "row_no":        failed_df["row_no"],
            "site_id":       None,      # unknown — that's the whole problem
            "site_name":     failed_df["site_name"],
            "hw_id":         failed_df["hw_id"],
            "inverter_name": failed_df["inverter_name"],
            "reading_date":  failed_df["reading_date"],
            "mppt_no":       None,      # not applicable for this check
            "issue_type":    "SITE_NOT_FOUND",
            "severity":      "error",
            "issue_message": "Site '" + failed_df["site_name"].astype(str)
                             + "' not found in sites table.",
        })
 
        # One single DB call for all failed rows
        issues_df.to_sql(
            "validation_issues",
            con=engine,
            if_exists="append",
            index=False,
            method="multi",   # batches rows into one INSERT statement
            chunksize=500,    # safety: split at 500 rows if very large
        )
        log(f"Inserted {len(issues_df)} SITE_NOT_FOUND issues → validation_issues.")
 
    # Drop the helper column before returning
    passed_df.drop(columns=["_site_key"], inplace=True, errors="ignore")
    failed_df.drop(columns=["_site_key"], inplace=True, errors="ignore")
 
    log(
        f"CHECK 1 — Site exists: "
        f"{len(passed_df)} passed, {len(failed_df)} failed."
    )
    return passed_df, failed_df
 
 
# ─────────────────────────────────────────────
# MAIN — run_validation()
# ─────────────────────────────────────────────
 
def run_validation(daily_df: Optional[pd.DataFrame] = None) -> None:
    """
    Main validation entry point.
 
    Two ways to call this:
 
    1. From load_daily_file_supabase.py (FAST — no DB read):
        from validate_daily_data import run_validation
        run_validation(daily_df)   ← pass the already-cleaned DataFrame
 
    2. Standalone CLI (reads from raw_daily_staging):
        python scripts/validate_daily_data.py
 
    The daily_df parameter is optional. If not provided, the function
    reads from raw_daily_staging automatically.
    """
    log("=" * 60)
    log("VALIDATION STARTED")
 
    # ── Get the data ─────────────────────────────────────────
    if daily_df is not None:
        # Called from pipeline — data already in memory, no DB read needed
        log(f"Using in-memory DataFrame ({len(daily_df)} rows) — skipping DB read.")
        staging_df = daily_df.copy()
    else:
        # Called standalone — read from raw_daily_staging
        staging_df = read_staging()
 
    if staging_df.empty:
        log("No data to validate — exiting.")
        log("=" * 60)
        return
 
    # ── Load lookups ─────────────────────────────────────────
    sites_lookup = load_sites_lookup()
 
    # ── Run checks ───────────────────────────────────────────
    # CHECK 1 — Site exists
    passed_df, failed_df = check_site_exists(staging_df, sites_lookup)
 
    # CHECK 2, 3, 4, 5... will follow the same pattern:
    #   passed_df, failed_df_2 = check_inverter_exists(passed_df, metadata_lookup)
    #   passed_df, failed_df_3 = check_missing_values(passed_df)
    #   etc.
 
    # ── Summary ──────────────────────────────────────────────
    log("-" * 60)
    log(f"Total rows       : {len(staging_df)}")
    log(f"Passed all checks: {len(passed_df)}")
    log(f"Failed CHECK 1   : {len(failed_df)}")
    log("VALIDATION COMPLETE")
    log("=" * 60)
 
 
# ─────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────
 
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run validation on raw_daily_staging data."
    )
    # Future: --upload-id flag to validate a specific upload only
    # parser.add_argument("--upload-id", type=int, help="Validate a specific upload_id only.")
    args = parser.parse_args()
 
    try:
        run_validation()   # no DataFrame passed → reads from DB
    except Exception as exc:
        log(f"Validation script failed: {exc}")
        sys.exit(1)
 
 
if __name__ == "__main__":
    main()