
CREATE TABLE ctl.source_config
(
    source_id           INT             NOT NULL,

    source_system       VARCHAR(30)     NOT NULL,
    entity              VARCHAR(60)     NOT NULL,
    target_table        VARCHAR(120)    NOT NULL,

    file_pattern        VARCHAR(400)    NOT NULL,
    is_date_partitioned BIT             NOT NULL,

    file_format         VARCHAR(10)     NOT NULL,
    delimiter           VARCHAR(3)      NULL,
    decimal_mark        VARCHAR(1)      NULL,
    encoding            VARCHAR(30)     NOT NULL,
    has_header          BIT             NOT NULL,
    sheet_name          VARCHAR(60)     NULL,

    load_type           VARCHAR(15)     NOT NULL,
    watermark_column    VARCHAR(60)     NULL,

    watermark_value     VARCHAR(40)     NULL,

    key_columns         VARCHAR(200)    NOT NULL,

    is_active           BIT             NOT NULL,
    load_order          INT             NOT NULL,
    retry_limit         INT             NOT NULL,
    description         VARCHAR(300)    NULL,
    created_ts          DATETIME2(3)    NOT NULL,
    updated_ts          DATETIME2(3)    NOT NULL
);
GO

ALTER TABLE ctl.source_config
    ADD CONSTRAINT pk_source_config PRIMARY KEY NONCLUSTERED (source_id) NOT ENFORCED;
GO
