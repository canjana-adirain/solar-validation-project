# from __future__ import annotations

# import os
# import tempfile
# from pathlib import Path

# import pandas as pd
# import streamlit as st
# from dotenv import load_dotenv
# from sqlalchemy import text

# from db import BASE_DIR, engine
# from load_metadata_supabase import load_metadata
# from load_daily_file_supabase import load_daily_file

# load_dotenv(BASE_DIR / ".env")
# APP_PASSWORD = os.getenv("APP_PASSWORD")


# st.set_page_config(page_title="Solar Validation System", page_icon="☀️", layout="wide")


# if APP_PASSWORD:
#     entered = st.sidebar.text_input("App password", type="password")
#     if entered != APP_PASSWORD:
#         st.title("☀️ Solar Validation System")
#         st.info("Enter the app password in the sidebar to continue.")
#         st.stop()

# st.sidebar.title("☀️ Solar Validation")
# st.sidebar.markdown("---")
# page = st.sidebar.radio("Navigation", [
#     "📤 Upload Daily File",
#     "📋 Upload Metadata",
#     "📊 Upload Status",
#     "🔍 String Monitoring",
#     "⚠️ Validation Issues",
#     "✅ Validated Data Preview",
# ])
# # It creates a new temporary folder (temp_dir),then saves the uploaded file inside that folder, and finally returns the full path of that saved file.
# def save_upload(uploaded_file) -> Path:
#     temp_dir  = Path(tempfile.mkdtemp())
#     temp_path = temp_dir / uploaded_file.name
#     temp_path.write_bytes(uploaded_file.getbuffer())
#     return temp_path

# if page == "📤 Upload Daily File":
#     st.title("📤 Upload Daily Raw Excel File")
#     st.markdown(
#         "Upload the daily raw Excel file. "
#         "If the same dates and sites were uploaded before, **old data will be replaced** — not duplicated."
#     )
#     st.markdown("---")

#     uploaded_by   = st.text_input("Your name *", placeholder="e.g. xyz..")
#     uploaded_file = st.file_uploader("Choose daily raw Excel file (.xlsx)", type=["xlsx","xls"])

#     if uploaded_file:
#         st.info(f"Selected: **{uploaded_file.name}** ({round(uploaded_file.size/1024,1)} KB)")

#     if st.button("⬆️ Upload and Process", type="primary"):
#         if not uploaded_file:
#             st.warning("Please select a file first.")
#         elif not uploaded_by.strip():
#             st.warning("Please enter your name before uploading.")
#         else:
#             temp_path = save_upload(uploaded_file)
#             with st.spinner("Processing..."):
#                 try:
#                     upload_id = load_daily_file(temp_path, uploaded_by=uploaded_by.strip())
#                     st.success(f"✅ File processed! Upload ID: **{upload_id}**")
#                     st.info("Check **Upload Status** to confirm. Check **String Monitoring** to see per-string analysis.")
#                 except Exception as exc:
#                     st.error(f"❌ Processing failed: {exc}")

# # ─────────────────────────────────────────────
# # PAGE 2 — UPLOAD METADATA
# # ─────────────────────────────────────────────
# elif page == "📋 Upload Metadata":
#     st.title("📋 Upload Metadata File")
#     st.warning("⚠️ Use carefully — metadata is the rulebook used for validation. Uploading updates existing site and inverter records.")
#     st.markdown("---")

#     uploaded_by   = st.text_input("Your name *", placeholder="e.g. xyz...")
#     uploaded_file = st.file_uploader("Choose metadata Excel file (.xlsx)", type=["xlsx","xls"])

#     if uploaded_file:
#         st.info(f"Selected: **{uploaded_file.name}** ({round(uploaded_file.size/1024,1)} KB)")

#     if st.button("⬆️ Load Metadata", type="primary"):
#         if not uploaded_file:
#             st.warning("Please select a file first.")
#         elif not uploaded_by.strip():
#             st.warning("Please enter your name.")
#         else:
#             temp_path = save_upload(uploaded_file)
#             status_box = st.empty()
#             log_box    = st.empty()
#             log_lines: list[str] = []

