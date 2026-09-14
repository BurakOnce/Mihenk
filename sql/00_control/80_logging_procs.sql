
CREATE PROCEDURE ctl.usp_log_step_start
    @batch_id   VARCHAR(40),
    @source_id  INT,
    @layer      VARCHAR(10),
    @step_name  VARCHAR(120)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @run_id BIGINT =
        ISNULL((SELECT MAX(run_id) FROM ctl.pipeline_run_log), 0) + 1;

    INSERT INTO ctl.pipeline_run_log
        (run_id, batch_id, source_id, layer, step_name, status,
         start_ts, end_ts, duration_seconds,
         rows_read, rows_written, rows_rejected, files_read,
         watermark_from, watermark_to, error_message, created_ts)
    VALUES
        (@run_id, @batch_id, @source_id, @layer, @step_name, 'RUNNING',
         SYSDATETIME(), NULL, NULL,
         NULL, NULL, NULL, NULL,
         NULL, NULL, NULL, SYSDATETIME());

    SELECT @run_id AS run_id;
END;
GO

CREATE PROCEDURE ctl.usp_log_step_end
    @run_id         BIGINT,
    @status         VARCHAR(15),
    @rows_read      BIGINT = NULL,
    @rows_written   BIGINT = NULL,
    @rows_rejected  BIGINT = NULL,
    @files_read     INT = NULL,
    @watermark_from VARCHAR(40) = NULL,
    @watermark_to   VARCHAR(40) = NULL,
    @error_message  VARCHAR(4000) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE ctl.pipeline_run_log
    SET status            = @status,
        end_ts            = SYSDATETIME(),
        duration_seconds  = DATEDIFF(SECOND, start_ts, SYSDATETIME()),
        rows_read         = @rows_read,
        rows_written      = @rows_written,
        rows_rejected     = @rows_rejected,
        files_read        = @files_read,
        watermark_from    = @watermark_from,
        watermark_to      = @watermark_to,
        error_message     = LEFT(@error_message, 4000)
    WHERE run_id = @run_id;
END;
GO

CREATE PROCEDURE ctl.usp_advance_watermark
    @source_id       INT,
    @new_watermark   VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;

    IF @new_watermark IS NULL OR @new_watermark = ''
        RETURN;

    UPDATE ctl.source_config
    SET watermark_value = @new_watermark,
        updated_ts      = SYSDATETIME()
    WHERE source_id = @source_id

      AND (watermark_value IS NULL OR @new_watermark > watermark_value);
END;
GO

CREATE PROCEDURE ctl.usp_start_batch
    @batch_id   VARCHAR(40),
    @layer      VARCHAR(10)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @run_id BIGINT =
        ISNULL((SELECT MAX(run_id) FROM ctl.pipeline_run_log), 0) + 1;

    INSERT INTO ctl.pipeline_run_log
        (run_id, batch_id, source_id, layer, step_name, status,
         start_ts, end_ts, duration_seconds,
         rows_read, rows_written, rows_rejected, files_read,
         watermark_from, watermark_to, error_message, created_ts)
    VALUES
        (@run_id, @batch_id, NULL, @layer, 'BATCH', 'RUNNING',
         SYSDATETIME(), NULL, NULL,
         NULL, NULL, NULL, NULL,
         NULL, NULL, NULL, SYSDATETIME());

    SELECT @run_id AS run_id;
END;
GO

CREATE PROCEDURE ctl.usp_end_batch
    @batch_id   VARCHAR(40),
    @layer      VARCHAR(10)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @failed INT =
    (
        SELECT COUNT(*)
        FROM ctl.pipeline_run_log
        WHERE batch_id = @batch_id AND layer = @layer
          AND step_name <> 'BATCH' AND status = 'FAILED'
    );

    UPDATE ctl.pipeline_run_log
    SET status = CASE WHEN @failed > 0 THEN 'FAILED' ELSE 'SUCCEEDED' END,
        end_ts = SYSDATETIME(),
        duration_seconds = DATEDIFF(SECOND, start_ts, SYSDATETIME()),
        rows_read = child.rows_read,
        rows_written = child.rows_written,
        rows_rejected = child.rows_rejected,
        files_read = child.files_read,
        error_message = CASE WHEN @failed > 0
                             THEN CAST(@failed AS VARCHAR(10)) + ' source(s) failed'
                             ELSE NULL END
    FROM ctl.pipeline_run_log AS log
    CROSS APPLY
    (
        SELECT
            SUM(ISNULL(rows_read, 0))     AS rows_read,
            SUM(ISNULL(rows_written, 0))  AS rows_written,
            SUM(ISNULL(rows_rejected, 0)) AS rows_rejected,
            SUM(ISNULL(files_read, 0))    AS files_read
        FROM ctl.pipeline_run_log
        WHERE batch_id = @batch_id AND layer = @layer AND step_name <> 'BATCH'
    ) AS child
    WHERE log.batch_id = @batch_id
      AND log.layer = @layer
      AND log.step_name = 'BATCH';
END;
GO
