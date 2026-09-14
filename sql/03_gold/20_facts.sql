
CREATE TABLE gold.fact_vehicle_sale
(

    contract_no                 VARCHAR(30)     NOT NULL,

    contract_date_key           INT             NOT NULL,
    delivery_date_key           INT             NOT NULL,
    invoice_date_key            INT             NOT NULL,
    registration_date_key       INT             NOT NULL,

    vehicle_sk                  BIGINT          NOT NULL,
    trade_in_vehicle_sk         BIGINT          NOT NULL,
    customer_sk                 BIGINT          NOT NULL,
    dealer_sk                   BIGINT          NOT NULL,
    salesperson_sk              BIGINT          NOT NULL,
    model_trim_sk               BIGINT          NOT NULL,
    transaction_flag_sk         BIGINT          NOT NULL,

    list_price_amount           DECIMAL(18,2)   NULL,
    discount_amount             DECIMAL(18,2)   NULL,
    discount_rate               DECIMAL(9,6)    NULL,
    net_sale_amount             DECIMAL(18,2)   NULL,
    trade_in_amount             DECIMAL(18,2)   NULL,
    vehicle_cost_amount         DECIMAL(18,2)   NULL,

    gross_margin_amount         DECIMAL(18,2)   NULL,
    sale_count                  INT             NOT NULL,

    days_in_stock               INT             NULL,
    order_to_delivery_days      INT             NULL,
    currency_code               VARCHAR(3)      NULL,
    fx_rate_to_try              DECIMAL(18,6)   NULL,
    sale_type                   VARCHAR(10)     NULL,

    _batch_id                   VARCHAR(40)     NULL,
    _loaded_ts                  DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.fact_vehicle_sale
    ADD CONSTRAINT pk_fact_vehicle_sale PRIMARY KEY NONCLUSTERED (contract_no) NOT ENFORCED;
GO

CREATE TABLE gold.fact_repair_order
(
    repair_order_no             VARCHAR(30)     NOT NULL,

    appointment_date_key        INT             NOT NULL,
    checkin_date_key            INT             NOT NULL,
    inspection_date_key         INT             NOT NULL,
    parts_ready_date_key        INT             NOT NULL,
    repair_start_date_key       INT             NOT NULL,
    repair_end_date_key         INT             NOT NULL,
    qc_date_key                 INT             NOT NULL,
    delivery_date_key           INT             NOT NULL,

    checkin_ts                  DATETIME2(0)    NULL,
    inspection_ts               DATETIME2(0)    NULL,
    parts_wait_start_ts         DATETIME2(0)    NULL,
    parts_ready_ts              DATETIME2(0)    NULL,
    repair_start_ts             DATETIME2(0)    NULL,
    repair_end_ts               DATETIME2(0)    NULL,
    qc_ts                       DATETIME2(0)    NULL,
    delivery_ts                 DATETIME2(0)    NULL,

    vehicle_sk                  BIGINT          NOT NULL,
    customer_sk                 BIGINT          NOT NULL,
    dealer_sk                   BIGINT          NOT NULL,
    service_advisor_sk          BIGINT          NOT NULL,
    technician_sk               BIGINT          NOT NULL,
    service_type_sk             BIGINT          NOT NULL,
    transaction_flag_sk         BIGINT          NOT NULL,

    inspection_wait_hours       DECIMAL(12,2)   NULL,
    parts_wait_hours            DECIMAL(12,2)   NULL,
    repair_duration_hours       DECIMAL(12,2)   NULL,
    qc_wait_hours               DECIMAL(12,2)   NULL,
    collection_wait_hours       DECIMAL(12,2)   NULL,
    total_cycle_hours           DECIMAL(12,2)   NULL,

    touch_time_hours            DECIMAL(12,2)   NULL,

    labour_amount               DECIMAL(18,2)   NULL,
    part_amount                 DECIMAL(18,2)   NULL,
    warranty_amount             DECIMAL(18,2)   NULL,
    customer_payable_amount     DECIMAL(18,2)   NULL,
    total_amount                DECIMAL(18,2)   NULL,
    labour_hours_sold           DECIMAL(12,2)   NULL,
    repair_order_count          INT             NOT NULL,

    odometer_km                 BIGINT          NULL,
    plate_masked                VARCHAR(20)     NULL,
    status                      VARCHAR(25)     NULL,
    is_open                     BIT             NOT NULL,

    _batch_id                   VARCHAR(40)     NULL,
    _loaded_ts                  DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.fact_repair_order
    ADD CONSTRAINT pk_fact_repair_order
    PRIMARY KEY NONCLUSTERED (repair_order_no) NOT ENFORCED;
GO

CREATE TABLE gold.fact_repair_order_line
(
    repair_order_no             VARCHAR(30)     NOT NULL,
    line_no                     INT             NOT NULL,

    checkin_date_key            INT             NOT NULL,
    vehicle_sk                  BIGINT          NOT NULL,
    customer_sk                 BIGINT          NOT NULL,
    dealer_sk                   BIGINT          NOT NULL,
    technician_sk               BIGINT          NOT NULL,
    service_type_sk             BIGINT          NOT NULL,
    part_sk                     BIGINT          NOT NULL,

    line_type                   VARCHAR(10)     NOT NULL,
    operation_code              VARCHAR(20)     NULL,

    quantity                    DECIMAL(18,3)   NULL,
    labour_hours                DECIMAL(12,2)   NULL,
    unit_price_amount           DECIMAL(18,2)   NULL,
    discount_amount             DECIMAL(18,2)   NULL,
    line_amount                 DECIMAL(18,2)   NULL,
    warranty_amount             DECIMAL(18,2)   NULL,
    customer_amount             DECIMAL(18,2)   NULL,
    line_count                  INT             NOT NULL,

    _batch_id                   VARCHAR(40)     NULL,
    _loaded_ts                  DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.fact_repair_order_line
    ADD CONSTRAINT pk_fact_repair_order_line
    PRIMARY KEY NONCLUSTERED (repair_order_no, line_no) NOT ENFORCED;
GO

CREATE TABLE gold.fact_part_purchase
(
    po_no                       VARCHAR(30)     NOT NULL,
    po_line_no                  INT             NOT NULL,

    order_date_key              INT             NOT NULL,
    promised_date_key           INT             NOT NULL,
    delivery_date_key           INT             NOT NULL,

    supplier_sk                 BIGINT          NOT NULL,
    part_sk                     BIGINT          NOT NULL,

    ordered_quantity            DECIMAL(18,3)   NULL,
    received_quantity           DECIMAL(18,3)   NULL,
    shortfall_quantity          DECIMAL(18,3)   NULL,
    unit_cost_amount            DECIMAL(18,2)   NULL,
    line_amount                 DECIMAL(18,2)   NULL,

    delay_days                  INT             NULL,
    is_late                     BIT             NULL,
    po_line_count               INT             NOT NULL,

    status                      VARCHAR(15)     NULL,
    currency_code               VARCHAR(3)      NULL,
    fx_rate_to_try              DECIMAL(18,6)   NULL,

    _batch_id                   VARCHAR(40)     NULL,
    _loaded_ts                  DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.fact_part_purchase
    ADD CONSTRAINT pk_fact_part_purchase
    PRIMARY KEY NONCLUSTERED (po_no, po_line_no) NOT ENFORCED;
GO

CREATE TABLE gold.fact_vehicle_inventory_daily
(
    snapshot_date_key           INT             NOT NULL,
    vehicle_sk                  BIGINT          NOT NULL,
    dealer_sk                   BIGINT          NOT NULL,
    model_trim_sk               BIGINT          NOT NULL,

    days_in_stock               INT             NOT NULL,
    stock_value_amount          DECIMAL(18,2)   NULL,
    vehicle_count               INT             NOT NULL,

    age_band                    VARCHAR(15)     NOT NULL,

    _batch_id                   VARCHAR(40)     NULL,
    _loaded_ts                  DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.fact_vehicle_inventory_daily
    ADD CONSTRAINT pk_fact_vehicle_inventory_daily
    PRIMARY KEY NONCLUSTERED (snapshot_date_key, vehicle_sk) NOT ENFORCED;
GO

CREATE TABLE gold.fact_recall_coverage
(
    campaign_code               VARCHAR(20)     NOT NULL,
    vehicle_sk                  BIGINT          NOT NULL,
    vin                         VARCHAR(20)     NOT NULL,

    launch_date_key             INT             NOT NULL,
    notified_date_key           INT             NOT NULL,
    completed_date_key          INT             NOT NULL,

    model_trim_sk               BIGINT          NOT NULL,
    dealer_sk                   BIGINT          NOT NULL,

    campaign_name               VARCHAR(120)    NULL,
    campaign_category           VARCHAR(15)     NULL,
    is_completed                BIT             NOT NULL,
    days_to_complete            INT             NULL,

    days_outstanding            INT             NULL,
    coverage_count              INT             NOT NULL,

    _batch_id                   VARCHAR(40)     NULL,
    _loaded_ts                  DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.fact_recall_coverage
    ADD CONSTRAINT pk_fact_recall_coverage
    PRIMARY KEY NONCLUSTERED (campaign_code, vin) NOT ENFORCED;
GO

CREATE TABLE gold.fact_data_quality
(
    batch_id                    VARCHAR(40)     NOT NULL,
    rule_code                   VARCHAR(40)     NOT NULL,
    executed_date_key           INT             NOT NULL,

    target_table                VARCHAR(120)    NOT NULL,
    target_layer                VARCHAR(10)     NULL,
    rule_type                   VARCHAR(20)     NULL,
    severity                    VARCHAR(10)     NOT NULL,
    outcome                     VARCHAR(10)     NOT NULL,

    rows_evaluated              BIGINT          NOT NULL,
    rows_violated               BIGINT          NOT NULL,
    violation_rate              DECIMAL(9,6)    NOT NULL,
    rows_quarantined            BIGINT          NULL,
    rule_execution_count        INT             NOT NULL,

    _loaded_ts                  DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.fact_data_quality
    ADD CONSTRAINT pk_fact_data_quality
    PRIMARY KEY NONCLUSTERED (batch_id, rule_code, target_table) NOT ENFORCED;
GO

CREATE TABLE gold.agg_monthly_dealer_model_sale
(
    month_key                   INT             NOT NULL,
    dealer_sk                   BIGINT          NOT NULL,
    model_trim_sk               BIGINT          NOT NULL,

    sale_count                  INT             NOT NULL,
    new_sale_count              INT             NOT NULL,
    used_sale_count             INT             NOT NULL,
    trade_in_count              INT             NOT NULL,
    list_price_amount           DECIMAL(18,2)   NULL,
    discount_amount             DECIMAL(18,2)   NULL,
    net_sale_amount             DECIMAL(18,2)   NULL,
    gross_margin_amount         DECIMAL(18,2)   NULL,
    avg_discount_rate           DECIMAL(9,6)    NULL,
    avg_days_in_stock           DECIMAL(9,2)    NULL,

    _batch_id                   VARCHAR(40)     NULL,
    _loaded_ts                  DATETIME2(3)    NOT NULL
);
GO

CREATE TABLE gold.agg_monthly_dealer_target
(
    month_key                   INT             NOT NULL,
    dealer_sk                   BIGINT          NOT NULL,

    target_sale_count           DECIMAL(18,2)   NULL,
    target_sale_amount          DECIMAL(18,2)   NULL,
    target_service_amount       DECIMAL(18,2)   NULL,
    actual_sale_count           INT             NULL,
    actual_sale_amount          DECIMAL(18,2)   NULL,
    actual_service_amount       DECIMAL(18,2)   NULL,

    _batch_id                   VARCHAR(40)     NULL,
    _loaded_ts                  DATETIME2(3)    NOT NULL
);
GO

CREATE TABLE gold.agg_monthly_service_summary
(
    month_key                   INT             NOT NULL,
    dealer_sk                   BIGINT          NOT NULL,
    service_type_sk             BIGINT          NOT NULL,

    repair_order_count          INT             NOT NULL,
    open_order_count            INT             NOT NULL,
    labour_hours_sold           DECIMAL(14,2)   NULL,

    available_labour_hours      DECIMAL(14,2)   NULL,
    labour_amount               DECIMAL(18,2)   NULL,
    part_amount                 DECIMAL(18,2)   NULL,
    warranty_amount             DECIMAL(18,2)   NULL,
    customer_payable_amount     DECIMAL(18,2)   NULL,
    avg_cycle_hours             DECIMAL(12,2)   NULL,
    avg_parts_wait_hours        DECIMAL(12,2)   NULL,
    orders_with_parts_wait      INT             NULL,

    _batch_id                   VARCHAR(40)     NULL,
    _loaded_ts                  DATETIME2(3)    NOT NULL
);
GO
