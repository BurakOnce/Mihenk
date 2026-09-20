-- dimension yükleme prosedürleri: type 2 boyutların bronze snapshot'larından geçmişle
-- ilk yüklemesi (backfill) ve type 1 / mdm boyutlarının silver'dan yüklenmesi.
-- dealer için kalıp 30_scd2_pattern.sql'de; buradakiler aynı kalıbı izliyor.
-- bronze'dan okunan tutarlar türkçe ondalık ("1989500,0") olduğu için TRY_CAST(REPLACE(...)).

CREATE PROCEDURE gold.usp_backfill_dim_employee
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM gold.dim_employee WHERE employee_sk > 0)
    BEGIN
        SELECT 'SKIPPED' AS outcome, 'dim_employee already populated' AS reason;
        RETURN;
    END;

    WITH snapshots AS
    (
        SELECT employee_id, full_name, first_name, last_name, dealer_code,
               role_code, email, hire_date, is_active,
               CAST(last_modified_ts AS DATE) AS observed_date,
               ROW_NUMBER() OVER (PARTITION BY employee_id, CAST(last_modified_ts AS DATE)
                                  ORDER BY _ingest_ts DESC) AS rn
        FROM mihenk_lh.bronze.dms_employee
        WHERE employee_id IS NOT NULL AND employee_id <> ''
    ),
    hashed AS
    (
        SELECT s.*,
               CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', CONCAT_WS('||',
                   ISNULL(full_name, ''), ISNULL(dealer_code, ''),
                   ISNULL(role_code, ''), ISNULL(email, ''),
                   ISNULL(CAST(is_active AS VARCHAR(1)), '')
               )), 2) AS row_hash
        FROM snapshots AS s WHERE s.rn = 1
    ),
    versions AS
    (
        SELECT * FROM (
            SELECT h.*, LAG(h.row_hash) OVER (PARTITION BY h.employee_id
                                              ORDER BY h.observed_date) AS previous_hash
            FROM hashed AS h
        ) AS b
        WHERE previous_hash IS NULL OR previous_hash <> row_hash
    ),
    ranged AS
    (
        SELECT v.*, LEAD(v.observed_date) OVER (PARTITION BY v.employee_id
                                                ORDER BY v.observed_date) AS next_version_start
        FROM versions AS v
    )
    INSERT INTO gold.dim_employee
    (employee_sk, employee_id, full_name, first_name, last_name, dealer_code,
     role_code, email, hire_date, is_active, is_inferred,
     valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts)
    SELECT
        ROW_NUMBER() OVER (ORDER BY r.employee_id, r.observed_date)
            + ISNULL((SELECT MAX(employee_sk) FROM gold.dim_employee WHERE employee_sk > 0), 0),
        r.employee_id, r.full_name, r.first_name, r.last_name, r.dealer_code,
        r.role_code, r.email, r.hire_date, r.is_active, 0,
        r.observed_date, ISNULL(r.next_version_start, '9999-12-31'),
        CASE WHEN r.next_version_start IS NULL THEN 1 ELSE 0 END,
        r.row_hash, @batch_id, SYSDATETIME()
    FROM ranged AS r;

    INSERT INTO gold.dim_employee
    (employee_sk, employee_id, full_name, first_name, last_name, dealer_code,
     role_code, email, hire_date, is_active, is_inferred,
     valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts)
    SELECT * FROM (VALUES
        (-1, '-1', 'Bilinmiyor',  NULL, NULL, NULL, 'UNKNOWN', NULL, NULL, 0, 0,
         '1900-01-01', '9999-12-31', 1, NULL, NULL, SYSDATETIME()),
        (-2, '-2', 'Uygulanamaz', NULL, NULL, NULL, 'NA',      NULL, NULL, 0, 0,
         '1900-01-01', '9999-12-31', 1, NULL, NULL, SYSDATETIME())
    ) AS v (employee_sk, employee_id, full_name, first_name, last_name, dealer_code,
            role_code, email, hire_date, is_active, is_inferred,
            valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts);

    SELECT COUNT(*) AS versions_created, COUNT(DISTINCT employee_id) AS distinct_employees
    FROM gold.dim_employee WHERE employee_sk > 0;
