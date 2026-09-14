
CREATE PROCEDURE gold.usp_load_agg_monthly_dealer_model_sale
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;

    DELETE FROM gold.agg_monthly_dealer_model_sale;

    INSERT INTO gold.agg_monthly_dealer_model_sale
    (month_key, dealer_sk, model_trim_sk, sale_count, new_sale_count,
     used_sale_count, trade_in_count, list_price_amount, discount_amount,
     net_sale_amount, gross_margin_amount, avg_discount_rate, avg_days_in_stock,
     _batch_id, _loaded_ts)
    SELECT
        d.month_key,
        f.dealer_sk,
        f.model_trim_sk,
        COUNT(*),
        SUM(CASE WHEN f.sale_type = 'NEW'  THEN 1 ELSE 0 END),
        SUM(CASE WHEN f.sale_type = 'USED' THEN 1 ELSE 0 END),
        SUM(CASE WHEN f.trade_in_vehicle_sk > 0 THEN 1 ELSE 0 END),
        SUM(f.list_price_amount),
        SUM(f.discount_amount),
        SUM(f.net_sale_amount),
        SUM(f.gross_margin_amount),

        CASE WHEN SUM(f.list_price_amount) > 0
             THEN SUM(f.discount_amount) / SUM(f.list_price_amount) END,
        AVG(CAST(f.days_in_stock AS DECIMAL(9,2))),
        @batch_id, SYSDATETIME()
    FROM gold.fact_vehicle_sale AS f
    INNER JOIN gold.dim_date AS d ON d.date_key = f.contract_date_key
    WHERE d.date_key > 0
    GROUP BY d.month_key, f.dealer_sk, f.model_trim_sk;

    SELECT COUNT(*) AS rows_loaded FROM gold.agg_monthly_dealer_model_sale;
END;
GO

CREATE PROCEDURE gold.usp_load_agg_monthly_dealer_target
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;
    DELETE FROM gold.agg_monthly_dealer_target;

    WITH targets AS
    (
        SELECT
            b.budget_year * 100 + b.budget_month AS month_key,
            dl.dealer_sk,
            SUM(CASE WHEN b.metric_code = 'VEHICLE_SALES_COUNT'    THEN b.target_value END) AS target_sale_count,
            SUM(CASE WHEN b.metric_code = 'VEHICLE_SALES_AMOUNT'   THEN b.target_value END) AS target_sale_amount,
            SUM(CASE WHEN b.metric_code = 'SERVICE_REVENUE_AMOUNT' THEN b.target_value END) AS target_service_amount
        FROM mihenk_lh.silver.budget AS b
        LEFT JOIN gold.dim_dealer AS dl
            ON dl.dealer_code = b.dealer_code AND dl.is_current = 1
        GROUP BY b.budget_year * 100 + b.budget_month, dl.dealer_sk
    ),
    sales_actual AS
    (
        SELECT d.month_key, f.dealer_sk,
               COUNT(*) AS actual_sale_count,
               SUM(f.net_sale_amount) AS actual_sale_amount
        FROM gold.fact_vehicle_sale AS f
        INNER JOIN gold.dim_date AS d ON d.date_key = f.contract_date_key
        WHERE d.date_key > 0
        GROUP BY d.month_key, f.dealer_sk
    ),
    service_actual AS
    (
        SELECT d.month_key, f.dealer_sk,
               SUM(f.total_amount) AS actual_service_amount
        FROM gold.fact_repair_order AS f
        INNER JOIN gold.dim_date AS d ON d.date_key = f.checkin_date_key
        WHERE d.date_key > 0
        GROUP BY d.month_key, f.dealer_sk
    )
    INSERT INTO gold.agg_monthly_dealer_target
    (month_key, dealer_sk, target_sale_count, target_sale_amount,
     target_service_amount, actual_sale_count, actual_sale_amount,
     actual_service_amount, _batch_id, _loaded_ts)
    SELECT
        t.month_key, t.dealer_sk,
        t.target_sale_count, t.target_sale_amount, t.target_service_amount,

        ISNULL(sa.actual_sale_count, 0),
        ISNULL(sa.actual_sale_amount, 0),
        ISNULL(sv.actual_service_amount, 0),
        @batch_id, SYSDATETIME()
    FROM targets AS t
    LEFT JOIN sales_actual   AS sa ON sa.month_key = t.month_key AND sa.dealer_sk = t.dealer_sk
    LEFT JOIN service_actual AS sv ON sv.month_key = t.month_key AND sv.dealer_sk = t.dealer_sk;

    SELECT COUNT(*) AS rows_loaded FROM gold.agg_monthly_dealer_target;
END;
GO

CREATE PROCEDURE gold.usp_load_agg_monthly_service_summary
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;
    DELETE FROM gold.agg_monthly_service_summary;

    WITH working_days AS
    (
        SELECT month_key, SUM(CAST(is_working_day AS INT)) AS working_days
        FROM gold.dim_date
        WHERE date_key > 0
        GROUP BY month_key
    ),
    orders AS
    (
        SELECT
            d.month_key, f.dealer_sk, f.service_type_sk,
            COUNT(*)                                          AS repair_order_count,
            SUM(CAST(f.is_open AS INT))                       AS open_order_count,
            SUM(f.labour_hours_sold)                          AS labour_hours_sold,
            SUM(f.labour_amount)                              AS labour_amount,
            SUM(f.part_amount)                                AS part_amount,
            SUM(f.warranty_amount)                            AS warranty_amount,
            SUM(f.customer_payable_amount)                    AS customer_payable_amount,
            AVG(f.total_cycle_hours)                          AS avg_cycle_hours,
            AVG(f.parts_wait_hours)                           AS avg_parts_wait_hours,
            SUM(CASE WHEN f.parts_wait_hours IS NOT NULL THEN 1 ELSE 0 END)
                                                              AS orders_with_parts_wait
        FROM gold.fact_repair_order AS f
        INNER JOIN gold.dim_date AS d ON d.date_key = f.checkin_date_key
        WHERE d.date_key > 0
        GROUP BY d.month_key, f.dealer_sk, f.service_type_sk
    )
    INSERT INTO gold.agg_monthly_service_summary
    (month_key, dealer_sk, service_type_sk, repair_order_count, open_order_count,
     labour_hours_sold, available_labour_hours, labour_amount, part_amount,
     warranty_amount, customer_payable_amount, avg_cycle_hours,
     avg_parts_wait_hours, orders_with_parts_wait, _batch_id, _loaded_ts)
    SELECT
        o.month_key, o.dealer_sk, o.service_type_sk,
        o.repair_order_count, o.open_order_count, o.labour_hours_sold,

        CAST(dl.monthly_capacity_hours AS DECIMAL(14,2)) / 22.0 * wd.working_days,
        o.labour_amount, o.part_amount, o.warranty_amount, o.customer_payable_amount,
        o.avg_cycle_hours, o.avg_parts_wait_hours, o.orders_with_parts_wait,
        @batch_id, SYSDATETIME()
    FROM orders AS o
    INNER JOIN working_days AS wd ON wd.month_key = o.month_key
    LEFT JOIN gold.dim_dealer AS dl ON dl.dealer_sk = o.dealer_sk;

    SELECT COUNT(*) AS rows_loaded FROM gold.agg_monthly_service_summary;
END;
GO
