# """
# load_metadata_supabase.py
# -------------------------
# Reads Meta_data.xlsx and loads data into Supabase/PostgreSQL:
#   1. sites
#   2. metadata_rulebook

# Usage:
#     python scripts/load_metadata_supabase.py
#     python scripts/load_metadata_supabase.py --file input/Meta_data.xlsx

# Before running:
#     1. Create Supabase project.
#     2. Run sql/01_create_tables_supabase.sql in Supabase SQL Editor.
#     3. Put SUPABASE_DB_URL in .env.
# """

# from __future__ import annotations

# import argparse
# import re
# from datetime import datetime
# from pathlib import Path
# from typing import Iterable, Optional

# import pandas as pd
# from sqlalchemy import text

# from db import BASE_DIR, engine

# LOG_DIR = BASE_DIR / "logs"
# LOG_DIR.mkdir(exist_ok=True)
# LOG_FILE = LOG_DIR / f"load_metadata_supabase_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


# def log(message: str) -> None:
#     line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
#     print(line)
#     with LOG_FILE.open("a", encoding="utf-8") as f:
#         f.write(line + "\n")


# def find_column(df: pd.DataFrame, candidates: Iterable[str]) -> str:
#     """Return the first matching column name from a list of possible names."""
#     normalized = {str(c).strip().lower(): c for c in df.columns}
#     for candidate in candidates:
#         key = candidate.strip().lower()
#         if key in normalized:
#             return normalized[key]
#     raise KeyError(f"Missing expected column. Tried: {list(candidates)}")


# def clean_text(value) -> Optional[str]:
#     if pd.isna(value):
#         return None
#     value = str(value).strip()
#     if value == "" or value.lower() == "nan":
#         return None
#     return value


# def to_float(value) -> Optional[float]:
#     if pd.isna(value) or str(value).strip() == "":
#         return None
#     cleaned = str(value).replace(",", "").strip()
#     try:
#         return float(cleaned)
#     except ValueError:
#         return None


# def to_int(value) -> Optional[int]:
#     number = to_float(value)
#     return int(number) if number is not None else None


# def parse_mppt_range(value) -> tuple[Optional[float], Optional[float]]:
#     """Extract min and max voltage from strings like '500 V -800 V' or '500–800 V'."""
#     if pd.isna(value) or str(value).strip() == "":
#         return None, None
#     numbers = re.findall(r"[\d.]+", str(value))
#     if len(numbers) >= 2:
#         return float(numbers[0]), float(numbers[1])
#     return None, None


# def load_metadata(file_path: str | Path) -> None:
#     file_path = Path(file_path)
#     if not file_path.exists():
#         raise FileNotFoundError(f"Metadata file not found: {file_path}")

#     log(f"Reading metadata file: {file_path}")
#     df = pd.read_excel(file_path, sheet_name="Meta Data", dtype=str)
#     df.columns = [str(c).strip() for c in df.columns]
#     log(f"Loaded {len(df)} rows from 'Meta Data' sheet.")
#     log(f"Columns found: {list(df.columns)}")

#     # Support your current typo columns plus cleaner future names.
#     col_site = find_column(df, ["Projest Name", "Project Name", "Site", "Site Name"])
#     col_code = find_column(df, ["Projest Code", "Project Code", "Code", "Site Code"])
#     col_cod = find_column(df, ["COD", "Commission Date"])
#     col_dc_kw = find_column(df, ["Capacity (kWDC)", "DC kW", "Capacity DC"])
#     col_ac_kw = find_column(df, ["Capacity (kWAC)", "AC kW", "Capacity AC"])
#     col_manufacturer = find_column(df, ["Module Manufacturer", "Manufacturer"])
#     col_inverter = find_column(df, ["Inverter", "Inverter Name"])
#     col_mppt = find_column(df, ["MPPT", "MPPT No"])
#     col_strings = find_column(df, ["String Per MPPT", "Str/MPPT", "Strings Per MPPT"])
#     col_modules_per_string = find_column(df, ["Module /String", "Mod/String", "Modules Per String"])
#     col_total_modules = find_column(df, ["Total Module", "Total Modules"])
#     col_module_w = find_column(df, ["Module capacity", "Module W", "Module Wattage"])
#     col_dc_load = find_column(df, ["DC Load (KW)", "DC Load kW"])
#     col_tilt = find_column(df, ["Tilt", "Tilt°", "Tilt Degrees"])
#     col_azimuth = find_column(df, ["Azimuth", "Az°", "Azimuth Degrees"])
#     col_mppt_range = find_column(df, ["MPPT Range", "Voltage Range"])

