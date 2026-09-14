
CREATE TABLE gold.dim_date
(
    date_key                INT             NOT NULL,
    full_date               DATE            NOT NULL,

    day_of_month            INT             NOT NULL,
    day_of_year             INT             NOT NULL,
    day_of_week             INT             NOT NULL,
    day_name_tr             VARCHAR(12)     NOT NULL,
    day_name_en             VARCHAR(12)     NOT NULL,
    day_abbr_tr             VARCHAR(4)      NOT NULL,

    iso_week                INT             NOT NULL,
    iso_year                INT             NOT NULL,
    week_start_date         DATE            NOT NULL,

    month_number            INT             NOT NULL,
    month_name_tr           VARCHAR(12)     NOT NULL,
    month_name_en           VARCHAR(12)     NOT NULL,

    month_key               INT             NOT NULL,
    month_year_label        VARCHAR(8)      NOT NULL,
    first_day_of_month      DATE            NOT NULL,
    last_day_of_month       DATE            NOT NULL,
    days_in_month           INT             NOT NULL,

    quarter_number          INT             NOT NULL,
    quarter_label           VARCHAR(8)      NOT NULL,
    year_number             INT             NOT NULL,
    fiscal_year             INT             NOT NULL,
    fiscal_quarter          INT             NOT NULL,
    fiscal_month            INT             NOT NULL,

    is_weekend              BIT             NOT NULL,
    is_public_holiday       BIT             NOT NULL,
    is_half_day             BIT             NOT NULL,
    holiday_name            VARCHAR(60)     NULL,

    is_working_day          BIT             NOT NULL,

    same_date_last_year_key INT             NULL,
    same_month_last_year_key INT            NULL
);
GO

ALTER TABLE gold.dim_date
    ADD CONSTRAINT pk_dim_date PRIMARY KEY NONCLUSTERED (date_key) NOT ENFORCED;
GO

CREATE TABLE gold.ref_public_holiday
(
    holiday_date    DATE            NOT NULL,
    holiday_name    VARCHAR(60)     NOT NULL,
    is_half_day     BIT             NOT NULL
);
GO

CREATE PROCEDURE gold.usp_populate_dim_date
    @from_date  DATE,
    @to_date    DATE