END;
GO

CREATE PROCEDURE gold.usp_backfill_dim_model_trim
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM gold.dim_model_trim WHERE model_trim_sk > 0)
    BEGIN
        SELECT 'SKIPPED' AS outcome, 'dim_model_trim already populated' AS reason;
        RETURN;
    END;

    WITH snapshots AS
    (
        SELECT model_trim_code, brand, model_name, trim_name, model_year, body_type,
               segment, engine_cc, fuel_type, transmission, warranty_months,
               warranty_km, list_price_try, is_active,
               CAST(last_modified_ts AS DATE) AS observed_date,
               ROW_NUMBER() OVER (PARTITION BY model_trim_code, CAST(last_modified_ts AS DATE)
                                  ORDER BY _ingest_ts DESC) AS rn
        FROM mihenk_lh.bronze.dms_model_trim
        WHERE model_trim_code IS NOT NULL AND model_trim_code <> ''
    ),
    hashed AS
    (
        SELECT s.*,
               CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', CONCAT_WS('||',
                   ISNULL(brand, ''), ISNULL(model_name, ''), ISNULL(trim_name, ''),
                   ISNULL(CAST(model_year AS VARCHAR(6)), ''),
                   ISNULL(CAST(list_price_try AS VARCHAR(30)), ''),
                   ISNULL(CAST(warranty_months AS VARCHAR(6)), ''),
                   ISNULL(CAST(is_active AS VARCHAR(1)), '')
               )), 2) AS row_hash
        FROM snapshots AS s WHERE s.rn = 1
    ),
    versions AS
    (
        SELECT * FROM (
            SELECT h.*, LAG(h.row_hash) OVER (PARTITION BY h.model_trim_code
                                              ORDER BY h.observed_date) AS previous_hash
            FROM hashed AS h
        ) AS b
        WHERE previous_hash IS NULL OR previous_hash <> row_hash
    ),
    ranged AS
    (
        SELECT v.*, LEAD(v.observed_date) OVER (PARTITION BY v.model_trim_code
                                                ORDER BY v.observed_date) AS next_version_start
        FROM versions AS v
    )
    INSERT INTO gold.dim_model_trim
    (model_trim_sk, model_trim_code, brand, model_name, trim_name, model_year,
     body_type, segment, engine_cc, fuel_type, transmission, warranty_months,
     warranty_km, list_price_amount, is_active, is_inferred,
     valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts)
    SELECT
        ROW_NUMBER() OVER (ORDER BY r.model_trim_code, r.observed_date)
            + ISNULL((SELECT MAX(model_trim_sk) FROM gold.dim_model_trim WHERE model_trim_sk > 0), 0),
        r.model_trim_code, r.brand, r.model_name, r.trim_name, r.model_year,
        r.body_type, r.segment, r.engine_cc, r.fuel_type, r.transmission,
        r.warranty_months, r.warranty_km, TRY_CAST(REPLACE(r.list_price_try, ',', '.') AS DECIMAL(18,2)), r.is_active, 0,
        r.observed_date, ISNULL(r.next_version_start, '9999-12-31'),
        CASE WHEN r.next_version_start IS NULL THEN 1 ELSE 0 END,
        r.row_hash, @batch_id, SYSDATETIME()
    FROM ranged AS r;

    INSERT INTO gold.dim_model_trim
    (model_trim_sk, model_trim_code, brand, model_name, trim_name, model_year,
     body_type, segment, engine_cc, fuel_type, transmission, warranty_months,
     warranty_km, list_price_amount, is_active, is_inferred,
     valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts)
    SELECT * FROM (VALUES
        (-1, '-1', 'Bilinmiyor', 'Bilinmiyor', NULL, NULL, NULL, NULL, NULL, NULL,
         NULL, NULL, NULL, NULL, 0, 0, '1900-01-01', '9999-12-31', 1, NULL, NULL, SYSDATETIME()),
        (-2, '-2', 'Uygulanamaz', 'Uygulanamaz', NULL, NULL, NULL, NULL, NULL, NULL,
         NULL, NULL, NULL, NULL, 0, 0, '1900-01-01', '9999-12-31', 1, NULL, NULL, SYSDATETIME())
    ) AS v (model_trim_sk, model_trim_code, brand, model_name, trim_name, model_year,
            body_type, segment, engine_cc, fuel_type, transmission, warranty_months,
            warranty_km, list_price_amount, is_active, is_inferred,
            valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts);

    SELECT COUNT(*) AS versions_created, COUNT(DISTINCT model_trim_code) AS distinct_trims
    FROM gold.dim_model_trim WHERE model_trim_sk > 0;
