
CREATE TABLE ctl.vin_weight
(
    vin_position    INT     NOT NULL,
    weight          INT     NOT NULL
);
GO

INSERT INTO ctl.vin_weight (vin_position, weight)
SELECT * FROM (VALUES
    (1, 8), (2, 7), (3, 6), (4, 5), (5, 4), (6, 3), (7, 2),
    (8, 10),
    (9, 0),
    (10, 9), (11, 8), (12, 7), (13, 6), (14, 5), (15, 4), (16, 3), (17, 2)
) AS v (vin_position, weight);
GO

CREATE TABLE ctl.vin_transliteration
(
    vin_character   VARCHAR(1)  NOT NULL,
    numeric_value   INT         NOT NULL
);
GO

INSERT INTO ctl.vin_transliteration (vin_character, numeric_value)
SELECT * FROM (VALUES
    ('0',0), ('1',1), ('2',2), ('3',3), ('4',4),
    ('5',5), ('6',6), ('7',7), ('8',8), ('9',9),

    ('A',1), ('B',2), ('C',3), ('D',4), ('E',5), ('F',6), ('G',7), ('H',8),
    ('J',1), ('K',2), ('L',3), ('M',4), ('N',5), ('P',7), ('R',9),
    ('S',2), ('T',3), ('U',4), ('V',5), ('W',6), ('X',7), ('Y',8), ('Z',9)
) AS v (vin_character, numeric_value);
GO

CREATE VIEW ctl.vw_vin_check_digit
AS
WITH all_vins AS
(
    SELECT 'sales_contract' AS source_entity, contract_no      AS business_key, vin FROM silver.sales_contract
    UNION ALL
    SELECT 'repair_order',                    repair_order_no,                  vin FROM silver.repair_order
    UNION ALL
    SELECT 'vehicle',                         vin,                              vin FROM silver.vehicle
),
structurally_valid AS
(
    SELECT source_entity, business_key, vin
    FROM all_vins
    WHERE vin IS NOT NULL
      AND LEN(vin) = 17
      AND vin NOT LIKE '%[IOQ]%'
),
weighted AS
(
    SELECT
        sv.source_entity,
        sv.business_key,
        sv.vin,
        SUM(t.numeric_value * w.weight) % 11 AS remainder
    FROM structurally_valid AS sv
    CROSS JOIN ctl.vin_weight AS w
    INNER JOIN ctl.vin_transliteration AS t
        ON t.vin_character = SUBSTRING(sv.vin, w.vin_position, 1)
    GROUP BY sv.source_entity, sv.business_key, sv.vin

    HAVING COUNT(*) = 17
)
SELECT
    source_entity,
    business_key,
    vin,
    SUBSTRING(vin, 9, 1) AS actual_check_digit,
    CASE WHEN remainder = 10 THEN 'X' ELSE CAST(remainder AS VARCHAR(1)) END
        AS expected_check_digit,
    CASE WHEN SUBSTRING(vin, 9, 1) =
              CASE WHEN remainder = 10 THEN 'X' ELSE CAST(remainder AS VARCHAR(1)) END
         THEN 1 ELSE 0 END AS is_valid
FROM weighted;
GO
