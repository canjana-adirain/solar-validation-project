-- 02_process_daily_upload.sql
-- Run this after 01_create_tables_supabase.sql in Supabase SQL Editor.
-- This function processes one upload_id from raw_daily_staging.

CREATE OR REPLACE FUNCTION process_daily_upload(p_upload_id BIGINT)
RETURNS TABLE (
    upload_id BIGINT,
    staging_rows BIGINT,
    raw_history_rows BIGINT,
    error_count BIGINT,
    warning_count BIGINT,
    validated_rows BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_staging_rows BIGINT := 0;
    v_history_rows BIGINT := 0;
    v_error_count BIGINT := 0;
    v_warning_count BIGINT := 0;
    v_validated_rows BIGINT := 0;
BEGIN
    -- Remove old issues for this upload in case the upload is reprocessed.
    DELETE FROM validation_issues
    WHERE validation_issues.upload_id = p_upload_id;

    SELECT COUNT(*) INTO v_staging_rows
    FROM raw_daily_staging s
    WHERE s.upload_id = p_upload_id;

    -- Copy current staging rows into permanent raw history.
    INSERT INTO raw_daily_history (
        upload_id, row_no, raw_site_id, site_name, hw_id, inverter_name,
        reading_date, has_rsds,
        idc_total, idc_1, idc_2, idc_3, idc_4, idc_5, idc_6,
        vdc_avg, vdc_1, vdc_2, vdc_3, vdc_4, vdc_5, vdc_6
    )
    SELECT
        s.upload_id, s.row_no, s.raw_site_id, s.site_name, s.hw_id, s.inverter_name,
        s.reading_date, s.has_rsds,
        s.idc_total, s.idc_1, s.idc_2, s.idc_3, s.idc_4, s.idc_5, s.idc_6,
        s.vdc_avg, s.vdc_1, s.vdc_2, s.vdc_3, s.vdc_4, s.vdc_5, s.vdc_6
    FROM raw_daily_staging s
    WHERE s.upload_id = p_upload_id
    ON CONFLICT (upload_id, row_no) DO NOTHING;

    GET DIAGNOSTICS v_history_rows = ROW_COUNT;

    -- Validation 1: Site not found.
    INSERT INTO validation_issues (
        upload_id, row_no, site_name, hw_id, inverter_name, reading_date,
        issue_type, severity, issue_message
    )
    SELECT
        s.upload_id, s.row_no, s.site_name, s.hw_id, s.inverter_name, s.reading_date,
        'SITE_NOT_FOUND',
        COALESCE(rc.severity, 'error'),
        'Site not found in sites or site_alias: ' || COALESCE(s.site_name, '[blank]')
    FROM raw_daily_staging s
    LEFT JOIN sites st
        ON LOWER(TRIM(st.site_name)) = LOWER(TRIM(s.site_name))
    LEFT JOIN site_alias sa
        ON LOWER(TRIM(sa.raw_site_name)) = LOWER(TRIM(s.site_name))
       AND sa.is_active = TRUE
    LEFT JOIN validation_rule_config rc
        ON rc.rule_name = 'SITE_NOT_FOUND'
       AND rc.is_active = TRUE
    WHERE s.upload_id = p_upload_id
      AND st.site_id IS NULL
      AND sa.site_id IS NULL
      AND COALESCE(rc.is_active, TRUE) = TRUE;

    -- Validation 2: Missing/invalid date.
    INSERT INTO validation_issues (
        upload_id, row_no, site_name, hw_id, inverter_name, reading_date,
        issue_type, severity, issue_message
    )
    SELECT
        s.upload_id, s.row_no, s.site_name, s.hw_id, s.inverter_name, s.reading_date,
        'MISSING_DATE',
        COALESCE(rc.severity, 'error'),
        'Reading date is missing or invalid.'
    FROM raw_daily_staging s
    LEFT JOIN validation_rule_config rc
        ON rc.rule_name = 'MISSING_DATE'
       AND rc.is_active = TRUE
    WHERE s.upload_id = p_upload_id
      AND s.reading_date IS NULL
      AND COALESCE(rc.is_active, TRUE) = TRUE;

    -- Validation 3: Missing important fields.
    INSERT INTO validation_issues (
        upload_id, row_no, site_name, hw_id, inverter_name, reading_date,
        issue_type, severity, issue_message
    )
    SELECT
        s.upload_id, s.row_no, s.site_name, s.hw_id, s.inverter_name, s.reading_date,
        'MISSING_REQUIRED_VALUE',
        COALESCE(rc.severity, 'error'),
        'Required field missing: site_name, hw_id, inverter_name, or date.'
    FROM raw_daily_staging s
    LEFT JOIN validation_rule_config rc
        ON rc.rule_name = 'MISSING_REQUIRED_VALUE'
       AND rc.is_active = TRUE
    WHERE s.upload_id = p_upload_id
      AND (
          s.site_name IS NULL OR TRIM(s.site_name) = '' OR
          s.hw_id IS NULL OR TRIM(s.hw_id) = '' OR
          s.inverter_name IS NULL OR TRIM(s.inverter_name) = '' OR
          s.reading_date IS NULL
      )
      AND COALESCE(rc.is_active, TRUE) = TRUE;

    -- Validation 4: Inverter not found in metadata or inverter_alias.
    WITH mapped AS (
        SELECT
            s.*,
            COALESCE(sa.site_id, st.site_id) AS resolved_site_id
        FROM raw_daily_staging s
        LEFT JOIN sites st
            ON LOWER(TRIM(st.site_name)) = LOWER(TRIM(s.site_name))
        LEFT JOIN site_alias sa
            ON LOWER(TRIM(sa.raw_site_name)) = LOWER(TRIM(s.site_name))
           AND sa.is_active = TRUE
        WHERE s.upload_id = p_upload_id
    )
    INSERT INTO validation_issues (
        upload_id, row_no, site_id, site_name, hw_id, inverter_name, reading_date,
        issue_type, severity, issue_message
    )
    SELECT
        m.upload_id, m.row_no, m.resolved_site_id, m.site_name, m.hw_id, m.inverter_name, m.reading_date,
        'INVERTER_NOT_FOUND',
        COALESCE(rc.severity, 'error'),
        'Inverter not found in metadata_rulebook or inverter_alias: ' || COALESCE(m.inverter_name, '[blank]')
    FROM mapped m
    LEFT JOIN validation_rule_config rc
        ON rc.rule_name = 'INVERTER_NOT_FOUND'
       AND rc.is_active = TRUE
    WHERE m.resolved_site_id IS NOT NULL
      AND COALESCE(rc.is_active, TRUE) = TRUE
      AND NOT EXISTS (
          SELECT 1
          FROM metadata_rulebook mr
          WHERE mr.site_id = m.resolved_site_id
            AND LOWER(TRIM(mr.inverter_name)) = LOWER(TRIM(m.inverter_name))
      )
      AND NOT EXISTS (
          SELECT 1
          FROM inverter_alias ia
          WHERE ia.site_id = m.resolved_site_id
            AND ia.is_active = TRUE
            AND LOWER(TRIM(ia.raw_inverter_name)) = LOWER(TRIM(m.inverter_name))
      );

    -- Validation 5: Negative IDC/VDC values.
    INSERT INTO validation_issues (
        upload_id, row_no, site_name, hw_id, inverter_name, reading_date,
        issue_type, severity, issue_message
    )
    SELECT
        s.upload_id, s.row_no, s.site_name, s.hw_id, s.inverter_name, s.reading_date,
        'NEGATIVE_VALUE',
        COALESCE(rc.severity, 'error'),
        'Negative IDC or VDC value found.'
    FROM raw_daily_staging s
    LEFT JOIN validation_rule_config rc
        ON rc.rule_name = 'NEGATIVE_VALUE'
       AND rc.is_active = TRUE
    WHERE s.upload_id = p_upload_id
      AND COALESCE(rc.is_active, TRUE) = TRUE
      AND (
          s.idc_total < 0 OR s.idc_1 < 0 OR s.idc_2 < 0 OR s.idc_3 < 0 OR s.idc_4 < 0 OR s.idc_5 < 0 OR s.idc_6 < 0 OR
          s.vdc_avg < 0 OR s.vdc_1 < 0 OR s.vdc_2 < 0 OR s.vdc_3 < 0 OR s.vdc_4 < 0 OR s.vdc_5 < 0 OR s.vdc_6 < 0
      );

    -- Validation 6: VDC outside metadata MPPT range.
    WITH mapped AS (
        SELECT
            s.*,
            COALESCE(sa.site_id, st.site_id) AS resolved_site_id,
            COALESCE(ia.metadata_inverter_name, s.inverter_name) AS resolved_inverter_name
        FROM raw_daily_staging s
        LEFT JOIN sites st
            ON LOWER(TRIM(st.site_name)) = LOWER(TRIM(s.site_name))
        LEFT JOIN site_alias sa
            ON LOWER(TRIM(sa.raw_site_name)) = LOWER(TRIM(s.site_name))
           AND sa.is_active = TRUE
        LEFT JOIN inverter_alias ia
            ON ia.site_id = COALESCE(sa.site_id, st.site_id)
           AND ia.is_active = TRUE
           AND LOWER(TRIM(ia.raw_inverter_name)) = LOWER(TRIM(s.inverter_name))
        WHERE s.upload_id = p_upload_id
    ), mppt_values AS (
        SELECT
            m.upload_id, m.row_no, m.resolved_site_id, m.site_name, m.hw_id,
            m.resolved_inverter_name AS inverter_name, m.reading_date,
            v.mppt_no, v.idc, v.vdc
        FROM mapped m
        CROSS JOIN LATERAL (
            VALUES
                (1, m.idc_1, m.vdc_1),
                (2, m.idc_2, m.vdc_2),
                (3, m.idc_3, m.vdc_3),
                (4, m.idc_4, m.vdc_4),
                (5, m.idc_5, m.vdc_5),
                (6, m.idc_6, m.vdc_6)
        ) AS v(mppt_no, idc, vdc)
    )
    INSERT INTO validation_issues (
        upload_id, row_no, site_id, site_name, hw_id, inverter_name, reading_date, mppt_no,
        issue_type, severity, issue_message
    )
    SELECT
        mv.upload_id, mv.row_no, mv.resolved_site_id, mv.site_name, mv.hw_id, mv.inverter_name, mv.reading_date, mv.mppt_no,
        'VDC_OUT_OF_RANGE',
        COALESCE(rc.severity, 'warning'),
        'VDC ' || mv.vdc || ' outside expected range ' || mr.mppt_v_min || '-' || mr.mppt_v_max || ' for MPPT ' || mv.mppt_no
    FROM mppt_values mv
    JOIN metadata_rulebook mr
        ON mr.site_id = mv.resolved_site_id
       AND LOWER(TRIM(mr.inverter_name)) = LOWER(TRIM(mv.inverter_name))
       AND mr.mppt_no = mv.mppt_no
    LEFT JOIN validation_rule_config rc
        ON rc.rule_name = 'VDC_OUT_OF_RANGE'
       AND rc.is_active = TRUE
    WHERE mv.vdc IS NOT NULL
      AND mv.vdc <> 0
      AND mr.mppt_v_min IS NOT NULL
      AND mr.mppt_v_max IS NOT NULL
      AND COALESCE(rc.is_active, TRUE) = TRUE
      AND (mv.vdc < mr.mppt_v_min OR mv.vdc > mr.mppt_v_max);

    -- Insert good rows into permanent validated table.
    -- Rows with severity='warning' are allowed into final data.
    WITH mapped AS (
        SELECT
            s.*,
            COALESCE(sa.site_id, st.site_id) AS resolved_site_id
        FROM raw_daily_staging s
        LEFT JOIN sites st
            ON LOWER(TRIM(st.site_name)) = LOWER(TRIM(s.site_name))
        LEFT JOIN site_alias sa
            ON LOWER(TRIM(sa.raw_site_name)) = LOWER(TRIM(s.site_name))
           AND sa.is_active = TRUE
        WHERE s.upload_id = p_upload_id
    )
    INSERT INTO daily_validated_data (
        site_id, raw_site_id, site_name, hw_id, inverter_name, reading_date,
        has_rsds,
        idc_total, idc_1, idc_2, idc_3, idc_4, idc_5, idc_6,
        vdc_avg, vdc_1, vdc_2, vdc_3, vdc_4, vdc_5, vdc_6,
        source_upload_id
    )
    SELECT
        m.resolved_site_id,
        m.raw_site_id, m.site_name, m.hw_id, m.inverter_name, m.reading_date,
        m.has_rsds,
        m.idc_total, m.idc_1, m.idc_2, m.idc_3, m.idc_4, m.idc_5, m.idc_6,
        m.vdc_avg, m.vdc_1, m.vdc_2, m.vdc_3, m.vdc_4, m.vdc_5, m.vdc_6,
        m.upload_id
    FROM mapped m
    WHERE NOT EXISTS (
        SELECT 1
        FROM validation_issues vi
        WHERE vi.upload_id = m.upload_id
          AND vi.row_no = m.row_no
          AND vi.severity = 'error'
    )
      AND m.resolved_site_id IS NOT NULL
      AND m.site_name IS NOT NULL
      AND m.hw_id IS NOT NULL
      AND m.inverter_name IS NOT NULL
      AND m.reading_date IS NOT NULL
    ON CONFLICT (site_name, hw_id, inverter_name, reading_date)
    DO UPDATE SET
        site_id = EXCLUDED.site_id,
        raw_site_id = EXCLUDED.raw_site_id,
        has_rsds = EXCLUDED.has_rsds,
        idc_total = EXCLUDED.idc_total,
        idc_1 = EXCLUDED.idc_1,
        idc_2 = EXCLUDED.idc_2,
        idc_3 = EXCLUDED.idc_3,
        idc_4 = EXCLUDED.idc_4,
        idc_5 = EXCLUDED.idc_5,
        idc_6 = EXCLUDED.idc_6,
        vdc_avg = EXCLUDED.vdc_avg,
        vdc_1 = EXCLUDED.vdc_1,
        vdc_2 = EXCLUDED.vdc_2,
        vdc_3 = EXCLUDED.vdc_3,
        vdc_4 = EXCLUDED.vdc_4,
        vdc_5 = EXCLUDED.vdc_5,
        vdc_6 = EXCLUDED.vdc_6,
        source_upload_id = EXCLUDED.source_upload_id,
        updated_at = NOW();

    GET DIAGNOSTICS v_validated_rows = ROW_COUNT;

    SELECT COUNT(*) INTO v_error_count
    FROM validation_issues vi
    WHERE vi.upload_id = p_upload_id
      AND vi.severity = 'error';

    SELECT COUNT(*) INTO v_warning_count
    FROM validation_issues vi
    WHERE vi.upload_id = p_upload_id
      AND vi.severity = 'warning';

    UPDATE upload_batch
    SET status = CASE WHEN v_error_count > 0 THEN 'completed_with_errors' ELSE 'completed' END,
        remarks = 'Processed rows=' || v_staging_rows || ', inserted/updated validated=' || v_validated_rows || ', errors=' || v_error_count || ', warnings=' || v_warning_count
    WHERE upload_batch.upload_id = p_upload_id;

    RETURN QUERY SELECT p_upload_id, v_staging_rows, v_history_rows, v_error_count, v_warning_count, v_validated_rows;
END;
$$;