END;
GO

CREATE PROCEDURE gold.usp_backfill_dim_part
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM gold.dim_part WHERE part_sk > 0)
    BEGIN
        SELECT 'SKIPPED' AS outcome, 'dim_part already populated' AS reason;
        RETURN;
    END;

    WITH snapshots AS
    (
        SELECT part_no, part_name, part_group_code, part_group_name, is_genuine,
               supplier_id, unit_of_measure, list_price_try, is_active,
               CAST(last_modified_ts AS DATE) AS observed_date,
               ROW_NUMBER() OVER (PARTITION BY part_no, CAST(last_modified_ts AS DATE)
                                  ORDER BY _ingest_ts DESC) AS rn
        FROM mihenk_lh.bronze.parts_part
        WHERE part_no IS NOT NULL AND part_no <> ''
    ),
    hashed AS
    (
        SELECT s.*,
               CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', CONCAT_WS('||',
                   ISNULL(part_name, ''), ISNULL(part_group_code, ''),
                   ISNULL(CAST(is_genuine AS VARCHAR(1)), ''), ISNULL(supplier_id, ''),
                   ISNULL(CAST(list_price_try AS VARCHAR(30)), ''),
                   ISNULL(CAST(is_active AS VARCHAR(1)), '')
               )), 2) AS row_hash
        FROM snapshots AS s WHERE s.rn = 1
    ),
    versions AS
    (
        SELECT * FROM (
            SELECT h.*, LAG(h.row_hash) OVER (PARTITION BY h.part_no
                                              ORDER BY h.observed_date) AS previous_hash
            FROM hashed AS h
        ) AS b
        WHERE previous_hash IS NULL OR previous_hash <> row_hash
    ),
    ranged AS
    (
        SELECT v.*, LEAD(v.observed_date) OVER (PARTITION BY v.part_no
                                                ORDER BY v.observed_date) AS next_version_start
        FROM versions AS v
    )
    INSERT INTO gold.dim_part
    (part_sk, part_no, part_name, part_group_code, part_group_name, is_genuine,
     supplier_id, unit_of_measure, list_price_amount, is_active, is_inferred,
     valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts)
    SELECT
        ROW_NUMBER() OVER (ORDER BY r.part_no, r.observed_date)
            + ISNULL((SELECT MAX(part_sk) FROM gold.dim_part WHERE part_sk > 0), 0),
        r.part_no, r.part_name, r.part_group_code, r.part_group_name, r.is_genuine,
        r.supplier_id, r.unit_of_measure, TRY_CAST(REPLACE(r.list_price_try, ',', '.') AS DECIMAL(18,2)), r.is_active, 0,
        r.observed_date, ISNULL(r.next_version_start, '9999-12-31'),
        CASE WHEN r.next_version_start IS NULL THEN 1 ELSE 0 END,
        r.row_hash, @batch_id, SYSDATETIME()
    FROM ranged AS r;

    INSERT INTO gold.dim_part
    (part_sk, part_no, part_name, part_group_code, part_group_name, is_genuine,
     supplier_id, unit_of_measure, list_price_amount, is_active, is_inferred,
     valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts)
    SELECT * FROM (VALUES
        (-1, '-1', 'Bilinmiyor',  NULL, NULL, 0, NULL, NULL, NULL, 0, 0,
         '1900-01-01', '9999-12-31', 1, NULL, NULL, SYSDATETIME()),
        (-2, '-2', 'Uygulanamaz', NULL, NULL, 0, NULL, NULL, NULL, 0, 0,
         '1900-01-01', '9999-12-31', 1, NULL, NULL, SYSDATETIME())
    ) AS v (part_sk, part_no, part_name, part_group_code, part_group_name, is_genuine,
            supplier_id, unit_of_measure, list_price_amount, is_active, is_inferred,
            valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts);

    SELECT COUNT(*) AS versions_created, COUNT(DISTINCT part_no) AS distinct_parts
    FROM gold.dim_part WHERE part_sk > 0;
