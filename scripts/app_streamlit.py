"""
app_streamlit.py
----------------
Simple team-facing upload app for Supabase version.

Run locally:
    streamlit run scripts/app_streamlit.py

Deploy later on Streamlit Community Cloud, Render, Azure App Service, or company-approved hosting.
For production, replace APP_PASSWORD with Supabase Auth or company SSO.
"""

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

st.set_page_config(page_title="Solar Validation System", layout="wide")
st.title("Solar Validation System")

if APP_PASSWORD:
    entered = st.sidebar.text_input("App password", type="password")
    if entered != APP_PASSWORD:
        st.info("Enter the app password to continue.")
        st.stop()

page = st.sidebar.radio(
    "Menu",
    ["Upload Daily File", "Upload Metadata", "Upload Status", "Validation Issues", "Validated Data Preview"],
)


def save_upload(uploaded_file) -> Path:
    suffix = Path(uploaded_file.name).suffix
    temp_dir = Path(tempfile.mkdtemp())
    temp_path = temp_dir / uploaded_file.name
    temp_path.write_bytes(uploaded_file.getbuffer())
    return temp_path


if page == "Upload Daily File":
    st.header("Upload Daily Raw Excel File")
    uploaded_file = st.file_uploader("Choose daily raw Excel file", type=["xlsx", "xls"])
    uploaded_by = st.text_input("Uploaded by", value="team_user")

    if uploaded_file and st.button("Upload and Validate"):
        temp_path = save_upload(uploaded_file)
        with st.spinner("Processing daily file..."):
            try:
                upload_id = load_daily_file(temp_path)
                st.success(f"Daily file processed. Upload ID: {upload_id}")
            except Exception as exc:
                st.error(f"Processing failed: {exc}")

elif page == "Upload Metadata":
    st.header("Upload Metadata Excel File")
    st.warning("Use this carefully. Metadata is the rulebook used for validation.")
    uploaded_file = st.file_uploader("Choose metadata Excel file", type=["xlsx", "xls"])

    if uploaded_file and st.button("Load Metadata"):
        temp_path = save_upload(uploaded_file)
        with st.spinner("Loading metadata..."):
            try:
                load_metadata(temp_path)
                st.success("Metadata loaded/updated successfully.")
            except Exception as exc:
                st.error(f"Metadata load failed: {exc}")

elif page == "Upload Status":
    st.header("Upload Status")
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT upload_id, file_name, file_type, uploaded_by, loaded_at, status, remarks
            FROM upload_batch
            ORDER BY upload_id DESC
            LIMIT 100
        """)).mappings().all()
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

elif page == "Validation Issues":
    st.header("Validation Issues")
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT issue_id, upload_id, row_no, site_name, hw_id, inverter_name,
                   reading_date, mppt_no, issue_type, severity, issue_message, created_at
            FROM validation_issues
            ORDER BY issue_id DESC
            LIMIT 500
        """)).mappings().all()
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

elif page == "Validated Data Preview":
    st.header("Validated Data Preview")
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT validated_id, site_name, hw_id, inverter_name, reading_date,
                   idc_total, vdc_avg, source_upload_id, updated_at
            FROM daily_validated_data
            ORDER BY reading_date DESC, validated_id DESC
            LIMIT 500
        """)).mappings().all()
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