#             def update_progress(msg: str):
#                 log_lines.append(msg)
#                 log_box.code("\n".join(log_lines[-12:]))  # show last 12 lines

#             with st.spinner("Loading metadata — this may take 30–60 seconds for large files..."):
#                 try:
#                     result = load_metadata(
#                         temp_path,
#                         uploaded_by=uploaded_by.strip(),
#                         progress_fn=update_progress,
#                     )
#                     log_box.empty()
#                     st.success(
#                         f"✅ Metadata loaded successfully!  "
#                         f"**{result['sites_count']}** sites · "
#                         f"**{result['rulebook_count']}** rulebook rows · "
#                         f"Upload ID: **{result['upload_id']}**"
#                     )
#                     st.info("Check **Upload Status** to confirm the upload record."  )
#                 except Exception as exc:
#                     log_box.empty()
#                     st.error(f"❌ Metadata load failed: {exc}")

# # ─────────────────────────────────────────────
# # PAGE 3 — UPLOAD STATUS
# # ─────────────────────────────────────────────
# elif page == "📊 Upload Status":
#     st.title("📊 Upload Status")
#     st.markdown("Last 100 file uploads — who uploaded, when, and status.")
#     st.markdown("---")

#     try:
#         with engine.connect() as conn:
#             rows = conn.execute(text("""
#                 SELECT
#                     upload_id   AS "Upload ID",
#                     file_name   AS "File Name",
#                     file_type   AS "Type",
#                     uploaded_by AS "Uploaded By",
#                     loaded_at   AS "Uploaded At",
#                     status      AS "Status",
#                     remarks     AS "Remarks"
#                 FROM upload_batch
#                 ORDER BY upload_id DESC
#                 LIMIT 100
#             """)).mappings().all()

#         df = pd.DataFrame(rows)
#         if df.empty:
#             st.info("No uploads yet.")
#         else:
#             def colour_status(val):
#                 if val == "completed": return "background-color:#d4edda;color:#155724"
#                 if val == "failed":    return "background-color:#f8d7da;color:#721c24"
#                 if val == "loading":   return "background-color:#fff3cd;color:#856404"
#                 return ""
#             st.dataframe(df, use_container_width=True)
#             c1,c2,c3 = st.columns(3)
#             c1.metric("Total",     len(df))
#             c2.metric("✅ Completed", len(df[df["Status"]=="completed"]))
#             c3.metric("❌ Failed",    len(df[df["Status"]=="failed"]))
#     except Exception as exc:
#         st.error(f"Could not load status: {exc}")

# # ─────────────────────────────────────────────
# # PAGE 4 — STRING MONITORING
# # ─────────────────────────────────────────────
# elif page == "🔍 String Monitoring":
#     st.title("🔍 String Monitoring")
#     st.markdown("Per-string current and voltage analysis. Flags weak or anomalous strings.")
#     st.markdown("---")

#     try:
#         with engine.connect() as conn:
#             # Get available sites for filter
#             sites = conn.execute(text(
#                 "SELECT DISTINCT site_name FROM daily_string_monitoring ORDER BY site_name"
#             )).fetchall()
#             site_names = [r[0] for r in sites if r[0]]

#         selected_site = st.selectbox("Filter by site", ["All sites"] + site_names)
#         show_anomalies_only = st.checkbox("Show anomalies only", value=False)
#         col_filter = st.selectbox("Measurement type", ["All","Current","Voltage"])