END;
GO

CREATE PROCEDURE gold.usp_backfill_dim_vehicle
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM gold.dim_vehicle WHERE vehicle_sk > 0)
    BEGIN
        SELECT 'SKIPPED' AS outcome, 'dim_vehicle already populated' AS reason;
        RETURN;
    END;

    WITH snapshots AS
    (
        SELECT
            UPPER(vin) AS vin, model_trim_code, model_year, colour, engine_no,
            production_date, arrival_date, status, stock_dealer_code,
            plate_number, owner_customer_id, dealer_cost_try,
            CAST(last_modified_ts AS DATE) AS observed_date,
            ROW_NUMBER() OVER (PARTITION BY UPPER(vin), CAST(last_modified_ts AS DATE)
                               ORDER BY _ingest_ts DESC) AS rn
        FROM mihenk_lh.bronze.dms_vehicle_stock
        WHERE vin IS NOT NULL AND vin <> ''
    ),
    resolved AS
    (

        SELECT s.*, x.master_customer_id
        FROM snapshots AS s
        LEFT JOIN mihenk_lh.silver.customer_xref AS x ON x.dms_customer_id = s.owner_customer_id
        WHERE s.rn = 1
    ),
    hashed AS
    (
        SELECT r.*,
               CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', CONCAT_WS('||',
                   ISNULL(status, ''), ISNULL(stock_dealer_code, ''),
                   ISNULL(plate_number, ''), ISNULL(master_customer_id, ''),
                   ISNULL(CAST(dealer_cost_try AS VARCHAR(30)), '')
               )), 2) AS row_hash
        FROM resolved AS r
    ),
    versions AS
    (
        SELECT * FROM (
            SELECT h.*, LAG(h.row_hash) OVER (PARTITION BY h.vin
                                              ORDER BY h.observed_date) AS previous_hash
            FROM hashed AS h
        ) AS b
        WHERE previous_hash IS NULL OR previous_hash <> row_hash
    ),
    ranged AS
    (
        SELECT v.*,
               LEAD(v.observed_date) OVER (PARTITION BY v.vin
                                           ORDER BY v.observed_date) AS next_version_start,

               CASE WHEN ISNULL(LAG(v.master_customer_id) OVER (PARTITION BY v.vin
                                                                ORDER BY v.observed_date), '~')
                         = ISNULL(v.master_customer_id, '~')
                    THEN NULL ELSE v.observed_date END AS owner_change_date
        FROM versions AS v
    )
    INSERT INTO gold.dim_vehicle
    (vehicle_sk, vin, model_trim_code, model_year, colour, production_date,
     arrival_date, engine_no, status, stock_dealer_code, plate_hash, plate_masked,
     master_customer_id, owner_since_date, dealer_cost_amount,
     vin_well_formed, vin_check_digit_valid, is_inferred,
     valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts)
    SELECT
        ROW_NUMBER() OVER (ORDER BY r.vin, r.observed_date)
            + ISNULL((SELECT MAX(vehicle_sk) FROM gold.dim_vehicle WHERE vehicle_sk > 0), 0),
        r.vin, r.model_trim_code, r.model_year, r.colour, r.production_date,
        r.arrival_date, r.engine_no, r.status, r.stock_dealer_code,
        sv.plate_hash, sv.plate_number_masked,
        r.master_customer_id,
        COALESCE(r.owner_change_date,
                 MAX(r.owner_change_date) OVER (PARTITION BY r.vin, r.master_customer_id)),
        TRY_CAST(REPLACE(r.dealer_cost_try, ',', '.') AS DECIMAL(18,2)),
        sv.vin_well_formed, sv.vin_check_digit_valid, 0,
        r.observed_date, ISNULL(r.next_version_start, '9999-12-31'),
        CASE WHEN r.next_version_start IS NULL THEN 1 ELSE 0 END,
        r.row_hash, @batch_id, SYSDATETIME()
    FROM ranged AS r

    LEFT JOIN mihenk_lh.silver.vehicle AS sv ON sv.vin = r.vin;

    INSERT INTO gold.dim_vehicle
    (vehicle_sk, vin, model_trim_code, model_year, colour, production_date,
     arrival_date, engine_no, status, stock_dealer_code, plate_hash, plate_masked,
     master_customer_id, owner_since_date, dealer_cost_amount,
     vin_well_formed, vin_check_digit_valid, is_inferred,
     valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts)
    SELECT * FROM (VALUES
        (-1, '-1', NULL, NULL, 'Bilinmiyor', NULL, NULL, NULL, 'UNKNOWN', NULL,
         NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0,
         '1900-01-01', '9999-12-31', 1, NULL, NULL, SYSDATETIME()),
        (-2, '-2', NULL, NULL, 'Uygulanamaz', NULL, NULL, NULL, 'NA', NULL,
         NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0,
         '1900-01-01', '9999-12-31', 1, NULL, NULL, SYSDATETIME())
    ) AS v (vehicle_sk, vin, model_trim_code, model_year, colour, production_date,
            arrival_date, engine_no, status, stock_dealer_code, plate_hash, plate_masked,
            master_customer_id, owner_since_date, dealer_cost_amount,
            vin_well_formed, vin_check_digit_valid, is_inferred,
            valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts);

    SELECT COUNT(*) AS versions_created,
           COUNT(DISTINCT vin) AS distinct_vehicles,
           COUNT(DISTINCT CASE WHEN master_customer_id IS NOT NULL THEN vin END) AS owned_vehicles
    FROM gold.dim_vehicle WHERE vehicle_sk > 0;
