
CREATE PROCEDURE gold.usp_create_inferred_members
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;

    -- SELECT ... INTO #t, not CREATE TABLE #t + INSERT INTO #t (rejected on
    -- Fabric Warehouse, see the note in 30_scd2_pattern.sql) - same fix
    -- applies to all three #missing_* temp tables in this procedure.
    SELECT vin, MIN(first_seen) AS first_seen
    INTO #missing_vin
    FROM (
        SELECT UPPER(vin) AS vin, CAST(checkin_ts AS DATE) AS first_seen
        FROM mihenk_lh.silver.repair_order
        WHERE vin IS NOT NULL AND vin <> ''
        UNION ALL
        SELECT UPPER(vin), contract_date FROM mihenk_lh.silver.sales_contract
        WHERE vin IS NOT NULL AND vin <> ''
        UNION ALL

        SELECT UPPER(trade_in_vin), contract_date FROM mihenk_lh.silver.sales_contract
        WHERE trade_in_vin IS NOT NULL AND trade_in_vin <> ''
        UNION ALL
        SELECT UPPER(vin), notified_date FROM mihenk_lh.silver.recall_coverage
        WHERE vin IS NOT NULL AND vin <> ''
    ) AS referenced
    WHERE NOT EXISTS (SELECT 1 FROM gold.dim_vehicle AS d WHERE d.vin = referenced.vin)
    GROUP BY vin;

    INSERT INTO gold.dim_vehicle
    (vehicle_sk, vin, model_trim_code, model_year, colour, production_date,
     arrival_date, engine_no, status, stock_dealer_code, plate_hash, plate_masked,
     master_customer_id, owner_since_date, dealer_cost_amount,
     vin_well_formed, vin_check_digit_valid, is_inferred,
     valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts)
    SELECT
        ROW_NUMBER() OVER (ORDER BY m.vin)
            + ISNULL((SELECT MAX(vehicle_sk) FROM gold.dim_vehicle WHERE vehicle_sk > 0), 0),
        m.vin, NULL, NULL, NULL, NULL, NULL, NULL, 'EXTERNAL', NULL, NULL, NULL,
        NULL, NULL, NULL,
        NULL, NULL,
        1,

        m.first_seen, '9999-12-31', 1,
        NULL, @batch_id, SYSDATETIME()
    FROM #missing_vin AS m;

    DECLARE @inferred_vehicles INT = @@ROWCOUNT;

    SELECT master_customer_id, MIN(first_seen) AS first_seen
    INTO #missing_customer
    FROM (
        SELECT master_customer_id, contract_date AS first_seen
        FROM mihenk_lh.silver.sales_contract WHERE master_customer_id IS NOT NULL
        UNION ALL
        SELECT master_customer_id, CAST(checkin_ts AS DATE)
        FROM mihenk_lh.silver.repair_order WHERE master_customer_id IS NOT NULL
    ) AS referenced
    WHERE NOT EXISTS (SELECT 1 FROM gold.dim_customer AS d
                      WHERE d.master_customer_id = referenced.master_customer_id)
    GROUP BY master_customer_id;

    INSERT INTO gold.dim_customer
    (customer_sk, master_customer_id, customer_type, full_name, identity_hash,
     identity_no_masked, phone_hash, phone_masked, email_hash, email_masked,
     city, city_code, region, lead_source, consent_kvkk, customer_since_date,
     source_presence, match_score, is_inferred,
     valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts)
    SELECT
        ROW_NUMBER() OVER (ORDER BY m.master_customer_id)
            + ISNULL((SELECT MAX(customer_sk) FROM gold.dim_customer WHERE customer_sk > 0), 0),
        m.master_customer_id, 'UNKNOWN', 'Çıkarsanmış müşteri',
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        m.first_seen, NULL, NULL, 1,
        m.first_seen, '9999-12-31', 1, NULL, @batch_id, SYSDATETIME()
    FROM #missing_customer AS m;

    DECLARE @inferred_customers INT = @@ROWCOUNT;

    SELECT l.part_no, MIN(CAST(o.checkin_ts AS DATE)) AS first_seen
    INTO #missing_part
    FROM mihenk_lh.silver.repair_order_line AS l
    INNER JOIN mihenk_lh.silver.repair_order AS o ON o.repair_order_no = l.repair_order_no
    WHERE l.part_no IS NOT NULL AND l.part_no <> ''
      AND NOT EXISTS (SELECT 1 FROM gold.dim_part AS d WHERE d.part_no = l.part_no)
    GROUP BY l.part_no;

    INSERT INTO gold.dim_part
    (part_sk, part_no, part_name, part_group_code, part_group_name, is_genuine,
     supplier_id, unit_of_measure, list_price_amount, is_active, is_inferred,
     valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts)
    SELECT
        ROW_NUMBER() OVER (ORDER BY m.part_no)
            + ISNULL((SELECT MAX(part_sk) FROM gold.dim_part WHERE part_sk > 0), 0),
        m.part_no, 'Çıkarsanmış parça', 'UNKNOWN', 'Bilinmiyor', NULL,
        NULL, NULL, NULL, 1, 1,
        m.first_seen, '9999-12-31', 1, NULL, @batch_id, SYSDATETIME()
    FROM #missing_part AS m;

    DECLARE @inferred_parts INT = @@ROWCOUNT;

    DROP TABLE #missing_vin;
    DROP TABLE #missing_customer;
    DROP TABLE #missing_part;

    SELECT @inferred_vehicles AS inferred_vehicles,
           @inferred_customers AS inferred_customers,
           @inferred_parts AS inferred_parts;