#     sites_inserted_or_updated = 0
#     rulebook_inserted_or_updated = 0

#     with engine.begin() as conn:
#         # Load unique sites.
#         sites_df = df[[col_site, col_code, col_cod, col_dc_kw, col_ac_kw, col_manufacturer]].drop_duplicates(subset=[col_site])

#         site_lookup: dict[str, int] = {}

#         log("--- Loading sites table ---")
#         for _, row in sites_df.iterrows():
#             site_name = clean_text(row[col_site])
#             if not site_name:
#                 continue

#             result = conn.execute(
#                 text(
#                     """
#                     INSERT INTO sites (
#                         site_name, site_code, commission_date, dc_kw, ac_kw, manufacturer, updated_at
#                     ) VALUES (
#                         :site_name, :site_code, :commission_date, :dc_kw, :ac_kw, :manufacturer, NOW()
#                     )
#                     ON CONFLICT (site_name)
#                     DO UPDATE SET
#                         site_code = EXCLUDED.site_code,
#                         commission_date = EXCLUDED.commission_date,
#                         dc_kw = EXCLUDED.dc_kw,
#                         ac_kw = EXCLUDED.ac_kw,
#                         manufacturer = EXCLUDED.manufacturer,
#                         updated_at = NOW()
#                     RETURNING site_id
#                     """
#                 ),
#                 {
#                     "site_name": site_name,
#                     "site_code": clean_text(row[col_code]),
#                     "commission_date": pd.to_datetime(row[col_cod], errors="coerce").date()
#                     if pd.notna(pd.to_datetime(row[col_cod], errors="coerce"))
#                     else None,
#                     "dc_kw": to_float(row[col_dc_kw]),
#                     "ac_kw": to_float(row[col_ac_kw]),
#                     "manufacturer": clean_text(row[col_manufacturer]),
#                 },
#             ).fetchone()

#             site_lookup[site_name] = result.site_id
#             sites_inserted_or_updated += 1

#         log(f"Sites loaded/updated: {sites_inserted_or_updated}")

#         # Refresh lookup from DB in case table already had sites.
#         site_rows = conn.execute(text("SELECT site_id, site_name FROM sites")).fetchall()
#         site_lookup = {row.site_name: row.site_id for row in site_rows}
#         log(f"Built site lookup with {len(site_lookup)} sites.")

#         log("--- Loading metadata_rulebook table ---")
#         for idx, row in df.iterrows():
#             site_name = clean_text(row[col_site])
#             inverter_name = clean_text(row[col_inverter])
#             mppt_no = to_int(row[col_mppt])

#             if not site_name or not inverter_name or mppt_no is None:
#                 log(f"Skipping metadata row {idx + 2}: missing site, inverter, or MPPT.")
#                 continue

#             site_id = site_lookup.get(site_name)
#             if not site_id:
#                 log(f"Skipping metadata row {idx + 2}: site not found in lookup: {site_name}")
#                 continue

#             mppt_v_min, mppt_v_max = parse_mppt_range(row[col_mppt_range])

#             conn.execute(
#                 text(
#                     """
#                     INSERT INTO metadata_rulebook (
#                         site_id, inverter_name, mppt_no,
#                         strings_per_mppt, modules_per_string, total_modules,
#                         module_wattage, dc_load_kw, tilt_degrees, azimuth_degrees,
#                         mppt_v_min, mppt_v_max, manufacturer, updated_at
#                     ) VALUES (
#                         :site_id, :inverter_name, :mppt_no,
#                         :strings_per_mppt, :modules_per_string, :total_modules,
#                         :module_wattage, :dc_load_kw, :tilt_degrees, :azimuth_degrees,
#                         :mppt_v_min, :mppt_v_max, :manufacturer, NOW()
#                     )
#                     ON CONFLICT (site_id, inverter_name, mppt_no)
#                     DO UPDATE SET
#                         strings_per_mppt = EXCLUDED.strings_per_mppt,
#                         modules_per_string = EXCLUDED.modules_per_string,
#                         total_modules = EXCLUDED.total_modules,
#                         module_wattage = EXCLUDED.module_wattage,
#                         dc_load_kw = EXCLUDED.dc_load_kw,
#                         tilt_degrees = EXCLUDED.tilt_degrees,
#                         azimuth_degrees = EXCLUDED.azimuth_degrees,
#                         mppt_v_min = EXCLUDED.mppt_v_min,
#                         mppt_v_max = EXCLUDED.mppt_v_max,
#                         manufacturer = EXCLUDED.manufacturer,
#                         updated_at = NOW()
#                     """
#                 ),
#                 {
#                     "site_id": site_id,
#                     "inverter_name": inverter_name,
#                     "mppt_no": mppt_no,
#                     "strings_per_mppt": to_int(row[col_strings]),
#                     "modules_per_string": to_int(row[col_modules_per_string]),
#                     "total_modules": to_int(row[col_total_modules]),
#                     "module_wattage": to_float(row[col_module_w]),
#                     "dc_load_kw": to_float(row[col_dc_load]),
#                     "tilt_degrees": to_float(row[col_tilt]),
#                     "azimuth_degrees": to_float(row[col_azimuth]),
#                     "mppt_v_min": mppt_v_min,
#                     "mppt_v_max": mppt_v_max,
#                     "manufacturer": clean_text(row[col_manufacturer]),
#                 },
#             )
#             rulebook_inserted_or_updated += 1