END;
GO


CREATE PROCEDURE gold.usp_load_dim_service_type
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;
    DELETE FROM gold.dim_service_type;

    INSERT INTO gold.dim_service_type
    (service_type_sk, service_type_code, service_type_name_tr, service_type_name_en,
     is_warranty_eligible, is_scheduled, typical_labour_hours, _row_hash, _batch_id, _loaded_ts)
    SELECT sk, code, tr, en, warranty, scheduled, hours, NULL, @batch_id, SYSDATETIME()
    FROM (VALUES
        ( 1, 'MAINT',    'Periyodik Bakım',     'Scheduled maintenance', 0, 1,  2.0),
        ( 2, 'REPAIR',   'Arıza Onarımı',       'Fault repair',          0, 0,  3.5),
        ( 3, 'WARRANTY', 'Garanti Onarımı',     'Warranty repair',       1, 0,  4.0),
        ( 4, 'BODY',     'Kaporta-Boya',        'Body and paint',        0, 0, 12.0),
        ( 5, 'TYRE',     'Lastik / Mevsimsel',  'Tyre and seasonal',     0, 0,  1.0),
        ( 6, 'RECALL',   'Geri Çağırma',        'Recall campaign',       1, 0,  1.5),
        ( 7, 'INSPECT',  'Ekspertiz',           'Inspection',            0, 0,  1.0),
        (-1, '-1',       'Bilinmiyor',          'Unknown',               0, 0,  0.0),
        (-2, '-2',       'Uygulanamaz',         'Not applicable',        0, 0,  0.0)
    ) AS v (sk, code, tr, en, warranty, scheduled, hours);

    SELECT COUNT(*) AS rows_loaded FROM gold.dim_service_type;