END;
GO

CREATE PROCEDURE gold.usp_load_fact_vehicle_sale
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;

    DELETE FROM gold.fact_vehicle_sale WHERE _batch_id = @batch_id;

    INSERT INTO gold.fact_vehicle_sale
    (contract_no, contract_date_key, delivery_date_key, invoice_date_key,
     registration_date_key, vehicle_sk, trade_in_vehicle_sk, customer_sk,
     dealer_sk, salesperson_sk, model_trim_sk, transaction_flag_sk,
     list_price_amount, discount_amount, discount_rate, net_sale_amount,
     trade_in_amount, vehicle_cost_amount, gross_margin_amount, sale_count,
     days_in_stock, order_to_delivery_days, currency_code, fx_rate_to_try,
     sale_type, _batch_id, _loaded_ts)
    SELECT
        s.contract_no,

        ISNULL(dc.date_key, -1),
        ISNULL(dd.date_key, -1),
        ISNULL(di.date_key, -1),
        ISNULL(dr.date_key, -1),
        ISNULL(v.vehicle_sk, -1),

        CASE WHEN s.trade_in_vin IS NULL OR s.trade_in_vin = '' THEN -2
             ELSE ISNULL(tv.vehicle_sk, -1) END,
        ISNULL(c.customer_sk, -1),
        ISNULL(dl.dealer_sk, -1),
        ISNULL(e.employee_sk, -1),
        ISNULL(mt.model_trim_sk, -1),
        ISNULL(tf.transaction_flag_sk, -1),

        s.list_price, s.discount_amount, s.discount_rate, s.net_sale_amount,
        s.trade_in_amount,

        v.dealer_cost_amount,

        (s.net_sale_amount - ISNULL(v.dealer_cost_amount, 0)),
        1,
        s.days_in_stock,
        DATEDIFF(DAY, s.contract_date, s.delivery_date),
        s.currency_code, s.fx_rate_to_try, s.sale_type,
        @batch_id, SYSDATETIME()
    FROM mihenk_lh.silver.sales_contract AS s

    LEFT JOIN gold.dim_date AS dc ON dc.full_date = s.contract_date
    LEFT JOIN gold.dim_date AS dd ON dd.full_date = s.delivery_date
    LEFT JOIN gold.dim_date AS di ON di.full_date = s.invoice_date
    LEFT JOIN gold.dim_date AS dr ON dr.full_date = s.registration_date

    -- >= ve < (eşitsiz), ikisi de <= olursa versiyon değişim gününde fact
    -- ikiye katlanır. scd2 dimension'a her join'de bu kural geçerli.
    LEFT JOIN gold.dim_vehicle AS v
        ON  v.vin = s.vin
        AND s.contract_date >= v.valid_from AND s.contract_date < v.valid_to
    LEFT JOIN gold.dim_vehicle AS tv
        ON  tv.vin = s.trade_in_vin
        AND s.contract_date >= tv.valid_from AND s.contract_date < tv.valid_to
    LEFT JOIN gold.dim_customer AS c
        ON  c.master_customer_id = s.master_customer_id
        AND s.contract_date >= c.valid_from AND s.contract_date < c.valid_to
    LEFT JOIN gold.dim_dealer AS dl
        ON  dl.dealer_code = s.dealer_code
        AND s.contract_date >= dl.valid_from AND s.contract_date < dl.valid_to
    LEFT JOIN gold.dim_employee AS e
        ON  e.employee_id = s.salesperson_id
        AND s.contract_date >= e.valid_from AND s.contract_date < e.valid_to
    LEFT JOIN gold.dim_model_trim AS mt
        ON  mt.model_trim_code = s.model_trim_code
        AND s.contract_date >= mt.valid_from AND s.contract_date < mt.valid_to

    -- transaction_flag_sk > 0 excludes the -1 "Bilinmiyor" sentinel row - it
    -- was seeded with the same (0, 'NA', 'NA', 0, 0, 0) attribute combination
    -- as a genuine real flag row, so without this the join finds both and
    -- every fact matching that combination is silently duplicated. same
    -- pattern already used elsewhere for other dimensions (dealer_sk > 0 etc).
    LEFT JOIN gold.dim_transaction_flag AS tf
        ON  tf.is_campaign  = ISNULL(s.is_campaign, 0)
        AND tf.payment_type = ISNULL(s.payment_type, 'NA')
        AND tf.channel      = ISNULL(s.channel, 'NA')
        AND tf.is_used_vehicle = CASE WHEN s.sale_type = 'USED' THEN 1 ELSE 0 END
        AND tf.is_warranty  = 0
        AND tf.has_trade_in = CASE WHEN s.trade_in_vin IS NOT NULL
                                    AND s.trade_in_vin <> '' THEN 1 ELSE 0 END
        AND tf.transaction_flag_sk > 0;

    SELECT COUNT(*) AS rows_loaded,
           SUM(CASE WHEN vehicle_sk  = -1 THEN 1 ELSE 0 END) AS unresolved_vehicle,
           SUM(CASE WHEN customer_sk = -1 THEN 1 ELSE 0 END) AS unresolved_customer,
           SUM(CASE WHEN contract_date_key = -1 THEN 1 ELSE 0 END) AS unresolved_date
    FROM gold.fact_vehicle_sale WHERE _batch_id = @batch_id;
