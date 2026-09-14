
CREATE PROCEDURE ctl.usp_run_dq_rules
    @batch_id       VARCHAR(40),
    @target_layer   VARCHAR(10) = 'silver'
AS
BEGIN
    SET NOCOUNT ON;

    DELETE FROM ctl.dq_violation WHERE batch_id = @batch_id;
    DELETE FROM ctl.dq_result    WHERE batch_id = @batch_id;

    -- fabric warehouse rejects CREATE TABLE #t + a separate INSERT INTO #t
    -- SELECT with "references an object that is not supported in distributed
    -- processing mode" - even for the simplest case, nothing to do with the
    -- window function below. SELECT ... INTO #t (creating the temp table from
    -- the query itself, ctas-style) is the form that actually works.
    SELECT
        ROW_NUMBER() OVER (ORDER BY r.rule_id) AS seq,
        r.rule_id, r.rule_code, r.target_table, r.violation_sql,
        r.severity, r.max_violation_rate
    INTO #rules
    FROM ctl.dq_rule AS r
    WHERE r.is_active = 1
      AND r.target_layer = @target_layer;

    DECLARE @total_rules INT = (SELECT COUNT(*) FROM #rules);
    DECLARE @i INT = 1;

    DECLARE @rule_id            INT;
    DECLARE @rule_code          VARCHAR(40);
    DECLARE @target_table       VARCHAR(120);
    DECLARE @violation_sql      VARCHAR(4000);
    DECLARE @severity           VARCHAR(10);
    DECLARE @max_rate           DECIMAL(5,4);
    DECLARE @started            DATETIME2(3);
    DECLARE @evaluated          BIGINT;
    DECLARE @violated           BIGINT;
    DECLARE @outcome            VARCHAR(10);
    DECLARE @error              VARCHAR(4000);
    DECLARE @count_sql          NVARCHAR(500);
    DECLARE @insert_sql         NVARCHAR(4000);

    WHILE @i <= @total_rules
    BEGIN
        SELECT
            @rule_id       = rule_id,
            @rule_code     = rule_code,
            @target_table  = target_table,
            @violation_sql = violation_sql,
            @severity      = severity,
            @max_rate      = max_violation_rate
        FROM #rules WHERE seq = @i;

        SET @started   = SYSDATETIME();
        SET @evaluated = 0;
        SET @violated  = 0;
        SET @outcome   = 'PASSED';
        SET @error     = NULL;

        BEGIN TRY

            SET @count_sql = N'SELECT @out = COUNT_BIG(*) FROM ' + @target_table;
            EXEC sp_executesql @count_sql, N'@out BIGINT OUTPUT', @out = @evaluated OUTPUT;

            SET @insert_sql =
                N'INSERT INTO ctl.dq_violation
                    (violation_id, batch_id, rule_id, rule_code, target_table,
                     business_key, detail, detected_ts)
                  SELECT
                    ROW_NUMBER() OVER (ORDER BY (SELECT NULL))
                        + ISNULL((SELECT MAX(violation_id) FROM ctl.dq_violation), 0),
                    @p_batch, @p_rule_id, @p_rule_code, @p_table,
                    v.business_key, v.detail, SYSDATETIME()
                  FROM (' + CAST(@violation_sql AS NVARCHAR(4000)) + N') AS v';

            EXEC sp_executesql
                @insert_sql,
                N'@p_batch VARCHAR(40), @p_rule_id INT, @p_rule_code VARCHAR(40), @p_table VARCHAR(120)',
                @p_batch = @batch_id, @p_rule_id = @rule_id,
                @p_rule_code = @rule_code, @p_table = @target_table;

            SELECT @violated = COUNT_BIG(*)
            FROM ctl.dq_violation
            WHERE batch_id = @batch_id AND rule_id = @rule_id;

            IF @violated > 0 SET @outcome = 'FAILED';

            IF @max_rate IS NOT NULL
               AND @evaluated > 0
               AND (CAST(@violated AS DECIMAL(18,6)) / @evaluated) > @max_rate
                SET @outcome = 'SUSPECT';
        END TRY
        BEGIN CATCH

            SET @outcome = 'ERROR';
            SET @error = LEFT(ERROR_MESSAGE(), 4000);
        END CATCH;

        INSERT INTO ctl.dq_result
            (result_id, batch_id, rule_id, rule_code, target_table,
             rows_evaluated, rows_violated, violation_rate,
             severity, outcome, error_message, executed_ts, duration_seconds)
        SELECT
            ISNULL((SELECT MAX(result_id) FROM ctl.dq_result), 0) + 1,
            @batch_id, @rule_id, @rule_code, @target_table,
            @evaluated, @violated,
            CASE WHEN @evaluated > 0
                 THEN CAST(@violated AS DECIMAL(18,6)) / @evaluated
                 ELSE 0 END,
            @severity, @outcome, @error, @started,
            DATEDIFF(SECOND, @started, SYSDATETIME());

        SET @i = @i + 1;
    END;

    DROP TABLE #rules;

    SELECT
        @batch_id                                                          AS batch_id,
        COUNT(*)                                                           AS rules_run,
        SUM(CASE WHEN outcome = 'PASSED'  THEN 1 ELSE 0 END)               AS passed,
        SUM(CASE WHEN outcome = 'FAILED'  THEN 1 ELSE 0 END)               AS failed,
        SUM(CASE WHEN outcome = 'ERROR'   THEN 1 ELSE 0 END)               AS errored,
        SUM(CASE WHEN outcome = 'SUSPECT' THEN 1 ELSE 0 END)               AS suspect,
        SUM(rows_violated)                                                 AS total_violations,
        SUM(CASE WHEN severity = 'critical' THEN rows_violated ELSE 0 END) AS critical_violations
    FROM ctl.dq_result
    WHERE batch_id = @batch_id;
END;
GO

CREATE VIEW ctl.vw_dq_scorecard
AS
SELECT
    res.batch_id,
    res.rule_code,
    rul.rule_name,
    rul.rule_type,
    res.target_table,
    rul.target_column,
    res.severity,
    res.outcome,
    res.rows_evaluated,
    res.rows_violated,
    res.violation_rate,
    res.executed_ts,
    CAST(res.executed_ts AS DATE) AS executed_date
FROM ctl.dq_result AS res
INNER JOIN ctl.dq_rule AS rul
    ON rul.rule_id = res.rule_id;
GO