END;
GO

CREATE PROCEDURE gold.usp_load_dim_supplier
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE gold.dim_supplier
    SET supplier_name  = s.supplier_name,
        country_code   = s.country_code,
        is_domestic    = CASE WHEN s.country_code = 'TR' THEN 1 ELSE 0 END,
        lead_time_days = s.lead_time_days,
        contact_email  = s.contact_email,
        is_active      = s.is_active,
        _batch_id      = @batch_id,
        _loaded_ts     = SYSDATETIME()
    FROM gold.dim_supplier AS d
    INNER JOIN mihenk_lh.silver.supplier AS s ON s.supplier_id = d.supplier_id;

    INSERT INTO gold.dim_supplier
    (supplier_sk, supplier_id, supplier_name, country_code, is_domestic,
     lead_time_days, contact_email, is_active, _row_hash, _batch_id, _loaded_ts)
    SELECT
        ROW_NUMBER() OVER (ORDER BY s.supplier_id)
            + ISNULL((SELECT MAX(supplier_sk) FROM gold.dim_supplier WHERE supplier_sk > 0), 0),
        s.supplier_id, s.supplier_name, s.country_code,
        CASE WHEN s.country_code = 'TR' THEN 1 ELSE 0 END,
        s.lead_time_days, s.contact_email, s.is_active,
        NULL, @batch_id, SYSDATETIME()
    FROM mihenk_lh.silver.supplier AS s
    WHERE NOT EXISTS (SELECT 1 FROM gold.dim_supplier AS d WHERE d.supplier_id = s.supplier_id);

    IF NOT EXISTS (SELECT 1 FROM gold.dim_supplier WHERE supplier_sk = -1)
        INSERT INTO gold.dim_supplier
        (supplier_sk, supplier_id, supplier_name, country_code, is_domestic,
         lead_time_days, contact_email, is_active, _row_hash, _batch_id, _loaded_ts)
        SELECT * FROM (VALUES
            (-1, '-1', 'Bilinmiyor',  NULL, 0, NULL, NULL, 0, NULL, NULL, SYSDATETIME()),
            (-2, '-2', 'Uygulanamaz', NULL, 0, NULL, NULL, 0, NULL, NULL, SYSDATETIME())
        ) AS v (supplier_sk, supplier_id, supplier_name, country_code, is_domestic,
                lead_time_days, contact_email, is_active, _row_hash, _batch_id, _loaded_ts);

    SELECT COUNT(*) AS rows_loaded FROM gold.dim_supplier;
END;
GO