END;
GO

CREATE PROCEDURE gold.usp_load_fact_repair_order
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;

    DELETE FROM gold.fact_repair_order
    WHERE repair_order_no IN (SELECT repair_order_no FROM mihenk_lh.silver.repair_order);

    INSERT INTO gold.fact_repair_order
    (repair_order_no, appointment_date_key, checkin_date_key, inspection_date_key,
     parts_ready_date_key, repair_start_date_key, repair_end_date_key, qc_date_key,
     delivery_date_key,
     checkin_ts, inspection_ts, parts_wait_start_ts, parts_ready_ts,
     repair_start_ts, repair_end_ts, qc_ts, delivery_ts,
     vehicle_sk, customer_sk, dealer_sk, service_advisor_sk, technician_sk,
     service_type_sk, transaction_flag_sk,
     inspection_wait_hours, parts_wait_hours, repair_duration_hours,
     qc_wait_hours, collection_wait_hours, total_cycle_hours, touch_time_hours,
     labour_amount, part_amount, warranty_amount, customer_payable_amount,
     total_amount, labour_hours_sold, repair_order_count,
     odometer_km, plate_masked, status, is_open, _batch_id, _loaded_ts)
    SELECT
        o.repair_order_no,

        ISNULL(da.date_key, -1), ISNULL(dci.date_key, -1), ISNULL(din.date_key, -1),
        ISNULL(dpr.date_key, -1), ISNULL(drs.date_key, -1), ISNULL(dre.date_key, -1),
        ISNULL(dqc.date_key, -1), ISNULL(ddl.date_key, -1),

        o.checkin_ts, o.inspection_ts, o.parts_wait_start_ts, o.parts_ready_ts,
        o.repair_start_ts, o.repair_end_ts, o.qc_ts, o.delivery_ts,

        ISNULL(v.vehicle_sk, -1), ISNULL(c.customer_sk, -1), ISNULL(dl.dealer_sk, -1),
        ISNULL(sa.employee_sk, -1), ISNULL(tech.employee_sk, -1),
        ISNULL(st.service_type_sk, -1), ISNULL(tf.transaction_flag_sk, -1),

        o.inspection_wait_hours, o.parts_wait_hours, o.repair_duration_hours,
        o.qc_wait_hours, o.collection_wait_hours, o.total_cycle_hours,
        o.touch_time_hours,

        o.total_labour_amount, o.total_part_amount, o.total_warranty_amount,
        o.customer_payable_amount,
        (ISNULL(o.total_labour_amount, 0) + ISNULL(o.total_part_amount, 0)),

        lh.labour_hours_sold,
        1,
        o.odometer_km, o.plate_masked, o.status, o.is_open,
        @batch_id, SYSDATETIME()
    FROM mihenk_lh.silver.repair_order AS o

    LEFT JOIN (
        SELECT repair_order_no, SUM(labour_hours) AS labour_hours_sold
        FROM mihenk_lh.silver.repair_order_line
        WHERE line_type = 'LABOUR'
        GROUP BY repair_order_no
    ) AS lh ON lh.repair_order_no = o.repair_order_no

    LEFT JOIN gold.dim_date AS da  ON da.full_date  = o.appointment_date
    LEFT JOIN gold.dim_date AS dci ON dci.full_date = CAST(o.checkin_ts AS DATE)
    LEFT JOIN gold.dim_date AS din ON din.full_date = CAST(o.inspection_ts AS DATE)
    LEFT JOIN gold.dim_date AS dpr ON dpr.full_date = CAST(o.parts_ready_ts AS DATE)
    LEFT JOIN gold.dim_date AS drs ON drs.full_date = CAST(o.repair_start_ts AS DATE)
    LEFT JOIN gold.dim_date AS dre ON dre.full_date = CAST(o.repair_end_ts AS DATE)
    LEFT JOIN gold.dim_date AS dqc ON dqc.full_date = CAST(o.qc_ts AS DATE)
    LEFT JOIN gold.dim_date AS ddl ON ddl.full_date = CAST(o.delivery_ts AS DATE)

    LEFT JOIN gold.dim_vehicle AS v
        ON  v.vin = o.vin
        AND CAST(o.checkin_ts AS DATE) >= v.valid_from
        AND CAST(o.checkin_ts AS DATE) <  v.valid_to
    LEFT JOIN gold.dim_customer AS c
        ON  c.master_customer_id = o.master_customer_id
        AND CAST(o.checkin_ts AS DATE) >= c.valid_from
        AND CAST(o.checkin_ts AS DATE) <  c.valid_to
    LEFT JOIN gold.dim_dealer AS dl
        ON  dl.dealer_code = o.dealer_code
        AND CAST(o.checkin_ts AS DATE) >= dl.valid_from
        AND CAST(o.checkin_ts AS DATE) <  dl.valid_to
    LEFT JOIN gold.dim_employee AS sa
        ON  sa.employee_id = o.service_advisor_id
        AND CAST(o.checkin_ts AS DATE) >= sa.valid_from
        AND CAST(o.checkin_ts AS DATE) <  sa.valid_to
    LEFT JOIN gold.dim_employee AS tech
        ON  tech.employee_id = o.technician_id
        AND CAST(o.checkin_ts AS DATE) >= tech.valid_from
        AND CAST(o.checkin_ts AS DATE) <  tech.valid_to

    LEFT JOIN gold.dim_service_type AS st ON st.service_type_code = o.service_type_code
    -- transaction_flag_sk > 0 - see the note on the same join in
    -- usp_load_fact_vehicle_sale above.
    LEFT JOIN gold.dim_transaction_flag AS tf
        ON  tf.is_campaign = 0 AND tf.payment_type = 'NA' AND tf.channel = 'NA'
        AND tf.is_used_vehicle = 0 AND tf.has_trade_in = 0
        AND tf.is_warranty = ISNULL(o.is_warranty, 0)
        AND tf.transaction_flag_sk > 0;

    SELECT COUNT(*) AS rows_loaded,
           SUM(CAST(is_open AS INT)) AS still_open,
           SUM(CASE WHEN vehicle_sk = -1 THEN 1 ELSE 0 END) AS unresolved_vehicle
    FROM gold.fact_repair_order WHERE _batch_id = @batch_id;