#         with engine.connect() as conn:
#             rows = conn.execute(text("""
#                 SELECT
#                     monitoring_id   AS "ID",
#                     upload_id       AS "Upload ID",
#                     site_name       AS "Site",
#                     hw_id           AS "HW ID",
#                     inverter_name   AS "Inverter",
#                     reading_date    AS "Date",
#                     string_number   AS "String No",
#                     measurement_type AS "Type",
#                     avg_value       AS "Avg Value",
#                     max_current     AS "Max Current",
#                     max_voltage     AS "Max Voltage",
#                     deviation_percent AS "Deviation %",
#                     is_anomaly      AS "Anomaly?",
#                     current_category AS "Category",
#                     created_at      AS "Recorded At"
#                 FROM daily_string_monitoring
#                 ORDER BY monitoring_id DESC
#                 LIMIT 2000
#             """)).mappings().all()

#         df = pd.DataFrame(rows)
#         if df.empty:
#             st.info("No string monitoring data yet. Upload a daily file first.")
#         else:
#             if selected_site != "All sites":
#                 df = df[df["Site"] == selected_site]
#             if show_anomalies_only:
#                 df = df[df["Anomaly?"] == True]
#             if col_filter != "All":
#                 df = df[df["Type"] == col_filter]

#             c1,c2,c3,c4 = st.columns(4)
#             c1.metric("Total Strings",  len(df))
#             c2.metric("🔴 Anomalies",   len(df[df["Anomaly?"]==True]))
#             c3.metric("Avg Deviation",  f"{df['Deviation %'].mean():.2f}%")
#             c4.metric("Sites Shown",    df["Site"].nunique())

#             def colour_anomaly(val):
#                 if val == True:  return "background-color:#f8d7da;color:#721c24"
#                 if val == False: return "background-color:#d4edda;color:#155724"
#                 return ""
#             st.dataframe(df, use_container_width=True)

#     except Exception as exc:
#         st.error(f"Could not load string monitoring data: {exc}")

# # ─────────────────────────────────────────────
# # PAGE 5 — VALIDATION ISSUES
# # ─────────────────────────────────────────────
# elif page == "⚠️ Validation Issues":
#     st.title("⚠️ Validation Issues")
#     st.markdown("Validation errors and warnings found during data checks.")
#     st.markdown("---")
#     try:
#         with engine.connect() as conn:
#             rows = conn.execute(text("""
#                 SELECT issue_id, upload_id, row_no, site_name, hw_id,
#                        inverter_name, reading_date, mppt_no, issue_type,
#                        severity, issue_message, created_at
#                 FROM validation_issues
#                 ORDER BY issue_id DESC
#                 LIMIT 500
#             """)).mappings().all()
#         df = pd.DataFrame(rows)
#         if df.empty:
#             st.success("No validation issues found.")
#         else:
#             c1,c2 = st.columns(2)
#             c1.metric("Total Issues", len(df))
#             c2.metric("Errors",       len(df[df["severity"]=="error"]))
#             st.dataframe(df, use_container_width=True)
#     except Exception as exc:
#         st.error(f"Could not load validation issues: {exc}")

# # ─────────────────────────────────────────────
# # PAGE 6 — VALIDATED DATA PREVIEW
# # ─────────────────────────────────────────────
# elif page == "✅ Validated Data Preview":
#     st.title("✅ Validated Data Preview")
#     st.markdown("Final clean validated data (last 500 rows).")
#     st.markdown("---")
#     try:
#         with engine.connect() as conn:
#             rows = conn.execute(text("""
#                 SELECT validated_id, site_name, hw_id, inverter_name, reading_date,
#                        idc_total, vdc_avg, source_upload_id, updated_at
#                 FROM daily_validated_data
#                 ORDER BY reading_date DESC, validated_id DESC
#                 LIMIT 500
#             """)).mappings().all()
#         df = pd.DataFrame(rows)
#         if df.empty:
#             st.info("No validated data yet. Validation logic is pending.")
#         else:
#             st.metric("Total Validated Rows", len(df))
#             st.dataframe(df, use_container_width=True)
#     except Exception as exc:
#         st.error(f"Could not load validated data: {exc}")


from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import text

from db import BASE_DIR, engine
from load_metadata_supabase import load_metadata
from load_daily_file_supabase import load_daily_file

