-- silver sadece güncel durumu tutuyor, o yüzden ilk gold yüklemesinde tarihsel
-- versiyon üretmek için bronze'un aylık snapshot'larını lag/lead ile taramak
-- gerekiyor (aksi halde her dealer tek versiyonla, bugün açılmış gibi başlar).
--
-- ayrıca merge burada aslında gerekli değilmiş: bir versiyon kapatma (update)
-- ile yenisini açma (insert) tek merge deyiminde birleştirilemiyor zaten, o
-- yüzden merge'li ve merge'siz iki versiyonu da yazdım - ikisi de aynı işi
-- görüyor. bunu yazana kadar farkına varmamıştım.
CREATE PROCEDURE gold.usp_backfill_dim_dealer
    @batch_id VARCHAR(40)
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (SELECT 1 FROM gold.dim_dealer WHERE dealer_sk > 0)
    BEGIN

        SELECT 'SKIPPED' AS outcome,
               'dim_dealer already contains rows; truncate it first to re-backfill' AS reason;
        RETURN;
    END;

    WITH snapshots AS
    (

        SELECT
            dealer_code,
            dealer_name, dealer_type, province_code, city, region,
            address_line, phone, workshop_bay_count, monthly_capacity_hours,
            opening_date, is_active,
            CAST(last_modified_ts AS DATE) AS observed_date,
            ROW_NUMBER() OVER (
                PARTITION BY dealer_code, CAST(last_modified_ts AS DATE)
                ORDER BY _ingest_ts DESC
            ) AS rn
        FROM mihenk_lh.bronze.dms_dealer
        WHERE dealer_code IS NOT NULL AND dealer_code <> ''
    ),
    attribute_signature AS
    (
        SELECT
            s.*,

            CONCAT_WS('||',
                ISNULL(dealer_name, ''), ISNULL(dealer_type, ''),
                ISNULL(province_code, ''), ISNULL(city, ''), ISNULL(region, ''),
                ISNULL(address_line, ''), ISNULL(phone, ''),
                ISNULL(CAST(workshop_bay_count AS VARCHAR(10)), ''),
                ISNULL(CAST(monthly_capacity_hours AS VARCHAR(10)), ''),
                ISNULL(CAST(is_active AS VARCHAR(1)), '')
            ) AS signature
        FROM snapshots AS s
        WHERE s.rn = 1
    ),
    hashed AS
    (
        SELECT
            a.*,
            CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', a.signature), 2) AS row_hash
        FROM attribute_signature AS a
    ),
    boundaries AS
    (

        SELECT
            h.*,
            LAG(h.row_hash) OVER (
                PARTITION BY h.dealer_code ORDER BY h.observed_date
            ) AS previous_hash
        FROM hashed AS h
    ),
    versions AS
    (
        SELECT * FROM boundaries
        WHERE previous_hash IS NULL OR previous_hash <> row_hash
    ),
    ranged AS
    (

        SELECT
            v.*,
            LEAD(v.observed_date) OVER (
                PARTITION BY v.dealer_code ORDER BY v.observed_date
            ) AS next_version_start
        FROM versions AS v
    )
    INSERT INTO gold.dim_dealer
    (
        dealer_sk, dealer_code, dealer_name, dealer_type, province_code, city,
        region, address_line, phone, workshop_bay_count, monthly_capacity_hours,
        opening_date, is_active, is_inferred,
        valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts
    )
    -- fabric warehouse'ta IDENTITY yok, surrogate key'i böyle üretiyorum.
    -- WHERE dealer_sk > 0 şart - yoksa boş tabloda MAX, -1 (unknown üyesi)
    -- döner ve ilk gerçek key 0'dan başlamaya çalışır.
    SELECT
        ROW_NUMBER() OVER (ORDER BY r.dealer_code, r.observed_date)
            + ISNULL((SELECT MAX(dealer_sk) FROM gold.dim_dealer WHERE dealer_sk > 0), 0),
        r.dealer_code, r.dealer_name, r.dealer_type, r.province_code, r.city,
        r.region, r.address_line, r.phone, r.workshop_bay_count,
        r.monthly_capacity_hours, r.opening_date, r.is_active,
        0,
        r.observed_date,
        ISNULL(r.next_version_start, '9999-12-31'),
        CASE WHEN r.next_version_start IS NULL THEN 1 ELSE 0 END,
        r.row_hash, @batch_id, SYSDATETIME()
    FROM ranged AS r;

    INSERT INTO gold.dim_dealer
    (
        dealer_sk, dealer_code, dealer_name, dealer_type, province_code, city,
        region, address_line, phone, workshop_bay_count, monthly_capacity_hours,
        opening_date, is_active, is_inferred,
        valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts
    )
    SELECT * FROM (VALUES
        (-1, '-1', 'Bilinmiyor',   'UNKNOWN', NULL, 'Bilinmiyor', 'Bilinmiyor',
         NULL, NULL, 0, 0, NULL, 0, 0, '1900-01-01', '9999-12-31', 1, NULL, NULL, SYSDATETIME()),
        (-2, '-2', 'Uygulanamaz',  'NA',      NULL, 'Uygulanamaz', 'Uygulanamaz',
         NULL, NULL, 0, 0, NULL, 0, 0, '1900-01-01', '9999-12-31', 1, NULL, NULL, SYSDATETIME())
    ) AS v (dealer_sk, dealer_code, dealer_name, dealer_type, province_code, city,
            region, address_line, phone, workshop_bay_count, monthly_capacity_hours,
            opening_date, is_active, is_inferred, valid_from, valid_to, is_current,
            _row_hash, _batch_id, _loaded_ts);

    SELECT
        COUNT(*)                                        AS versions_created,
        COUNT(DISTINCT dealer_code)                     AS distinct_dealers,
        SUM(CASE WHEN is_current = 1 THEN 1 ELSE 0 END) AS open_versions,
        MIN(valid_from)                                 AS earliest_version
    FROM gold.dim_dealer
    WHERE dealer_sk > 0;