END;
GO

CREATE PROCEDURE gold.usp_load_fact_repair_order_line
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;

    DELETE FROM gold.fact_repair_order_line
    WHERE repair_order_no IN (SELECT repair_order_no FROM mihenk_lh.silver.repair_order);

    INSERT INTO gold.fact_repair_order_line
    (repair_order_no, line_no, checkin_date_key, vehicle_sk, customer_sk,
     dealer_sk, technician_sk, service_type_sk, part_sk, line_type,
     operation_code, quantity, labour_hours, unit_price_amount, discount_amount,
     line_amount, warranty_amount, customer_amount, line_count,
     _batch_id, _loaded_ts)
    SELECT
        l.repair_order_no, l.line_no,
        ISNULL(dci.date_key, -1),
        ISNULL(v.vehicle_sk, -1), ISNULL(c.customer_sk, -1), ISNULL(dl.dealer_sk, -1),
        ISNULL(tech.employee_sk, -1), ISNULL(st.service_type_sk, -1),

        CASE WHEN l.line_type = 'LABOUR' THEN -2 ELSE ISNULL(p.part_sk, -1) END,
        l.line_type, l.operation_code, l.quantity, l.labour_hours,
        l.unit_price, l.discount_amount, l.line_amount, l.warranty_amount,
        l.customer_amount, 1,
        @batch_id, SYSDATETIME()
    FROM mihenk_lh.silver.repair_order_line AS l
    INNER JOIN mihenk_lh.silver.repair_order AS o ON o.repair_order_no = l.repair_order_no

    LEFT JOIN gold.dim_date AS dci ON dci.full_date = CAST(o.checkin_ts AS DATE)
    LEFT JOIN gold.dim_vehicle AS v
        ON v.vin = o.vin
        AND CAST(o.checkin_ts AS DATE) >= v.valid_from
        AND CAST(o.checkin_ts AS DATE) <  v.valid_to
    LEFT JOIN gold.dim_customer AS c
        ON c.master_customer_id = o.master_customer_id
        AND CAST(o.checkin_ts AS DATE) >= c.valid_from
        AND CAST(o.checkin_ts AS DATE) <  c.valid_to
    LEFT JOIN gold.dim_dealer AS dl
        ON dl.dealer_code = o.dealer_code
        AND CAST(o.checkin_ts AS DATE) >= dl.valid_from
        AND CAST(o.checkin_ts AS DATE) <  dl.valid_to
    LEFT JOIN gold.dim_employee AS tech
        ON tech.employee_id = o.technician_id
        AND CAST(o.checkin_ts AS DATE) >= tech.valid_from
        AND CAST(o.checkin_ts AS DATE) <  tech.valid_to
    LEFT JOIN gold.dim_part AS p
        ON p.part_no = l.part_no
        AND CAST(o.checkin_ts AS DATE) >= p.valid_from
        AND CAST(o.checkin_ts AS DATE) <  p.valid_to
    LEFT JOIN gold.dim_service_type AS st ON st.service_type_code = o.service_type_code;

    SELECT COUNT(*) AS rows_loaded,
           SUM(CASE WHEN part_sk = -1 THEN 1 ELSE 0 END) AS unresolved_part
    FROM gold.fact_repair_order_line WHERE _batch_id = @batch_id;