load_dotenv(BASE_DIR / ".env")
APP_PASSWORD = os.getenv("APP_PASSWORD")


st.set_page_config(page_title="Solar Validation System", page_icon="☀️", layout="wide")


if APP_PASSWORD:
    entered = st.sidebar.text_input("App password", type="password")
    if entered != APP_PASSWORD:
        st.title("☀️ Solar Validation System")
        st.info("Enter the app password in the sidebar to continue.")
        st.stop()

st.sidebar.title("☀️ Solar Validation")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigation", [
    "📤 Upload Daily File",
    "📋 Upload Metadata",
    "📊 Upload Status",
    "🔍 String Monitoring",
    "⚠️ Validation Issues",
    "✅ Validated Data Preview",
])
# It creates a new temporary folder (temp_dir),then saves the uploaded file inside that folder, and finally returns the full path of that saved file.
def save_upload(uploaded_file) -> Path:
    temp_dir  = Path(tempfile.mkdtemp())
    temp_path = temp_dir / uploaded_file.name
    temp_path.write_bytes(uploaded_file.getbuffer())
    return temp_path

if page == "📤 Upload Daily File":
    st.title("📤 Upload Daily Raw Excel File")
    st.markdown(
        "Upload the daily raw Excel file. "
        "If the same dates and sites were uploaded before, **old data will be replaced** — not duplicated."
    )
    st.markdown("---")

    uploaded_by   = st.text_input("Your name *", placeholder="e.g. xyz..")
    uploaded_file = st.file_uploader("Choose daily raw Excel file (.xlsx)", type=["xlsx","xls"])

    if uploaded_file:
        st.info(f"Selected: **{uploaded_file.name}** ({round(uploaded_file.size/1024,1)} KB)")

    if st.button("⬆️ Upload and Process", type="primary"):
        if not uploaded_file:
            st.warning("Please select a file first.")
        elif not uploaded_by.strip():
            st.warning("Please enter your name before uploading.")
        else:
            temp_path = save_upload(uploaded_file)
            with st.spinner("Processing..."):
                try:
                    upload_id = load_daily_file(temp_path, uploaded_by=uploaded_by.strip())
                    st.success(f"✅ File processed! Upload ID: **{upload_id}**")
                    st.info("Validation ran automatically — check **⚠️ Validation Issues** for any errors found.")
                except Exception as exc:
                    st.error(f"❌ Processing failed: {exc}")

# ─────────────────────────────────────────────
# PAGE 2 — UPLOAD METADATA
# ─────────────────────────────────────────────
elif page == "📋 Upload Metadata":
    st.title("📋 Upload Metadata File")
    st.warning("⚠️ Use carefully — metadata is the rulebook used for validation. Uploading updates existing site and inverter records.")
    st.markdown("---")

    uploaded_by   = st.text_input("Your name *", placeholder="e.g. xyz...")
    uploaded_file = st.file_uploader("Choose metadata Excel file (.xlsx)", type=["xlsx","xls"])

    if uploaded_file:
        st.info(f"Selected: **{uploaded_file.name}** ({round(uploaded_file.size/1024,1)} KB)")

    if st.button("⬆️ Load Metadata", type="primary"):
        if not uploaded_file:
            st.warning("Please select a file first.")
        elif not uploaded_by.strip():
            st.warning("Please enter your name.")
        else:
            temp_path = save_upload(uploaded_file)
            status_box = st.empty()
            log_box    = st.empty()
            log_lines: list[str] = []

            def update_progress(msg: str):
                log_lines.append(msg)
                log_box.code("\n".join(log_lines[-12:]))  # show last 12 lines

            with st.spinner("Loading metadata — this may take 30–60 seconds for large files..."):
                try:
                    result = load_metadata(
                        temp_path,
                        uploaded_by=uploaded_by.strip(),
                        progress_fn=update_progress,
                    )
                    log_box.empty()
                    st.success(
                        f"✅ Metadata loaded successfully!  "
                        f"**{result['sites_count']}** sites · "
                        f"**{result['rulebook_count']}** rulebook rows · "
                        f"Upload ID: **{result['upload_id']}**"
                    )
                    st.info("Check **Upload Status** to confirm the upload record."  )
                except Exception as exc:
                    log_box.empty()
                    st.error(f"❌ Metadata load failed: {exc}")