AS
BEGIN
    SET NOCOUNT ON;

    DELETE FROM gold.ref_public_holiday;

    -- a CTE's scope is the one statement it's attached to - it cannot be
    -- reused across two separate INSERTs. a temp table can, which is why
    -- this is #years and not a CTE: the fixed-holiday insert below and the
    -- half-day insert after it both read from it.
    --
    -- CREATE TABLE #years + a separate INSERT INTO #years SELECT fails on
    -- Fabric Warehouse ("not supported in distributed processing mode"),
    -- confirmed down to the simplest possible case - it isn't about this
    -- query's complexity. SELECT ... INTO #years (creating the temp table
    -- from the query itself) is the form Fabric actually accepts.
    SELECT DISTINCT YEAR(d.full_date) AS y
    INTO #years
    FROM (SELECT DATEADD(DAY, n.n, @from_date) AS full_date
          FROM (SELECT TOP (DATEDIFF(DAY, @from_date, @to_date) + 1) n
                FROM ctl.util_numbers ORDER BY n) AS n) AS d;

    INSERT INTO gold.ref_public_holiday (holiday_date, holiday_name, is_half_day)
    SELECT DATEFROMPARTS(y, m, d), name, 0
    FROM #years
    CROSS JOIN (VALUES
        (1,  1,  'Yılbaşı'),
        (4,  23, 'Ulusal Egemenlik ve Çocuk Bayramı'),
        (5,  1,  'Emek ve Dayanışma Günü'),
        (5,  19, 'Atatürk''ü Anma, Gençlik ve Spor Bayramı'),
        (7,  15, 'Demokrasi ve Millî Birlik Günü'),
        (8,  30, 'Zafer Bayramı'),
        (10, 29, 'Cumhuriyet Bayramı')
    ) AS h (m, d, name);

    INSERT INTO gold.ref_public_holiday (holiday_date, holiday_name, is_half_day)
    SELECT DATEFROMPARTS(y, 10, 28), 'Cumhuriyet Bayramı Arifesi', 1 FROM #years;

    DROP TABLE #years;

    INSERT INTO gold.ref_public_holiday (holiday_date, holiday_name, is_half_day)
    SELECT * FROM (VALUES
        ('2023-04-20', 'Ramazan Bayramı Arifesi', 1),
        ('2023-04-21', 'Ramazan Bayramı', 0), ('2023-04-22', 'Ramazan Bayramı', 0),
        ('2023-04-23', 'Ramazan Bayramı', 0),
        ('2023-06-27', 'Kurban Bayramı Arifesi', 1),
        ('2023-06-28', 'Kurban Bayramı', 0), ('2023-06-29', 'Kurban Bayramı', 0),
        ('2023-06-30', 'Kurban Bayramı', 0), ('2023-07-01', 'Kurban Bayramı', 0),

        ('2024-04-09', 'Ramazan Bayramı Arifesi', 1),
        ('2024-04-10', 'Ramazan Bayramı', 0), ('2024-04-11', 'Ramazan Bayramı', 0),
        ('2024-04-12', 'Ramazan Bayramı', 0),
        ('2024-06-15', 'Kurban Bayramı Arifesi', 1),
        ('2024-06-16', 'Kurban Bayramı', 0), ('2024-06-17', 'Kurban Bayramı', 0),
        ('2024-06-18', 'Kurban Bayramı', 0), ('2024-06-19', 'Kurban Bayramı', 0),

        ('2025-03-29', 'Ramazan Bayramı Arifesi', 1),
        ('2025-03-30', 'Ramazan Bayramı', 0), ('2025-03-31', 'Ramazan Bayramı', 0),
        ('2025-04-01', 'Ramazan Bayramı', 0),
        ('2025-06-05', 'Kurban Bayramı Arifesi', 1),
        ('2025-06-06', 'Kurban Bayramı', 0), ('2025-06-07', 'Kurban Bayramı', 0),
        ('2025-06-08', 'Kurban Bayramı', 0), ('2025-06-09', 'Kurban Bayramı', 0),

        ('2026-03-19', 'Ramazan Bayramı Arifesi', 1),
        ('2026-03-20', 'Ramazan Bayramı', 0), ('2026-03-21', 'Ramazan Bayramı', 0),
        ('2026-03-22', 'Ramazan Bayramı', 0),
        ('2026-05-26', 'Kurban Bayramı Arifesi', 1),
        ('2026-05-27', 'Kurban Bayramı', 0), ('2026-05-28', 'Kurban Bayramı', 0),
        ('2026-05-29', 'Kurban Bayramı', 0), ('2026-05-30', 'Kurban Bayramı', 0)
    ) AS r (holiday_date, holiday_name, is_half_day)
    WHERE CAST(r.holiday_date AS DATE) BETWEEN @from_date AND @to_date;

    -- a fixed holiday and a religious one can land on the same date - 23 April
    -- 2023 is both Ulusal Egemenlik ve Çocuk Bayramı and the third day of
    -- Ramazan Bayramı that year. Left alone this puts two rows in
    -- ref_public_holiday for one date, and the join below would then try to
    -- insert that date_key into dim_date twice.
    --
    -- found by running this against a real, constraint-enforcing SQL Server -
    -- Fabric Warehouse would have accepted the duplicate silently (NOT
    -- ENFORCED) and quietly double-counted every fact joined to that day.
    -- exactly the failure mode ADR-0002 warns about.
    --
    -- the "full day beats half day" tie-break is expressed with GROUP BY +
    -- MAX/MIN rather than ROW_NUMBER()+DELETE, and staged with SELECT...INTO
    -- rather than CREATE TABLE + INSERT INTO - see the #years note above,
    -- the same temp-table restriction applies here.
    SELECT
        holiday_date,
        CASE WHEN MAX(CASE WHEN is_half_day = 0 THEN 1 ELSE 0 END) = 1
             THEN MIN(CASE WHEN is_half_day = 0 THEN holiday_name END)
             ELSE MIN(CASE WHEN is_half_day = 1 THEN holiday_name END)
        END AS holiday_name,
        CASE WHEN MAX(CASE WHEN is_half_day = 0 THEN 1 ELSE 0 END) = 1 THEN 0 ELSE 1 END AS is_half_day
    INTO #holiday_dedup
    FROM gold.ref_public_holiday
    GROUP BY holiday_date;

    DELETE FROM gold.ref_public_holiday;
    INSERT INTO gold.ref_public_holiday (holiday_date, holiday_name, is_half_day)
    SELECT holiday_date, holiday_name, is_half_day FROM #holiday_dedup;
    DROP TABLE #holiday_dedup;

    DELETE FROM gold.dim_date;

    WITH numbers AS
    (
        SELECT TOP (DATEDIFF(DAY, @from_date, @to_date) + 1) n
        FROM ctl.util_numbers
        ORDER BY n
    ),
    calendar AS
    (
        SELECT DATEADD(DAY, n, @from_date) AS d FROM numbers
    )
    INSERT INTO gold.dim_date
    (
        date_key, full_date,
        day_of_month, day_of_year, day_of_week, day_name_tr, day_name_en, day_abbr_tr,
        iso_week, iso_year, week_start_date,
        month_number, month_name_tr, month_name_en, month_key, month_year_label,
        first_day_of_month, last_day_of_month, days_in_month,
        quarter_number, quarter_label, year_number,
        fiscal_year, fiscal_quarter, fiscal_month,
        is_weekend, is_public_holiday, is_half_day, holiday_name, is_working_day,
        same_date_last_year_key, same_month_last_year_key
    )
    SELECT
        YEAR(c.d) * 10000 + MONTH(c.d) * 100 + DAY(c.d),
        c.d,
        DAY(c.d),
        DATEPART(DAYOFYEAR, c.d),

        ((DATEPART(WEEKDAY, c.d) + @@DATEFIRST - 2) % 7) + 1,
        dn.name_tr, dn.name_en, dn.abbr_tr,
        DATEPART(ISO_WEEK, c.d),
        YEAR(DATEADD(DAY, 26 - DATEPART(ISO_WEEK, c.d) * 7, c.d)),
        DATEADD(DAY, -(((DATEPART(WEEKDAY, c.d) + @@DATEFIRST - 2) % 7)), c.d),
        MONTH(c.d), mn.name_tr, mn.name_en,
        YEAR(c.d) * 100 + MONTH(c.d),
        CONCAT(CAST(YEAR(c.d) AS VARCHAR(4)), '-', RIGHT(CONCAT('0', CAST(MONTH(c.d) AS VARCHAR(2))), 2)),
        DATEFROMPARTS(YEAR(c.d), MONTH(c.d), 1),
        EOMONTH(c.d),
        DAY(EOMONTH(c.d)),
        DATEPART(QUARTER, c.d),
        CONCAT(CAST(YEAR(c.d) AS VARCHAR(4)), '-Q', CAST(DATEPART(QUARTER, c.d) AS VARCHAR(1))),
        YEAR(c.d),

        YEAR(c.d), DATEPART(QUARTER, c.d), MONTH(c.d),
        CASE WHEN ((DATEPART(WEEKDAY, c.d) + @@DATEFIRST - 2) % 7) + 1 >= 6 THEN 1 ELSE 0 END,
        CASE WHEN h.holiday_date IS NOT NULL AND h.is_half_day = 0 THEN 1 ELSE 0 END,
        CASE WHEN h.is_half_day = 1 THEN 1 ELSE 0 END,
        h.holiday_name,
        CASE
            WHEN ((DATEPART(WEEKDAY, c.d) + @@DATEFIRST - 2) % 7) + 1 >= 6 THEN 0
            WHEN h.holiday_date IS NOT NULL AND h.is_half_day = 0 THEN 0
            ELSE 1
        END,
        CASE WHEN DATEADD(YEAR, -1, c.d) >= @from_date
             THEN YEAR(DATEADD(YEAR, -1, c.d)) * 10000
                  + MONTH(DATEADD(YEAR, -1, c.d)) * 100
                  + DAY(DATEADD(YEAR, -1, c.d))
        END,
        CASE WHEN DATEADD(YEAR, -1, c.d) >= @from_date
             THEN (YEAR(c.d) - 1) * 100 + MONTH(c.d)
        END
    FROM calendar AS c
    LEFT JOIN gold.ref_public_holiday AS h ON h.holiday_date = c.d
    INNER JOIN (VALUES
        (1, 'Pazartesi', 'Monday',    'Pzt'),
        (2, 'Salı',      'Tuesday',   'Sal'),
        (3, 'Çarşamba',  'Wednesday', 'Çar'),
        (4, 'Perşembe',  'Thursday',  'Per'),
        (5, 'Cuma',      'Friday',    'Cum'),
        (6, 'Cumartesi', 'Saturday',  'Cmt'),
        (7, 'Pazar',     'Sunday',    'Paz')
    ) AS dn (dow, name_tr, name_en, abbr_tr)
        ON dn.dow = ((DATEPART(WEEKDAY, c.d) + @@DATEFIRST - 2) % 7) + 1
    INNER JOIN (VALUES
        (1, 'Ocak', 'January'),    (2, 'Şubat', 'February'),
        (3, 'Mart', 'March'),      (4, 'Nisan', 'April'),
        (5, 'Mayıs', 'May'),       (6, 'Haziran', 'June'),
        (7, 'Temmuz', 'July'),     (8, 'Ağustos', 'August'),
        (9, 'Eylül', 'September'), (10, 'Ekim', 'October'),
        (11, 'Kasım', 'November'), (12, 'Aralık', 'December')
    ) AS mn (mon, name_tr, name_en)
        ON mn.mon = MONTH(c.d);

    INSERT INTO gold.dim_date
    (
        date_key, full_date, day_of_month, day_of_year, day_of_week,
        day_name_tr, day_name_en, day_abbr_tr, iso_week, iso_year, week_start_date,
        month_number, month_name_tr, month_name_en, month_key, month_year_label,
        first_day_of_month, last_day_of_month, days_in_month,
        quarter_number, quarter_label, year_number,
        fiscal_year, fiscal_quarter, fiscal_month,
        is_weekend, is_public_holiday, is_half_day, holiday_name, is_working_day,
        same_date_last_year_key, same_month_last_year_key
    )
    VALUES
        (-1, '1900-01-01', 0, 0, 0, 'Bilinmiyor', 'Unknown', 'Blm',
         0, 0, '1900-01-01', 0, 'Bilinmiyor', 'Unknown', 0, 'Unknown',
         '1900-01-01', '1900-01-01', 0, 0, 'Unknown', 0, 0, 0, 0,
         0, 0, 0, NULL, 0, NULL, NULL);

    SELECT COUNT(*) AS rows_created,
           SUM(CAST(is_working_day AS INT)) AS working_days,
           SUM(CAST(is_public_holiday AS INT)) AS public_holidays
    FROM gold.dim_date;
END;
GO

CREATE VIEW gold.vw_date_contract AS
    SELECT date_key AS contract_date_key, full_date AS contract_date,
           month_year_label AS contract_month, quarter_label AS contract_quarter,
           year_number AS contract_year
    FROM gold.dim_date;
GO

CREATE VIEW gold.vw_date_delivery AS
    SELECT date_key AS delivery_date_key, full_date AS delivery_date,
           month_year_label AS delivery_month, quarter_label AS delivery_quarter,
           year_number AS delivery_year
    FROM gold.dim_date;
GO

CREATE VIEW gold.vw_date_registration AS
    SELECT date_key AS registration_date_key, full_date AS registration_date,
           month_year_label AS registration_month, year_number AS registration_year
    FROM gold.dim_date;
GO