END;
GO

CREATE PROCEDURE gold.usp_load_fact_part_purchase
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;
    DELETE FROM gold.fact_part_purchase WHERE _batch_id = @batch_id;

    INSERT INTO gold.fact_part_purchase
    (po_no, po_line_no, order_date_key, promised_date_key, delivery_date_key,
     supplier_sk, part_sk, ordered_quantity, received_quantity, shortfall_quantity,
     unit_cost_amount, line_amount, delay_days, is_late, po_line_count,
     status, currency_code, fx_rate_to_try, _batch_id, _loaded_ts)
    SELECT
        pl.po_no, pl.po_line_no,
        ISNULL(dor.date_key, -1), ISNULL(dpr.date_key, -1), ISNULL(ddl.date_key, -1),
        ISNULL(sp.supplier_sk, -1), ISNULL(p.part_sk, -1),
        pl.ordered_quantity, pl.received_quantity, pl.shortfall_quantity,
        pl.unit_cost, pl.line_amount, pl.delay_days, pl.is_late, 1,
        pl.status, pl.currency_code, pl.fx_rate_to_try,
        @batch_id, SYSDATETIME()
    FROM mihenk_lh.silver.purchase_order_line AS pl
    LEFT JOIN gold.dim_date AS dor ON dor.full_date = pl.order_date
    LEFT JOIN gold.dim_date AS dpr ON dpr.full_date = pl.promised_date
    LEFT JOIN gold.dim_date AS ddl ON ddl.full_date = pl.delivery_date

    LEFT JOIN gold.dim_supplier AS sp ON sp.supplier_id = pl.supplier_id
    LEFT JOIN gold.dim_part AS p
        ON p.part_no = pl.part_no
        AND pl.order_date >= p.valid_from AND pl.order_date < p.valid_to;

    SELECT COUNT(*) AS rows_loaded FROM gold.fact_part_purchase WHERE _batch_id = @batch_id;