# ─────────────────────────────────────────────
# PAGE 3 — UPLOAD STATUS
# ─────────────────────────────────────────────
elif page == "📊 Upload Status":
    st.title("📊 Upload Status")
    st.markdown("Last 100 file uploads — who uploaded, when, and status.")
    st.markdown("---")

    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    upload_id   AS "Upload ID",
                    file_name   AS "File Name",
                    file_type   AS "Type",
                    uploaded_by AS "Uploaded By",
                    loaded_at   AS "Uploaded At",
                    status      AS "Status",
                    remarks     AS "Remarks"
                FROM upload_batch
                ORDER BY upload_id DESC
                LIMIT 100
            """)).mappings().all()

        df = pd.DataFrame(rows)
        if df.empty:
            st.info("No uploads yet.")
        else:
            def colour_status(val):
                if val == "completed": return "background-color:#d4edda;color:#155724"
                if val == "failed":    return "background-color:#f8d7da;color:#721c24"
                if val == "loading":   return "background-color:#fff3cd;color:#856404"
                return ""
            st.dataframe(df, use_container_width=True)
            c1,c2,c3 = st.columns(3)
            c1.metric("Total",     len(df))
            c2.metric("✅ Completed", len(df[df["Status"]=="completed"]))
            c3.metric("❌ Failed",    len(df[df["Status"]=="failed"]))
    except Exception as exc:
        st.error(f"Could not load status: {exc}")

# ─────────────────────────────────────────────
# PAGE 4 — STRING MONITORING
# ─────────────────────────────────────────────
elif page == "🔍 String Monitoring":
    st.title("🔍 String Monitoring")
    st.markdown("Per-string current and voltage analysis. Flags weak or anomalous strings.")
    st.markdown("---")

    try:
        with engine.connect() as conn:
            # Get available sites for filter
            sites = conn.execute(text(
                "SELECT DISTINCT site_name FROM daily_string_monitoring ORDER BY site_name"
            )).fetchall()
            site_names = [r[0] for r in sites if r[0]]

        selected_site = st.selectbox("Filter by site", ["All sites"] + site_names)
        show_anomalies_only = st.checkbox("Show anomalies only", value=False)
        col_filter = st.selectbox("Measurement type", ["All","Current","Voltage"])

        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    monitoring_id   AS "ID",
                    upload_id       AS "Upload ID",
                    site_name       AS "Site",
                    hw_id           AS "HW ID",
                    inverter_name   AS "Inverter",
                    reading_date    AS "Date",
                    string_number   AS "String No",
                    measurement_type AS "Type",
                    avg_value       AS "Avg Value",
                    max_current     AS "Max Current",
                    max_voltage     AS "Max Voltage",
                    deviation_percent AS "Deviation %",
                    is_anomaly      AS "Anomaly?",
                    current_category AS "Category",
                    created_at      AS "Recorded At"
                FROM daily_string_monitoring
                ORDER BY monitoring_id DESC
                LIMIT 2000
            """)).mappings().all()

        df = pd.DataFrame(rows)
        if df.empty:
            st.info("No string monitoring data yet. Upload a daily file first.")
        else:
            if selected_site != "All sites":
                df = df[df["Site"] == selected_site]
            if show_anomalies_only:
                df = df[df["Anomaly?"] == True]
            if col_filter != "All":
                df = df[df["Type"] == col_filter]

            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Total Strings",  len(df))
            c2.metric("🔴 Anomalies",   len(df[df["Anomaly?"]==True]))
            c3.metric("Avg Deviation",  f"{df['Deviation %'].mean():.2f}%")
            c4.metric("Sites Shown",    df["Site"].nunique())

            def colour_anomaly(val):
                if val == True:  return "background-color:#f8d7da;color:#721c24"
                if val == False: return "background-color:#d4edda;color:#155724"
                return ""
            st.dataframe(df, use_container_width=True)

    except Exception as exc:
        st.error(f"Could not load string monitoring data: {exc}")