CREATE PROCEDURE gold.usp_load_dim_customer
    @batch_id       VARCHAR(40),
    @effective_date DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET @effective_date = ISNULL(@effective_date, CAST(SYSDATETIME() AS DATE));

    -- CREATE TABLE #t + INSERT INTO #t değil, SELECT ... INTO #t - 30_scd2_pattern.sql'deki
    -- nota bak. change_type'a açık CAST gerekiyor; çıplak NULL'dan tip çıkarılamıyor.
    SELECT
        c.master_customer_id, c.customer_type, c.full_name,
        c.identity_hash, c.identity_no_masked, c.phone_hash, c.phone_masked,
        c.email_hash, c.email_masked, c.city, c.city_code,

        p.region,
        c.lead_source, c.consent_kvkk, c.customer_since AS customer_since_date, c.source_presence,
        c.match_score,
        CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', CONCAT_WS('||',
            ISNULL(c.customer_type, ''), ISNULL(c.full_name, ''),
            ISNULL(c.city, ''), ISNULL(c.city_code, ''),
            ISNULL(c.lead_source, ''), ISNULL(CAST(c.consent_kvkk AS VARCHAR(1)), ''),
            ISNULL(c.source_presence, '')
        )), 2) AS row_hash,
        CAST(NULL AS VARCHAR(10)) AS change_type
    INTO #source
    FROM mihenk_lh.silver.customer AS c
    LEFT JOIN gold.ref_province AS p ON p.province_code = c.city_code
    WHERE c.master_customer_id IS NOT NULL;

    UPDATE #source
    SET change_type =
        CASE
            WHEN NOT EXISTS (SELECT 1 FROM gold.dim_customer AS d
                             WHERE d.master_customer_id = #source.master_customer_id)
                THEN 'NEW'
            WHEN EXISTS (SELECT 1 FROM gold.dim_customer AS d
                         WHERE d.master_customer_id = #source.master_customer_id
                           AND d.is_current = 1 AND d._row_hash <> #source.row_hash)
                THEN 'CHANGED'
            ELSE 'UNCHANGED'
        END;

    BEGIN TRANSACTION;

    UPDATE gold.dim_customer
    SET valid_to = @effective_date, is_current = 0,
        _batch_id = @batch_id, _loaded_ts = SYSDATETIME()
    WHERE is_current = 1
      AND EXISTS (SELECT 1 FROM #source AS s
                  WHERE s.master_customer_id = gold.dim_customer.master_customer_id
                    AND s.change_type = 'CHANGED');

    INSERT INTO gold.dim_customer
    (customer_sk, master_customer_id, customer_type, full_name, identity_hash,
     identity_no_masked, phone_hash, phone_masked, email_hash, email_masked,
     city, city_code, region, lead_source, consent_kvkk, customer_since_date,
     source_presence, match_score, is_inferred,
     valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts)
    SELECT
        ROW_NUMBER() OVER (ORDER BY s.master_customer_id)
            + ISNULL((SELECT MAX(customer_sk) FROM gold.dim_customer WHERE customer_sk > 0), 0),
        s.master_customer_id, s.customer_type, s.full_name, s.identity_hash,
        s.identity_no_masked, s.phone_hash, s.phone_masked, s.email_hash, s.email_masked,
        s.city, s.city_code, s.region, s.lead_source, s.consent_kvkk,
        s.customer_since_date, s.source_presence, s.match_score, 0,

        CASE WHEN s.change_type = 'NEW'
             THEN ISNULL(s.customer_since_date, @effective_date)
             ELSE @effective_date END,
        '9999-12-31', 1,
        s.row_hash, @batch_id, SYSDATETIME()
    FROM #source AS s
    WHERE s.change_type IN ('NEW', 'CHANGED');

    COMMIT TRANSACTION;

    IF NOT EXISTS (SELECT 1 FROM gold.dim_customer WHERE customer_sk = -1)
        INSERT INTO gold.dim_customer
        (customer_sk, master_customer_id, customer_type, full_name, identity_hash,
         identity_no_masked, phone_hash, phone_masked, email_hash, email_masked,
         city, city_code, region, lead_source, consent_kvkk, customer_since_date,
         source_presence, match_score, is_inferred,
         valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts)
        SELECT * FROM (VALUES
            (-1, '-1', 'UNKNOWN', 'Bilinmiyor', NULL, NULL, NULL, NULL, NULL, NULL,
             NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0,
             '1900-01-01', '9999-12-31', 1, NULL, NULL, SYSDATETIME()),
            (-2, '-2', 'NA', 'Uygulanamaz', NULL, NULL, NULL, NULL, NULL, NULL,
             NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0,
             '1900-01-01', '9999-12-31', 1, NULL, NULL, SYSDATETIME())
        ) AS v (customer_sk, master_customer_id, customer_type, full_name, identity_hash,
                identity_no_masked, phone_hash, phone_masked, email_hash, email_masked,
                city, city_code, region, lead_source, consent_kvkk, customer_since_date,
                source_presence, match_score, is_inferred,
                valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts);

    DROP TABLE #source;

    SELECT
        (SELECT COUNT(*) FROM gold.dim_customer WHERE _batch_id = @batch_id) AS rows_touched,
        (SELECT COUNT(*) FROM gold.dim_customer WHERE is_current = 1 AND customer_sk > 0) AS open_versions;
END;
GO

CREATE PROCEDURE gold.usp_load_dim_transaction_flag
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;

    -- CREATE TABLE #t + INSERT INTO #t değil, SELECT ... INTO #t (fabric warehouse
    -- reddediyor, 30_scd2_pattern.sql'deki nota bak). iki kaynak olduğu için iki
    -- INSERT tek bir UNION ALL'a katlanıyor, böylece tek SELECT INTO kalıyor.
    SELECT is_campaign, payment_type, channel, is_used_vehicle, is_warranty, has_trade_in
    INTO #combinations
    FROM (
        SELECT DISTINCT
            ISNULL(is_campaign, 0) AS is_campaign,
            ISNULL(payment_type, 'NA') AS payment_type,
            ISNULL(channel, 'NA') AS channel,
            CASE WHEN sale_type = 'USED' THEN 1 ELSE 0 END AS is_used_vehicle,
            0 AS is_warranty,
            CASE WHEN trade_in_vin IS NOT NULL AND trade_in_vin <> '' THEN 1 ELSE 0 END AS has_trade_in
        FROM mihenk_lh.silver.sales_contract

        UNION ALL

        SELECT DISTINCT 0, 'NA', 'NA', 0, ISNULL(is_warranty, 0), 0
        FROM mihenk_lh.silver.repair_order
    ) AS combos;

    DELETE FROM gold.dim_transaction_flag;

    INSERT INTO gold.dim_transaction_flag
    (transaction_flag_sk, is_campaign, payment_type, channel,
     is_used_vehicle, is_warranty, has_trade_in, flag_description, _row_hash, _loaded_ts)
    SELECT
        ROW_NUMBER() OVER (ORDER BY payment_type, channel, is_campaign,
                                    is_used_vehicle, is_warranty, has_trade_in),
        is_campaign, payment_type, channel, is_used_vehicle, is_warranty, has_trade_in,

        CONCAT_WS(', ',
            CASE WHEN is_campaign = 1 THEN 'Kampanyalı' END,
            CASE WHEN payment_type <> 'NA' THEN payment_type END,
            CASE WHEN channel <> 'NA' THEN channel END,
            CASE WHEN is_used_vehicle = 1 THEN 'İkinci el' END,
            CASE WHEN is_warranty = 1 THEN 'Garanti' END,
            CASE WHEN has_trade_in = 1 THEN 'Takaslı' END
        ),
        NULL, SYSDATETIME()
    FROM (SELECT DISTINCT * FROM #combinations) AS c;

    INSERT INTO gold.dim_transaction_flag
    (transaction_flag_sk, is_campaign, payment_type, channel,
     is_used_vehicle, is_warranty, has_trade_in, flag_description, _row_hash, _loaded_ts)
    VALUES (-1, 0, 'NA', 'NA', 0, 0, 0, 'Bilinmiyor', NULL, SYSDATETIME());

    DROP TABLE #combinations;
    SELECT COUNT(*) AS rows_loaded FROM gold.dim_transaction_flag;
END;
GO
