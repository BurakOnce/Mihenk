
CREATE TABLE gold.dim_vehicle
(
    vehicle_sk              BIGINT          NOT NULL,
    vin                     VARCHAR(20)     NOT NULL,

    model_trim_code         VARCHAR(20)     NULL,
    model_year              INT             NULL,
    colour                  VARCHAR(30)     NULL,
    production_date         DATE            NULL,
    arrival_date            DATE            NULL,
    engine_no               VARCHAR(30)     NULL,

    status                  VARCHAR(20)     NULL,
    stock_dealer_code       VARCHAR(20)     NULL,
    plate_hash              VARCHAR(64)     NULL,
    plate_masked            VARCHAR(20)     NULL,
    master_customer_id      VARCHAR(20)     NULL,
    owner_since_date        DATE            NULL,
    dealer_cost_amount      DECIMAL(18,2)   NULL,

    vin_well_formed         BIT             NULL,
    vin_check_digit_valid   BIT             NULL,

    is_inferred             BIT             NOT NULL,
    valid_from              DATE            NOT NULL,
    valid_to                DATE            NOT NULL,
    is_current              BIT             NOT NULL,
    _row_hash               VARCHAR(64)     NULL,
    _batch_id               VARCHAR(40)     NULL,
    _loaded_ts              DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.dim_vehicle
    ADD CONSTRAINT pk_dim_vehicle PRIMARY KEY NONCLUSTERED (vehicle_sk) NOT ENFORCED;
GO

CREATE TABLE gold.dim_customer
(
    customer_sk             BIGINT          NOT NULL,
    master_customer_id      VARCHAR(20)     NOT NULL,

    customer_type           VARCHAR(15)     NULL,
    full_name               VARCHAR(200)    NULL,

    identity_hash           VARCHAR(64)     NULL,
    identity_no_masked      VARCHAR(20)     NULL,
    phone_hash              VARCHAR(64)     NULL,
    phone_masked            VARCHAR(20)     NULL,
    email_hash              VARCHAR(64)     NULL,
    email_masked            VARCHAR(100)    NULL,

    city                    VARCHAR(40)     NULL,
    city_code               VARCHAR(2)      NULL,
    region                  VARCHAR(30)     NULL,
    lead_source             VARCHAR(20)     NULL,
    consent_kvkk            BIT             NULL,
    customer_since_date     DATE            NULL,

    source_presence         VARCHAR(10)     NULL,
    match_score             INT             NULL,

    is_inferred             BIT             NOT NULL,
    valid_from              DATE            NOT NULL,
    valid_to                DATE            NOT NULL,
    is_current              BIT             NOT NULL,
    _row_hash               VARCHAR(64)     NULL,
    _batch_id               VARCHAR(40)     NULL,
    _loaded_ts              DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.dim_customer
    ADD CONSTRAINT pk_dim_customer PRIMARY KEY NONCLUSTERED (customer_sk) NOT ENFORCED;
GO

CREATE TABLE gold.dim_dealer
(
    dealer_sk               BIGINT          NOT NULL,
    dealer_code             VARCHAR(20)     NOT NULL,

    dealer_name             VARCHAR(120)    NULL,
    dealer_type             VARCHAR(15)     NULL,
    province_code           VARCHAR(2)      NULL,
    city                    VARCHAR(40)     NULL,
    region                  VARCHAR(30)     NULL,
    address_line            VARCHAR(200)    NULL,
    phone                   VARCHAR(30)     NULL,

    workshop_bay_count      INT             NULL,
    monthly_capacity_hours  INT             NULL,
    opening_date            DATE            NULL,
    is_active               BIT             NULL,

    is_inferred             BIT             NOT NULL,
    valid_from              DATE            NOT NULL,
    valid_to                DATE            NOT NULL,
    is_current              BIT             NOT NULL,
    _row_hash               VARCHAR(64)     NULL,
    _batch_id               VARCHAR(40)     NULL,
    _loaded_ts              DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.dim_dealer
    ADD CONSTRAINT pk_dim_dealer PRIMARY KEY NONCLUSTERED (dealer_sk) NOT ENFORCED;
GO

CREATE TABLE gold.dim_employee
(
    employee_sk             BIGINT          NOT NULL,
    employee_id             VARCHAR(20)     NOT NULL,

    full_name               VARCHAR(120)    NULL,
    first_name              VARCHAR(60)     NULL,
    last_name               VARCHAR(60)     NULL,
    dealer_code             VARCHAR(20)     NULL,
    role_code               VARCHAR(20)     NULL,
    email                   VARCHAR(120)    NULL,
    hire_date               DATE            NULL,
    is_active               BIT             NULL,

    is_inferred             BIT             NOT NULL,
    valid_from              DATE            NOT NULL,
    valid_to                DATE            NOT NULL,
    is_current              BIT             NOT NULL,
    _row_hash               VARCHAR(64)     NULL,
    _batch_id               VARCHAR(40)     NULL,
    _loaded_ts              DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.dim_employee
    ADD CONSTRAINT pk_dim_employee PRIMARY KEY NONCLUSTERED (employee_sk) NOT ENFORCED;
GO

CREATE TABLE gold.dim_model_trim
(
    model_trim_sk           BIGINT          NOT NULL,
    model_trim_code         VARCHAR(20)     NOT NULL,

    brand                   VARCHAR(30)     NULL,
    model_name              VARCHAR(40)     NULL,
    trim_name               VARCHAR(30)     NULL,
    model_year              INT             NULL,
    body_type               VARCHAR(20)     NULL,
    segment                 VARCHAR(10)     NULL,
    engine_cc               INT             NULL,
    fuel_type               VARCHAR(15)     NULL,
    transmission            VARCHAR(15)     NULL,
    warranty_months         INT             NULL,
    warranty_km             INT             NULL,
    list_price_amount       DECIMAL(18,2)   NULL,
    is_active               BIT             NULL,

    is_inferred             BIT             NOT NULL,
    valid_from              DATE            NOT NULL,
    valid_to                DATE            NOT NULL,
    is_current              BIT             NOT NULL,
    _row_hash               VARCHAR(64)     NULL,
    _batch_id               VARCHAR(40)     NULL,
    _loaded_ts              DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.dim_model_trim
    ADD CONSTRAINT pk_dim_model_trim PRIMARY KEY NONCLUSTERED (model_trim_sk) NOT ENFORCED;
GO

CREATE TABLE gold.dim_part
(
    part_sk                 BIGINT          NOT NULL,
    part_no                 VARCHAR(30)     NOT NULL,

    part_name               VARCHAR(120)    NULL,
    part_group_code         VARCHAR(15)     NULL,
    part_group_name         VARCHAR(60)     NULL,
    is_genuine              BIT             NULL,
    supplier_id             VARCHAR(20)     NULL,
    unit_of_measure         VARCHAR(5)      NULL,
    list_price_amount       DECIMAL(18,2)   NULL,
    is_active               BIT             NULL,

    is_inferred             BIT             NOT NULL,
    valid_from              DATE            NOT NULL,
    valid_to                DATE            NOT NULL,
    is_current              BIT             NOT NULL,
    _row_hash               VARCHAR(64)     NULL,
    _batch_id               VARCHAR(40)     NULL,
    _loaded_ts              DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.dim_part
    ADD CONSTRAINT pk_dim_part PRIMARY KEY NONCLUSTERED (part_sk) NOT ENFORCED;
GO

CREATE TABLE gold.dim_supplier
(
    supplier_sk             BIGINT          NOT NULL,
    supplier_id             VARCHAR(20)     NOT NULL,

    supplier_name           VARCHAR(120)    NULL,
    country_code            VARCHAR(2)      NULL,
    is_domestic             BIT             NULL,
    lead_time_days          INT             NULL,
    contact_email           VARCHAR(120)    NULL,
    is_active               BIT             NULL,

    _row_hash               VARCHAR(64)     NULL,
    _batch_id               VARCHAR(40)     NULL,
    _loaded_ts              DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.dim_supplier
    ADD CONSTRAINT pk_dim_supplier PRIMARY KEY NONCLUSTERED (supplier_sk) NOT ENFORCED;
GO

CREATE TABLE gold.dim_service_type
(
    service_type_sk         BIGINT          NOT NULL,
    service_type_code       VARCHAR(15)     NOT NULL,

    service_type_name_tr    VARCHAR(60)     NULL,
    service_type_name_en    VARCHAR(60)     NULL,
    is_warranty_eligible    BIT             NULL,
    is_scheduled            BIT             NULL,
    typical_labour_hours    DECIMAL(9,2)    NULL,

    _row_hash               VARCHAR(64)     NULL,
    _batch_id               VARCHAR(40)     NULL,
    _loaded_ts              DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.dim_service_type
    ADD CONSTRAINT pk_dim_service_type PRIMARY KEY NONCLUSTERED (service_type_sk) NOT ENFORCED;
GO

CREATE TABLE gold.dim_transaction_flag
(
    transaction_flag_sk     BIGINT          NOT NULL,

    is_campaign             BIT             NOT NULL,
    payment_type            VARCHAR(10)     NOT NULL,
    channel                 VARCHAR(15)     NOT NULL,
    is_used_vehicle         BIT             NOT NULL,
    is_warranty             BIT             NOT NULL,
    has_trade_in            BIT             NOT NULL,

    flag_description        VARCHAR(200)    NULL,

    _row_hash               VARCHAR(64)     NULL,
    _loaded_ts              DATETIME2(3)    NOT NULL
);
GO
ALTER TABLE gold.dim_transaction_flag
    ADD CONSTRAINT pk_dim_transaction_flag
    PRIMARY KEY NONCLUSTERED (transaction_flag_sk) NOT ENFORCED;
GO

CREATE VIEW gold.vw_dim_vehicle_current AS
    SELECT * FROM gold.dim_vehicle WHERE is_current = 1;
GO
CREATE VIEW gold.vw_dim_customer_current AS
    SELECT * FROM gold.dim_customer WHERE is_current = 1;
GO
CREATE VIEW gold.vw_dim_dealer_current AS
    SELECT * FROM gold.dim_dealer WHERE is_current = 1;
GO
CREATE VIEW gold.vw_dim_employee_current AS
    SELECT * FROM gold.dim_employee WHERE is_current = 1;
GO
CREATE VIEW gold.vw_dim_model_trim_current AS
    SELECT * FROM gold.dim_model_trim WHERE is_current = 1;
GO
CREATE VIEW gold.vw_dim_part_current AS
    SELECT * FROM gold.dim_part WHERE is_current = 1;
GO