# ─────────────────────────────────────────────
# PAGE 5 — VALIDATION ISSUES
# ─────────────────────────────────────────────
elif page == "⚠️ Validation Issues":
    st.title("⚠️ Validation Issues")
    st.markdown("Validation errors and warnings written automatically after every upload.")
    st.markdown("---")
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT issue_id, upload_id, row_no, site_name, hw_id,
                       inverter_name, reading_date, mppt_no, issue_type,
                       severity, issue_message, created_at
                FROM validation_issues
                ORDER BY issue_id DESC
                LIMIT 2000
            """)).mappings().all()

        df = pd.DataFrame(rows)

        if df.empty:
            st.success("✅ No validation issues found.")
        else:
            # ── Filters ──────────────────────────────────────────────
            col_f1, col_f2, col_f3 = st.columns(3)

            upload_ids = ["All"] + sorted(df["upload_id"].dropna().unique().astype(str).tolist(), reverse=True)
            sel_upload = col_f1.selectbox("Filter by Upload ID", upload_ids)

            severities = ["All"] + sorted(df["severity"].dropna().unique().tolist())
            sel_severity = col_f2.selectbox("Filter by Severity", severities)

            issue_types = ["All"] + sorted(df["issue_type"].dropna().unique().tolist())
            sel_issue = col_f3.selectbox("Filter by Issue Type", issue_types)

            filtered = df.copy()
            if sel_upload   != "All": filtered = filtered[filtered["upload_id"].astype(str) == sel_upload]
            if sel_severity != "All": filtered = filtered[filtered["severity"] == sel_severity]
            if sel_issue    != "All": filtered = filtered[filtered["issue_type"] == sel_issue]

            # ── Metrics ──────────────────────────────────────────────
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Issues",    len(filtered))
            c2.metric("🔴 Errors",       len(filtered[filtered["severity"] == "error"]))
            c3.metric("🟡 Warnings",     len(filtered[filtered["severity"] == "warning"]))
            c4.metric("Issue Types",     filtered["issue_type"].nunique())

            # ── Colour by severity ────────────────────────────────────
            def colour_severity(val):
                if val == "error":   return "background-color:#f8d7da;color:#721c24"
                if val == "warning": return "background-color:#fff3cd;color:#856404"
                return ""

            styled = filtered.style.applymap(colour_severity, subset=["severity"])
            st.dataframe(styled, use_container_width=True)

            # ── CSV download ──────────────────────────────────────────
            csv = filtered.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download as CSV",
                data=csv,
                file_name=f"validation_issues_upload{sel_upload}.csv",
                mime="text/csv",
            )

    except Exception as exc:
        st.error(f"Could not load validation issues: {exc}")

# ─────────────────────────────────────────────
# PAGE 6 — VALIDATED DATA PREVIEW
# ─────────────────────────────────────────────
elif page == "✅ Validated Data Preview":
    st.title("✅ Validated Data Preview")
    st.markdown("Final clean validated data (last 500 rows).")
    st.markdown("---")
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT validated_id, site_name, hw_id, inverter_name, reading_date,
                       idc_total, vdc_avg, source_upload_id, updated_at
                FROM daily_validated_data
                ORDER BY reading_date DESC, validated_id DESC
                LIMIT 500
            """)).mappings().all()
        df = pd.DataFrame(rows)
        if df.empty:
            st.info("No validated data yet. Validation logic is pending.")
        else:
            st.metric("Total Validated Rows", len(df))
            st.dataframe(df, use_container_width=True)
    except Exception as exc:
        st.error(f"Could not load validated data: {exc}")