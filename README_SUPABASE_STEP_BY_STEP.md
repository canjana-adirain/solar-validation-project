# Supabase Solar Validation System - Step-by-Step Guide

This project converts the local MySQL version into a Supabase/PostgreSQL version.

Important: Supabase uses PostgreSQL, not MySQL. That means the database syntax and connection string are different.

---

## 1. What your system will do

Team member uploads a daily Excel file.

The system will:

1. Track the file in `upload_batch`.
2. Load the Excel rows into `raw_daily_staging`.
3. Copy the same rows into `raw_daily_history`.
4. Validate the data against `sites` and `metadata_rulebook`.
5. Save errors/warnings into `validation_issues`.
6. Save accepted rows into `daily_validated_data`.
7. Show results in Streamlit and later Power BI.

Simple flow:

```text
Excel file
↓
Streamlit / Python script
↓
Supabase PostgreSQL database
↓
Validation
↓
Validated data + validation issues
↓
Dashboard
```

---

## 2. Files in this package

```text
supabase_solar_validation_project/
│
├── sql/
│   ├── 01_create_tables_supabase.sql
│   └── 02_process_daily_upload.sql
│
├── scripts/
│   ├── db.py
│   ├── load_metadata_supabase.py
│   ├── load_daily_file_supabase.py
│   └── app_streamlit.py
│
├── input/
│   └── daily_raw_files/
│
├── archive/
│   └── processed/
│
├── failed/
│   └── failed_files/
│
├── logs/
│
├── requirements.txt
├── .env.example
└── README_SUPABASE_STEP_BY_STEP.md
```

---

## 3. Step 1: Create Supabase project

1. Go to Supabase.
2. Create a new project.
3. Choose a project name, for example:

```text
solar-validation-system
```

4. Save your database password safely.

---

## 4. Step 2: Create database tables

In Supabase:

1. Open your project.
2. Go to **SQL Editor**.
3. Open `sql/01_create_tables_supabase.sql` from this package.
4. Copy and paste the full SQL into Supabase SQL Editor.
5. Click **Run**.

This creates:

```text
sites
metadata_rulebook
upload_batch
raw_daily_staging
raw_daily_history
daily_validated_data
validation_issues
site_alias
inverter_alias
validation_rule_config
```

---

## 5. Step 3: Create validation function

In Supabase SQL Editor:

1. Open `sql/02_process_daily_upload.sql`.
2. Copy and paste the full SQL.
3. Click **Run**.

This creates one important function:

```text
process_daily_upload(upload_id)
```

This function does the main backend work:

```text
Copy staging to raw history
Run validation checks
Store errors/warnings
Store good rows
Update upload status
```

---

## 6. Step 4: Get Supabase database connection string

In Supabase:

1. Go to **Project Settings**.
2. Go to **Database**.
3. Find the database connection string.
4. Use the connection string in SQLAlchemy format:

```text
postgresql+psycopg2://postgres:YOUR_PASSWORD@YOUR_HOST:5432/postgres
```

If your password has special characters like `@`, `#`, `%`, or `/`, URL encode it.

---

## 7. Step 5: Create `.env` file

Copy `.env.example` and rename it to `.env`.

Put your actual Supabase database connection string:

```text
SUPABASE_DB_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@YOUR_HOST:5432/postgres
APP_PASSWORD=your_app_password
```

Do not share this file publicly.

---

## 8. Step 6: Install Python packages

Open terminal inside the project folder and run:

```bash
python -m venv .venv
```

Activate it:

Windows:

```bash
.venv\Scripts\activate
```

Mac/Linux:

```bash
source .venv/bin/activate
```

Install packages:

```bash
pip install -r requirements.txt
```

---

## 9. Step 7: Load metadata

Place the metadata file here:

```text
input/Meta_data.xlsx
```

Then run:

```bash
python scripts/load_metadata_supabase.py
```

Or pass file path manually:

```bash
python scripts/load_metadata_supabase.py --file "input/Meta_data.xlsx"
```

This fills:

```text
sites
metadata_rulebook
```

---

## 10. Step 8: Load daily raw file

Place daily Excel file here:

```text
input/daily_raw_files/
```

Then run:

```bash
python scripts/load_daily_file_supabase.py
```

Or pass a file manually:

```bash
python scripts/load_daily_file_supabase.py --file "input/daily_raw_files/Register data_Raw.xlsx"
```

This fills/processes:

```text
upload_batch
raw_daily_staging
raw_daily_history
validation_issues
daily_validated_data
```

---

## 11. Step 9: Run the team upload app

Run:

```bash
streamlit run scripts/app_streamlit.py
```

The app will show pages:

```text
Upload Daily File
Upload Metadata
Upload Status
Validation Issues
Validated Data Preview
```

For local testing, your team can use it only if they can access your machine.
For real team usage, deploy this app on company-approved hosting such as Render, Azure App Service, Streamlit Cloud, or an internal server.

---

## 12. How the team will use it

### Uploader

1. Open the web app link.
2. Enter password/login.
3. Go to **Upload Daily File**.
4. Upload the Excel file.
5. Click **Upload and Validate**.
6. Check upload status and validation issues.

### Domain expert/admin

1. Open the web app link.
2. Upload metadata when needed.
3. Later, metadata configuration screens can be added for editing site/inverter/rule values directly from frontend.

### Manager/viewer

1. Open Power BI dashboard.
2. Check upload status, errors, warnings, and trends.

---

## 13. What is already included

Included validation checks:

```text
SITE_NOT_FOUND
INVERTER_NOT_FOUND
MISSING_DATE
MISSING_REQUIRED_VALUE
NEGATIVE_VALUE
VDC_OUT_OF_RANGE
```

`VDC_OUT_OF_RANGE` is set as `warning` by default.
Most others are `error` by default.

Rows with warnings can still enter `daily_validated_data`.
Rows with errors do not enter `daily_validated_data`.

---

## 14. Important difference from MySQL version

MySQL used:

```text
AUTO_INCREMENT
ON DUPLICATE KEY UPDATE
mysql+pymysql connection
```

Supabase/PostgreSQL uses:

```text
GENERATED BY DEFAULT AS IDENTITY
ON CONFLICT DO UPDATE
postgresql+psycopg2 connection
```

---

## 15. Deployment recommendation

For quick testing:

```text
Run Streamlit locally + Supabase cloud DB
```

For team usage:

```text
Deploy Streamlit/Flask app online
Supabase remains the cloud database
Power BI connects to Supabase PostgreSQL
```

Best production-style flow:

```text
Team opens web app
↓
Uploads Excel
↓
Python backend processes file
↓
Supabase stores data
↓
Power BI dashboard shows results
```

---

## 16. What still needs to be added later

For full production, add:

```text
Supabase Auth login
Role-based access
Metadata edit screens
Inverter alias edit screen
Site alias edit screen
Power BI dashboard
Better file storage in Supabase Storage
Automated backups and security checks
```

This package gives you the Supabase database + processing foundation.