END;
GO

CREATE PROCEDURE gold.usp_load_dim_dealer
    @batch_id       VARCHAR(40),
    @effective_date DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;

    SET @effective_date = ISNULL(@effective_date, CAST(SYSDATETIME() AS DATE));

    -- CREATE TABLE #t + ayrı INSERT INTO #t SELECT fabric warehouse'ta
    -- reddediliyor ("not supported in distributed processing mode") - en basit
    -- durumda bile doğrulandı, bu sorguya özgü bir şey değil.
    -- SELECT ... INTO #t fabric'in kabul ettiği biçim.
    SELECT
        s.dealer_code, s.dealer_name, s.dealer_type, s.province_code, s.city,
        s.region, s.address_line, s.phone, s.workshop_bay_count,
        s.monthly_capacity_hours, s.opening_date, s.is_active,
        CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', CONCAT_WS('||',
            ISNULL(s.dealer_name, ''), ISNULL(s.dealer_type, ''),
            ISNULL(s.province_code, ''), ISNULL(s.city, ''), ISNULL(s.region, ''),
            ISNULL(s.address_line, ''), ISNULL(s.phone, ''),
            ISNULL(CAST(s.workshop_bay_count AS VARCHAR(10)), ''),
            ISNULL(CAST(s.monthly_capacity_hours AS VARCHAR(10)), ''),
            ISNULL(CAST(s.is_active AS VARCHAR(1)), '')
        )), 2) AS row_hash
    INTO #source
    FROM mihenk_lh.silver.dealer AS s
    WHERE s.dealer_code IS NOT NULL AND s.dealer_code <> '';

    SELECT s.dealer_code
    INTO #changed
    FROM #source AS s
    INNER JOIN gold.dim_dealer AS d
        ON  d.dealer_code = s.dealer_code
        AND d.is_current = 1
    WHERE d._row_hash <> s.row_hash;

    MERGE gold.dim_dealer AS target
    USING #source AS source
        ON  target.dealer_code = source.dealer_code
        AND target.is_current = 1

    WHEN MATCHED AND target._row_hash <> source.row_hash THEN
        UPDATE SET

            target.valid_to   = @effective_date,
            target.is_current = 0,

            target._batch_id  = @batch_id,
            target._loaded_ts = SYSDATETIME()

    ;

    INSERT INTO gold.dim_dealer
    (
        dealer_sk, dealer_code, dealer_name, dealer_type, province_code, city,
        region, address_line, phone, workshop_bay_count, monthly_capacity_hours,
        opening_date, is_active, is_inferred,
        valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts
    )
    SELECT
        ROW_NUMBER() OVER (ORDER BY s.dealer_code)
            + ISNULL((SELECT MAX(dealer_sk) FROM gold.dim_dealer WHERE dealer_sk > 0), 0),
        s.dealer_code, s.dealer_name, s.dealer_type, s.province_code, s.city,
        s.region, s.address_line, s.phone, s.workshop_bay_count,
        s.monthly_capacity_hours, s.opening_date, s.is_active, 0,
        @effective_date, '9999-12-31', 1,
        s.row_hash, @batch_id, SYSDATETIME()
    FROM #source AS s
    WHERE EXISTS (SELECT 1 FROM #changed AS c WHERE c.dealer_code = s.dealer_code)
       OR NOT EXISTS (SELECT 1 FROM gold.dim_dealer AS d
                      WHERE d.dealer_code = s.dealer_code);

    UPDATE gold.dim_dealer
    SET is_active  = 0,
        _batch_id  = @batch_id,
        _loaded_ts = SYSDATETIME()
    WHERE is_current = 1
      AND dealer_sk > 0
      AND is_active = 1
      AND NOT EXISTS (SELECT 1 FROM #source AS s WHERE s.dealer_code = gold.dim_dealer.dealer_code);

    DROP TABLE #source;
    DROP TABLE #changed;

    SELECT
        (SELECT COUNT(*) FROM gold.dim_dealer WHERE _batch_id = @batch_id
                                                AND valid_from = @effective_date) AS versions_opened,
        (SELECT COUNT(*) FROM gold.dim_dealer WHERE _batch_id = @batch_id
                                                AND is_current = 0)                AS versions_closed,
        (SELECT COUNT(*) FROM gold.dim_dealer WHERE is_current = 1
                                                AND dealer_sk > 0)                 AS open_versions;
END;
GO

CREATE PROCEDURE gold.usp_load_dim_dealer_nomerge
    @batch_id       VARCHAR(40),
    @effective_date DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET @effective_date = ISNULL(@effective_date, CAST(SYSDATETIME() AS DATE));

    -- CREATE TABLE #t + INSERT INTO #t değil, SELECT ... INTO #t - yukarıdaki
    -- usp_load_dim_dealer notuna bak. buradaki NULL yer tutucuya açık CAST
    -- gerekiyor: SELECT INTO her sütunun tipini verilenden çıkarıyor ve çıplak
    -- tipsiz bir NULL, change_type'ı sonraki UPDATE'in ihtiyaç duyduğu VARCHAR(10)
    -- yerine tipsiz bırakıyor.
    SELECT
        s.dealer_code, s.dealer_name, s.dealer_type, s.province_code, s.city,
        s.region, s.address_line, s.phone, s.workshop_bay_count,
        s.monthly_capacity_hours, s.opening_date, s.is_active,
        CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', CONCAT_WS('||',
            ISNULL(s.dealer_name, ''), ISNULL(s.dealer_type, ''),
            ISNULL(s.province_code, ''), ISNULL(s.city, ''), ISNULL(s.region, ''),
            ISNULL(s.address_line, ''), ISNULL(s.phone, ''),
            ISNULL(CAST(s.workshop_bay_count AS VARCHAR(10)), ''),
            ISNULL(CAST(s.monthly_capacity_hours AS VARCHAR(10)), ''),
            ISNULL(CAST(s.is_active AS VARCHAR(1)), '')
        )), 2) AS row_hash,
        CAST(NULL AS VARCHAR(10)) AS change_type
    INTO #source
    FROM mihenk_lh.silver.dealer AS s
    WHERE s.dealer_code IS NOT NULL AND s.dealer_code <> '';

    UPDATE #source
    SET change_type =
        CASE
            WHEN NOT EXISTS (SELECT 1 FROM gold.dim_dealer AS d
                             WHERE d.dealer_code = #source.dealer_code)
                THEN 'NEW'
            WHEN EXISTS (SELECT 1 FROM gold.dim_dealer AS d
                         WHERE d.dealer_code = #source.dealer_code
                           AND d.is_current = 1
                           AND d._row_hash <> #source.row_hash)
                THEN 'CHANGED'
            ELSE 'UNCHANGED'
        END;

    BEGIN TRANSACTION;

    UPDATE gold.dim_dealer
    SET valid_to   = @effective_date,
        is_current = 0,
        _batch_id  = @batch_id,
        _loaded_ts = SYSDATETIME()
    WHERE is_current = 1
      AND EXISTS (SELECT 1 FROM #source AS s
                  WHERE s.dealer_code = gold.dim_dealer.dealer_code
                    AND s.change_type = 'CHANGED');

    INSERT INTO gold.dim_dealer
    (
        dealer_sk, dealer_code, dealer_name, dealer_type, province_code, city,
        region, address_line, phone, workshop_bay_count, monthly_capacity_hours,
        opening_date, is_active, is_inferred,
        valid_from, valid_to, is_current, _row_hash, _batch_id, _loaded_ts
    )
    SELECT
        ROW_NUMBER() OVER (ORDER BY s.dealer_code)
            + ISNULL((SELECT MAX(dealer_sk) FROM gold.dim_dealer WHERE dealer_sk > 0), 0),
        s.dealer_code, s.dealer_name, s.dealer_type, s.province_code, s.city,
        s.region, s.address_line, s.phone, s.workshop_bay_count,
        s.monthly_capacity_hours, s.opening_date, s.is_active, 0,
        @effective_date, '9999-12-31', 1,
        s.row_hash, @batch_id, SYSDATETIME()
    FROM #source AS s
    WHERE s.change_type IN ('NEW', 'CHANGED');

    UPDATE gold.dim_dealer
    SET is_active  = 0,
        _batch_id  = @batch_id,
        _loaded_ts = SYSDATETIME()
    WHERE is_current = 1
      AND dealer_sk > 0
      AND is_active = 1
      AND NOT EXISTS (SELECT 1 FROM #source AS s
                      WHERE s.dealer_code = gold.dim_dealer.dealer_code);

    COMMIT TRANSACTION;

    DROP TABLE #source;

    SELECT
        (SELECT COUNT(*) FROM gold.dim_dealer
         WHERE _batch_id = @batch_id AND valid_from = @effective_date) AS versions_opened,
        (SELECT COUNT(*) FROM gold.dim_dealer
         WHERE _batch_id = @batch_id AND is_current = 0)               AS versions_closed;
END;
GO

CREATE VIEW gold.vw_scd2_integrity
AS
WITH checks AS
(

    SELECT 'dim_dealer' AS dimension, 'MULTIPLE_OPEN_VERSIONS' AS check_name,
           CAST(dealer_code AS VARCHAR(60)) AS natural_key,
           CAST(COUNT(*) AS VARCHAR(40)) AS detail
    FROM gold.dim_dealer
    WHERE is_current = 1 AND dealer_sk > 0
    GROUP BY dealer_code
    HAVING COUNT(*) <> 1

    UNION ALL

    SELECT 'dim_dealer', 'FLAG_DATE_DISAGREEMENT',
           CAST(dealer_code AS VARCHAR(60)),
           CONCAT('is_current=', CAST(is_current AS VARCHAR(1)),
                  ' valid_to=', CONVERT(VARCHAR(10), valid_to, 23))
    FROM gold.dim_dealer
    WHERE dealer_sk > 0
      AND ((is_current = 1 AND valid_to <> '9999-12-31')
        OR (is_current = 0 AND valid_to = '9999-12-31'))

    UNION ALL

    SELECT 'dim_dealer', 'VERSION_RANGE_GAP_OR_OVERLAP',
           CAST(dealer_code AS VARCHAR(60)),
           CONCAT('valid_to=', CONVERT(VARCHAR(10), valid_to, 23),
                  ' next valid_from=', CONVERT(VARCHAR(10), next_from, 23))
    FROM (
        SELECT dealer_code, valid_to,
               LEAD(valid_from) OVER (PARTITION BY dealer_code ORDER BY valid_from) AS next_from
        FROM gold.dim_dealer
        WHERE dealer_sk > 0
    ) AS r
    WHERE next_from IS NOT NULL AND next_from <> valid_to
)
SELECT * FROM checks;
GO
