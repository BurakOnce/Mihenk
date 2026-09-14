
CREATE TABLE ctl.pipeline_run_log
(
    run_id              BIGINT          NOT NULL,

    batch_id            VARCHAR(40)     NOT NULL,

    source_id           INT             NULL,
    layer               VARCHAR(10)     NOT NULL,
    step_name           VARCHAR(120)    NOT NULL,

    status              VARCHAR(15)     NOT NULL,
    start_ts            DATETIME2(3)    NOT NULL,
    end_ts              DATETIME2(3)    NULL,
    duration_seconds    INT             NULL,

    rows_read           BIGINT          NULL,
    rows_written        BIGINT          NULL,
    rows_rejected       BIGINT          NULL,
    files_read          INT             NULL,

    watermark_from      VARCHAR(40)     NULL,
    watermark_to        VARCHAR(40)     NULL,

    error_message       VARCHAR(4000)   NULL,
    created_ts          DATETIME2(3)    NOT NULL
);
GO

ALTER TABLE ctl.pipeline_run_log
    ADD CONSTRAINT pk_pipeline_run_log PRIMARY KEY NONCLUSTERED (run_id) NOT ENFORCED;
GO

CREATE VIEW ctl.vw_batch_reconciliation
AS
SELECT
    batch_id,
    layer,
    COUNT(*)                                                AS step_count,
    SUM(CASE WHEN status = 'FAILED'    THEN 1 ELSE 0 END)    AS failed_steps,
    SUM(CASE WHEN status = 'RUNNING'   THEN 1 ELSE 0 END)    AS unfinished_steps,
    SUM(ISNULL(rows_read, 0))                                AS rows_read,
    SUM(ISNULL(rows_written, 0))                             AS rows_written,
    SUM(ISNULL(rows_rejected, 0))                            AS rows_rejected,

    SUM(ISNULL(rows_read, 0))
        - SUM(ISNULL(rows_written, 0))
        - SUM(ISNULL(rows_rejected, 0))                      AS unexplained_row_gap,
    MIN(start_ts)                                            AS batch_start_ts,
    MAX(end_ts)                                              AS batch_end_ts
FROM ctl.pipeline_run_log
GROUP BY batch_id, layer;
GO
