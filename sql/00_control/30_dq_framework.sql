
CREATE TABLE ctl.dq_rule
(
    rule_id             INT             NOT NULL,

    rule_code           VARCHAR(40)     NOT NULL,
    rule_name           VARCHAR(150)    NOT NULL,

    target_layer        VARCHAR(10)     NOT NULL,
    target_table        VARCHAR(120)    NOT NULL,
    target_column       VARCHAR(60)     NULL,

    rule_type           VARCHAR(20)     NOT NULL,

    violation_sql       VARCHAR(4000)   NOT NULL,

    severity            VARCHAR(10)     NOT NULL,
    quarantine_on_fail  BIT             NOT NULL,

    max_violation_rate  DECIMAL(5,4)    NULL,

    is_active           BIT             NOT NULL,
    description         VARCHAR(1000)   NULL,
    created_ts          DATETIME2(3)    NOT NULL
);
GO

ALTER TABLE ctl.dq_rule
    ADD CONSTRAINT pk_dq_rule PRIMARY KEY NONCLUSTERED (rule_id) NOT ENFORCED;
GO

CREATE TABLE ctl.dq_result
(
    result_id           BIGINT          NOT NULL,
    batch_id            VARCHAR(40)     NOT NULL,
    rule_id             INT             NOT NULL,
    rule_code           VARCHAR(40)     NOT NULL,

    target_table        VARCHAR(120)    NOT NULL,

    rows_evaluated      BIGINT          NOT NULL,
    rows_violated       BIGINT          NOT NULL,
    violation_rate      DECIMAL(9,6)    NOT NULL,

    severity            VARCHAR(10)     NOT NULL,

    outcome             VARCHAR(10)     NOT NULL,
    error_message       VARCHAR(4000)   NULL,

    executed_ts         DATETIME2(3)    NOT NULL,
    duration_seconds    INT             NULL
);
GO

ALTER TABLE ctl.dq_result
    ADD CONSTRAINT pk_dq_result PRIMARY KEY NONCLUSTERED (result_id) NOT ENFORCED;
GO

CREATE TABLE ctl.dq_violation
(
    violation_id        BIGINT          NOT NULL,
    batch_id            VARCHAR(40)     NOT NULL,
    rule_id             INT             NOT NULL,
    rule_code           VARCHAR(40)     NOT NULL,
    target_table        VARCHAR(120)    NOT NULL,

    business_key        VARCHAR(200)    NOT NULL,
    detail              VARCHAR(1000)   NULL,

    detected_ts         DATETIME2(3)    NOT NULL
);
GO

ALTER TABLE ctl.dq_violation
    ADD CONSTRAINT pk_dq_violation PRIMARY KEY NONCLUSTERED (violation_id) NOT ENFORCED;
GO