END;
GO

CREATE PROCEDURE gold.usp_load_fact_vehicle_inventory_daily
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;
    DELETE FROM gold.fact_vehicle_inventory_daily WHERE _batch_id = @batch_id;

    -- SELECT ... INTO #t, not CREATE TABLE #t + INSERT INTO #t - see the
    -- note in 30_scd2_pattern.sql.
    SELECT
        v.vin, v.arrival_date,
        ISNULL(sale.delivery_date, (SELECT MAX(full_date) FROM gold.dim_date WHERE date_key > 0)) AS exit_date,
        v.stock_dealer_code AS dealer_code, v.model_trim_code, v.dealer_cost_try AS cost_amount
    INTO #stock_window
    FROM mihenk_lh.silver.vehicle AS v
    LEFT JOIN (
        SELECT vin, MIN(delivery_date) AS delivery_date
        FROM mihenk_lh.silver.sales_contract
        WHERE sale_type = 'NEW' AND delivery_date IS NOT NULL
        GROUP BY vin
    ) AS sale ON sale.vin = v.vin
    WHERE v.arrival_date IS NOT NULL;

    INSERT INTO gold.fact_vehicle_inventory_daily
    (snapshot_date_key, vehicle_sk, dealer_sk, model_trim_sk,
     days_in_stock, stock_value_amount, vehicle_count, age_band,
     _batch_id, _loaded_ts)
    SELECT
        d.date_key,
        ISNULL(v.vehicle_sk, -1),
        ISNULL(dl.dealer_sk, -1),
        ISNULL(mt.model_trim_sk, -1),
        DATEDIFF(DAY, w.arrival_date, d.full_date),
        w.cost_amount,
        1,
        CASE
            WHEN DATEDIFF(DAY, w.arrival_date, d.full_date) <= 30  THEN '0-30'
            WHEN DATEDIFF(DAY, w.arrival_date, d.full_date) <= 60  THEN '31-60'
            WHEN DATEDIFF(DAY, w.arrival_date, d.full_date) <= 90  THEN '61-90'
            WHEN DATEDIFF(DAY, w.arrival_date, d.full_date) <= 180 THEN '91-180'
            ELSE '180+'
        END,
        @batch_id, SYSDATETIME()
    FROM #stock_window AS w
    INNER JOIN gold.dim_date AS d
        ON  d.date_key > 0
        AND d.full_date >= w.arrival_date

        AND d.full_date <  w.exit_date
    LEFT JOIN gold.dim_vehicle AS v
        ON v.vin = w.vin
        AND d.full_date >= v.valid_from AND d.full_date < v.valid_to
    LEFT JOIN gold.dim_dealer AS dl
        ON dl.dealer_code = w.dealer_code
        AND d.full_date >= dl.valid_from AND d.full_date < dl.valid_to
    LEFT JOIN gold.dim_model_trim AS mt
        ON mt.model_trim_code = w.model_trim_code
        AND d.full_date >= mt.valid_from AND d.full_date < mt.valid_to;

    DROP TABLE #stock_window;

    SELECT COUNT(*) AS rows_loaded,
           COUNT(DISTINCT vehicle_sk) AS vehicles_covered,
           AVG(CAST(days_in_stock AS FLOAT)) AS avg_days_in_stock
    FROM gold.fact_vehicle_inventory_daily WHERE _batch_id = @batch_id;
