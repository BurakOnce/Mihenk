
CREATE PROCEDURE gold.usp_initial_load
    @batch_id       VARCHAR(40),
    @calendar_from  DATE = '2022-01-01',
    @calendar_to    DATE = '2027-12-31'
AS
BEGIN
    SET NOCOUNT ON;

    EXEC gold.usp_populate_dim_date @from_date = @calendar_from, @to_date = @calendar_to;

    EXEC gold.usp_backfill_dim_dealer     @batch_id = @batch_id;
    EXEC gold.usp_backfill_dim_employee   @batch_id = @batch_id;
    EXEC gold.usp_backfill_dim_model_trim @batch_id = @batch_id;
    EXEC gold.usp_backfill_dim_part       @batch_id = @batch_id;
    EXEC gold.usp_backfill_dim_vehicle    @batch_id = @batch_id;

    EXEC gold.usp_load_gold @batch_id = @batch_id;
END;
GO

CREATE PROCEDURE gold.usp_load_gold
    @batch_id       VARCHAR(40),
    @effective_date DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET @effective_date = ISNULL(@effective_date, CAST(SYSDATETIME() AS DATE));

    EXEC gold.usp_load_dim_service_type     @batch_id = @batch_id;
    EXEC gold.usp_load_dim_supplier         @batch_id = @batch_id;
    EXEC gold.usp_load_dim_dealer           @batch_id = @batch_id, @effective_date = @effective_date;
    EXEC gold.usp_load_dim_customer         @batch_id = @batch_id, @effective_date = @effective_date;

    EXEC gold.usp_load_dim_transaction_flag @batch_id = @batch_id;

    EXEC gold.usp_create_inferred_members   @batch_id = @batch_id;

    EXEC gold.usp_load_fact_vehicle_sale            @batch_id = @batch_id;
    EXEC gold.usp_load_fact_repair_order            @batch_id = @batch_id;
    EXEC gold.usp_load_fact_repair_order_line       @batch_id = @batch_id;
    EXEC gold.usp_load_fact_part_purchase           @batch_id = @batch_id;
    EXEC gold.usp_load_fact_recall_coverage         @batch_id = @batch_id;
    EXEC gold.usp_load_fact_data_quality            @batch_id = @batch_id;

    EXEC gold.usp_load_fact_vehicle_inventory_daily @batch_id = @batch_id;

    EXEC gold.usp_load_agg_monthly_dealer_model_sale @batch_id = @batch_id;
    EXEC gold.usp_load_agg_monthly_dealer_target     @batch_id = @batch_id;
    EXEC gold.usp_load_agg_monthly_service_summary   @batch_id = @batch_id;
END;
GO

CREATE PROCEDURE gold.usp_verify_gold
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;

    SELECT * FROM (

        SELECT 'SCD2_INTEGRITY' AS check_name,
               CONCAT(dimension, ' / ', check_name, ' / ', natural_key) AS detail,
               1 AS failure_count
        FROM gold.vw_scd2_integrity

        UNION ALL

        SELECT 'UNRESOLVED_KEY_RATE',
               CONCAT('fact_vehicle_sale.vehicle_sk unknown on ',
                      CAST(COUNT(*) AS VARCHAR(20)), ' rows'),
               COUNT(*)
        FROM gold.fact_vehicle_sale
        WHERE vehicle_sk = -1
        HAVING COUNT(*) > 0

        UNION ALL

        SELECT 'FACT_ROW_RECONCILIATION',
               CONCAT('fact_vehicle_sale has ',
                      CAST((SELECT COUNT(*) FROM gold.fact_vehicle_sale) AS VARCHAR(20)),
                      ' rows against mihenk_lh.silver.sales_contract ',
                      CAST((SELECT COUNT(*) FROM mihenk_lh.silver.sales_contract) AS VARCHAR(20))),
               ABS((SELECT COUNT(*) FROM gold.fact_vehicle_sale)
                   - (SELECT COUNT(*) FROM mihenk_lh.silver.sales_contract))
        WHERE (SELECT COUNT(*) FROM gold.fact_vehicle_sale)
              <> (SELECT COUNT(*) FROM mihenk_lh.silver.sales_contract)

        UNION ALL

        SELECT 'DUPLICATE_FACT_GRAIN',
               CONCAT('fact_repair_order_line has ', CAST(COUNT(*) AS VARCHAR(20)),
                      ' duplicated (order, line) pairs'),
               COUNT(*)
        FROM (
            SELECT repair_order_no, line_no
            FROM gold.fact_repair_order_line
            GROUP BY repair_order_no, line_no
            HAVING COUNT(*) > 1
        ) AS d
        HAVING COUNT(*) > 0

        UNION ALL

        SELECT 'IMPOSSIBLE_MEASURE',
               CONCAT(CAST(COUNT(*) AS VARCHAR(20)),
                      ' sales with a discount exceeding the list price'),
               COUNT(*)
        FROM gold.fact_vehicle_sale
        WHERE discount_amount > list_price_amount
        HAVING COUNT(*) > 0

        UNION ALL

        SELECT 'INFERRED_MEMBER_BACKLOG',
               CONCAT(CAST(COUNT(*) AS VARCHAR(20)),
                      ' vehicles still inferred'),
               COUNT(*)
        FROM gold.dim_vehicle
        WHERE is_inferred = 1 AND is_current = 1
        HAVING COUNT(*) > 0

    ) AS checks
    ORDER BY check_name;
END;
GO