#     log("=" * 60)
#     log("METADATA LOAD COMPLETE")
#     log(f"Sites loaded/updated: {sites_inserted_or_updated}")
#     log(f"Rulebook rows loaded/updated: {rulebook_inserted_or_updated}")
#     log(f"Log saved to: {LOG_FILE}")
#     log("=" * 60)


# def main() -> None:
#     parser = argparse.ArgumentParser()
#     parser.add_argument(
#         "--file",
#         default=str(BASE_DIR / "input" / "Meta_data.xlsx"),
#         help="Path to metadata Excel file.",
#     )
#     args = parser.parse_args()
#     load_metadata(args.file)


# if __name__ == "__main__":
#     main()

"""
load_metadata_supabase.py
-------------------------
Reads Meta_data.xlsx and loads data into Supabase/PostgreSQL:
  1. sites
  2. metadata_rulebook

Usage:
    python scripts/load_metadata_supabase.py
    python scripts/load_metadata_supabase.py --file input/Meta_data.xlsx

Before running:
    1. Create Supabase project.
    2. Run sql/01_create_tables_supabase.sql in Supabase SQL Editor.
    3. Put SUPABASE_DB_URL in .env.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

import pandas as pd
from sqlalchemy import text

from db import BASE_DIR, engine


# ------------------------------------------------------------------
# Logging — print only (no disk I/O).
# On Streamlit Cloud, disk writes inside a request are slow and can
# cause timeouts when called hundreds of times in a loop.
# The optional `progress_fn` callback lets the frontend push updates
# to st.progress() / st.status() without coupling this module to st.
# ------------------------------------------------------------------

def _log(message: str, progress_fn: Optional[Callable[[str], None]] = None) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line)
    if progress_fn:
        try:
            progress_fn(message)
        except Exception:
            pass  # Never let UI callback crash the load


def find_column(df: pd.DataFrame, candidates: Iterable[str]) -> str:
    """Return the first matching column name from a list of possible names."""
    normalized = {str(c).strip().lower(): c for c in df.columns}
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in normalized:
            return normalized[key]
    raise KeyError(f"Missing expected column. Tried: {list(candidates)}")


def clean_text(value) -> Optional[str]:
    if pd.isna(value):
        return None
    value = str(value).strip()
    if value == "" or value.lower() == "nan":
        return None
    return value


def to_float(value) -> Optional[float]:
    if pd.isna(value) or str(value).strip() == "":
        return None
    cleaned = str(value).replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def to_int(value) -> Optional[int]:
    number = to_float(value)
    return int(number) if number is not None else None


def parse_mppt_range(value) -> tuple[Optional[float], Optional[float]]:
    """Extract min and max voltage from strings like '500 V -800 V' or '500–800 V'."""
    if pd.isna(value) or str(value).strip() == "":
        return None, None
    numbers = re.findall(r"[\d.]+", str(value))
    if len(numbers) >= 2:
        return float(numbers[0]), float(numbers[1])
    return None, None


def load_metadata(
    file_path: str | Path,
    uploaded_by: str = "system",
    progress_fn: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Load metadata from Excel into Supabase.

    Parameters
    ----------
    file_path    : Path to the Meta_data.xlsx file.
    uploaded_by  : Name of the person uploading (stored in upload_batch).
    progress_fn  : Optional callback(message: str) for frontend status updates.
                   Pass `st.status.write` or a lambda to update Streamlit UI.

    Returns
    -------
    dict with keys: sites_count, rulebook_count, upload_id
    """
    def log(msg: str):
        _log(msg, progress_fn)

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {file_path}")

    log(f"Reading metadata file: {file_path.name}")
    df = pd.read_excel(file_path, sheet_name="Meta Data", dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    log(f"Loaded {len(df)} rows from 'Meta Data' sheet.")

    # Column mapping — handles typos and alternate names
    col_site              = find_column(df, ["Projest Name", "Project Name", "Site", "Site Name"])
    col_code              = find_column(df, ["Projest Code", "Project Code", "Code", "Site Code"])
    col_cod               = find_column(df, ["COD", "Commission Date"])
    col_dc_kw             = find_column(df, ["Capacity (kWDC)", "DC kW", "Capacity DC"])
    col_ac_kw             = find_column(df, ["Capacity (kWAC)", "AC kW", "Capacity AC"])
    col_manufacturer      = find_column(df, ["Module Manufacturer", "Manufacturer"])
    col_inverter          = find_column(df, ["Inverter", "Inverter Name"])
    col_mppt              = find_column(df, ["MPPT", "MPPT No"])
    col_strings           = find_column(df, ["String Per MPPT", "Str/MPPT", "Strings Per MPPT"])
    col_modules_per_string = find_column(df, ["Module /String", "Mod/String", "Modules Per String"])
    col_total_modules     = find_column(df, ["Total Module", "Total Modules"])
    col_module_w          = find_column(df, ["Module capacity", "Module W", "Module Wattage"])
    col_dc_load           = find_column(df, ["DC Load (KW)", "DC Load kW"])
    col_tilt              = find_column(df, ["Tilt", "Tilt°", "Tilt Degrees"])
    col_azimuth           = find_column(df, ["Azimuth", "Az°", "Azimuth Degrees"])
    col_mppt_range        = find_column(df, ["MPPT Range", "Voltage Range"])

    sites_count    = 0
    rulebook_count = 0
    upload_id      = None

    with engine.begin() as conn:

        # ── Record this metadata upload in upload_batch ──────────────
        result = conn.execute(
            text("""
                INSERT INTO upload_batch (file_name, file_type, uploaded_by, status, remarks)
                VALUES (:file_name, 'metadata', :uploaded_by, 'loading', 'Metadata load started')
                RETURNING upload_id
            """),
            {"file_name": file_path.name, "uploaded_by": uploaded_by},
        ).fetchone()
        upload_id = result.upload_id
        log(f"Upload batch record created. Upload ID: {upload_id}")

        try:
            # ── SITES ────────────────────────────────────────────────
            sites_df = df[[col_site, col_code, col_cod, col_dc_kw, col_ac_kw, col_manufacturer]] \
                         .drop_duplicates(subset=[col_site])

            site_lookup: dict[str, int] = {}
            log(f"Loading {len(sites_df)} unique sites...")

            # Batch-friendly: build rows list, then bulk-upsert
            site_params = []
            for _, row in sites_df.iterrows():
                site_name = clean_text(row[col_site])
                if not site_name:
                    continue
                cod_raw = pd.to_datetime(row[col_cod], errors="coerce")
                site_params.append({
                    "site_name":       site_name,
                    "site_code":       clean_text(row[col_code]),
                    "commission_date": cod_raw.date() if pd.notna(cod_raw) else None,
                    "dc_kw":           to_float(row[col_dc_kw]),
                    "ac_kw":           to_float(row[col_ac_kw]),
                    "manufacturer":    clean_text(row[col_manufacturer]),
                })

            for params in site_params:
                result = conn.execute(
                    text("""
                        INSERT INTO sites (
                            site_name, site_code, commission_date,
                            dc_kw, ac_kw, manufacturer, updated_at
                        ) VALUES (
                            :site_name, :site_code, :commission_date,
                            :dc_kw, :ac_kw, :manufacturer, NOW()
                        )
                        ON CONFLICT (site_name) DO UPDATE SET
                            site_code       = EXCLUDED.site_code,
                            commission_date = EXCLUDED.commission_date,
                            dc_kw           = EXCLUDED.dc_kw,
                            ac_kw           = EXCLUDED.ac_kw,
                            manufacturer    = EXCLUDED.manufacturer,
                            updated_at      = NOW()
                        RETURNING site_id
                    """),
                    params,
                ).fetchone()
                site_lookup[params["site_name"]] = result.site_id
                sites_count += 1

            log(f"Sites loaded/updated: {sites_count}")

            # Refresh lookup from DB (catches pre-existing sites not in this file)
            all_sites = conn.execute(text("SELECT site_id, site_name FROM sites")).fetchall()
            site_lookup = {row.site_name: row.site_id for row in all_sites}
            log(f"Site lookup built: {len(site_lookup)} total sites in DB.")

            # ── METADATA RULEBOOK ────────────────────────────────────
            log(f"Loading {len(df)} rulebook rows...")

            rulebook_params = []
            skipped = 0
            for idx, row in df.iterrows():
                site_name    = clean_text(row[col_site])
                inverter_name = clean_text(row[col_inverter])
                mppt_no      = to_int(row[col_mppt])

                if not site_name or not inverter_name or mppt_no is None:
                    skipped += 1
                    continue

                site_id = site_lookup.get(site_name)
                if not site_id:
                    log(f"  Skipping row {idx + 2}: site not found — {site_name}")
                    skipped += 1
                    continue

                mppt_v_min, mppt_v_max = parse_mppt_range(row[col_mppt_range])
                rulebook_params.append({
                    "site_id":           site_id,
                    "inverter_name":     inverter_name,
                    "mppt_no":           mppt_no,
                    "strings_per_mppt":  to_int(row[col_strings]),
                    "modules_per_string": to_int(row[col_modules_per_string]),
                    "total_modules":     to_int(row[col_total_modules]),
                    "module_wattage":    to_float(row[col_module_w]),
                    "dc_load_kw":        to_float(row[col_dc_load]),
                    "tilt_degrees":      to_float(row[col_tilt]),
                    "azimuth_degrees":   to_float(row[col_azimuth]),
                    "mppt_v_min":        mppt_v_min,
                    "mppt_v_max":        mppt_v_max,
                    "manufacturer":      clean_text(row[col_manufacturer]),
                })

            # Execute rulebook upserts
            for params in rulebook_params:
                conn.execute(
                    text("""
                        INSERT INTO metadata_rulebook (
                            site_id, inverter_name, mppt_no,
                            strings_per_mppt, modules_per_string, total_modules,
                            module_wattage, dc_load_kw, tilt_degrees, azimuth_degrees,
                            mppt_v_min, mppt_v_max, manufacturer, updated_at
                        ) VALUES (
                            :site_id, :inverter_name, :mppt_no,
                            :strings_per_mppt, :modules_per_string, :total_modules,
                            :module_wattage, :dc_load_kw, :tilt_degrees, :azimuth_degrees,
                            :mppt_v_min, :mppt_v_max, :manufacturer, NOW()
                        )
                        ON CONFLICT (site_id, inverter_name, mppt_no) DO UPDATE SET
                            strings_per_mppt  = EXCLUDED.strings_per_mppt,
                            modules_per_string = EXCLUDED.modules_per_string,
                            total_modules     = EXCLUDED.total_modules,
                            module_wattage    = EXCLUDED.module_wattage,
                            dc_load_kw        = EXCLUDED.dc_load_kw,
                            tilt_degrees      = EXCLUDED.tilt_degrees,
                            azimuth_degrees   = EXCLUDED.azimuth_degrees,
                            mppt_v_min        = EXCLUDED.mppt_v_min,
                            mppt_v_max        = EXCLUDED.mppt_v_max,
                            manufacturer      = EXCLUDED.manufacturer,
                            updated_at        = NOW()
                    """),
                    params,
                )
                rulebook_count += 1

            # ── Mark upload as completed ─────────────────────────────
            conn.execute(
                text("""
                    UPDATE upload_batch
                    SET status  = 'completed',
                        remarks = :remarks
                    WHERE upload_id = :upload_id
                """),
                {
                    "upload_id": upload_id,
                    "remarks":   (
                        f"Sites: {sites_count} loaded/updated. "
                        f"Rulebook rows: {rulebook_count} loaded/updated. "
                        f"Skipped: {skipped}."
                    ),
                },
            )

        except Exception as exc:
            # Mark upload as failed so the team can see it in Upload Status
            conn.execute(
                text("""
                    UPDATE upload_batch
                    SET status  = 'failed',
                        remarks = :remarks
                    WHERE upload_id = :upload_id
                """),
                {"upload_id": upload_id, "remarks": str(exc)[:1000]},
            )
            raise

    log("=" * 60)
    log("METADATA LOAD COMPLETE")
    log(f"Sites loaded/updated:   {sites_count}")
    log(f"Rulebook rows inserted: {rulebook_count}")
    log("=" * 60)

    return {
        "sites_count":    sites_count,
        "rulebook_count": rulebook_count,
        "upload_id":      upload_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file",
        default=str(BASE_DIR / "input" / "Meta_data.xlsx"),
        help="Path to metadata Excel file.",
    )
    parser.add_argument(
        "--uploaded-by",
        default="cli",
        help="Name of the uploader (stored in upload_batch).",
    )
    args = parser.parse_args()
    result = load_metadata(args.file, uploaded_by=args.uploaded_by)
    print(result)


if __name__ == "__main__":
    main()