END;
GO

CREATE PROCEDURE gold.usp_load_fact_recall_coverage
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;
    DELETE FROM gold.fact_recall_coverage WHERE _batch_id = @batch_id;

    DECLARE @today DATE = (SELECT MAX(full_date) FROM gold.dim_date WHERE date_key > 0);

    INSERT INTO gold.fact_recall_coverage
    (campaign_code, vehicle_sk, vin, launch_date_key, notified_date_key,
     completed_date_key, model_trim_sk, dealer_sk, campaign_name,
     campaign_category, is_completed, days_to_complete, days_outstanding,
     coverage_count, _batch_id, _loaded_ts)
    SELECT
        rc.campaign_code,
        ISNULL(v.vehicle_sk, -1),
        rc.vin,
        ISNULL(dla.date_key, -1),
        ISNULL(dn.date_key, -1),
        ISNULL(dcp.date_key, -1),
        ISNULL(mt.model_trim_sk, -1),

        ISNULL(dl.dealer_sk, -1),
        cam.campaign_name, cam.category,
        rc.is_completed, rc.days_to_complete,

        CASE WHEN rc.is_completed = 0 AND rc.notified_date IS NOT NULL
             THEN DATEDIFF(DAY, rc.notified_date, @today) END,
        1,
        @batch_id, SYSDATETIME()
    FROM mihenk_lh.silver.recall_coverage AS rc
    INNER JOIN mihenk_lh.silver.recall_campaign AS cam ON cam.campaign_code = rc.campaign_code
    LEFT JOIN gold.dim_date AS dla ON dla.full_date = cam.launch_date
    LEFT JOIN gold.dim_date AS dn  ON dn.full_date  = rc.notified_date
    LEFT JOIN gold.dim_date AS dcp ON dcp.full_date = rc.completed_date
    LEFT JOIN gold.dim_vehicle AS v
        ON v.vin = rc.vin AND v.is_current = 1
    LEFT JOIN gold.dim_model_trim AS mt
        ON mt.model_trim_code = v.model_trim_code AND mt.is_current = 1

    LEFT JOIN (
        SELECT o.vin, o.dealer_code,
               ROW_NUMBER() OVER (PARTITION BY o.vin ORDER BY o.checkin_ts DESC) AS rn
        FROM mihenk_lh.silver.repair_order AS o
        WHERE o.service_type_code = 'RECALL'
    ) AS ro ON ro.vin = rc.vin AND ro.rn = 1
    LEFT JOIN gold.dim_dealer AS dl
        ON dl.dealer_code = ro.dealer_code AND dl.is_current = 1;

    SELECT COUNT(*) AS rows_loaded,
           SUM(CAST(is_completed AS INT)) AS completed,
           SUM(CASE WHEN is_completed = 0 THEN 1 ELSE 0 END) AS outstanding
    FROM gold.fact_recall_coverage WHERE _batch_id = @batch_id;
END;
GO

CREATE PROCEDURE gold.usp_load_fact_data_quality
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;
    DELETE FROM gold.fact_data_quality WHERE batch_id = @batch_id;

    INSERT INTO gold.fact_data_quality
    (batch_id, rule_code, executed_date_key, target_table, target_layer,
     rule_type, severity, outcome, rows_evaluated, rows_violated,
     violation_rate, rows_quarantined, rule_execution_count, _loaded_ts)
    SELECT
        r.batch_id, r.rule_code,
        ISNULL(d.date_key, -1),
        r.target_table, ru.target_layer, ru.rule_type,
        r.severity, r.outcome, r.rows_evaluated, r.rows_violated,
        r.violation_rate,
        CASE WHEN r.severity = 'critical' THEN r.rows_violated ELSE 0 END,
        1, SYSDATETIME()
    FROM ctl.dq_result AS r
    LEFT JOIN ctl.dq_rule AS ru ON ru.rule_id = r.rule_id
    LEFT JOIN gold.dim_date AS d ON d.full_date = CAST(r.executed_ts AS DATE)
    WHERE r.batch_id = @batch_id;

    SELECT COUNT(*) AS rows_loaded FROM gold.fact_data_quality WHERE batch_id = @batch_id;
END;
GO
