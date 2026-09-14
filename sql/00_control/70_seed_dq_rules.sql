-- generated file, do not edit by hand - see tools/generate_ctl_seed.py
-- generated 2026-09-13 21:37:24 - 25 rules, 21 codes, 15 injectable defects covered

DELETE FROM ctl.dq_rule;
GO

--  1. VIN_FORMAT :: VIN is 17 characters and contains no I, O or Q
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (1, 'VIN_FORMAT', 'VIN is 17 characters and contains no I, O or Q', 'silver',
     'silver.repair_order', 'vin', 'regex',
     'SELECT repair_order_no AS business_key,
       CONCAT(''vin='', vin, '' len='', CAST(LEN(vin) AS VARCHAR(4))) AS detail
FROM silver.repair_order
WHERE vin IS NOT NULL AND vin <> '''' AND vin_well_formed = 0',
     'critical', 1, 0.15, 1, 'ISO 3779 forbids I, O and Q anywhere in a VIN because they are confused with 1, 0 and 0 when read off a stamped plate. Null VINs are deliberately excluded here - they are a different defect and BUSINESS_KEY_NULL reports them, so the two rules stay separable.', '2026-09-13 21:37:24');
GO

--  2. VIN_FORMAT :: VIN is 17 characters and contains no I, O or Q (sales)
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (2, 'VIN_FORMAT', 'VIN is 17 characters and contains no I, O or Q (sales)', 'silver',
     'silver.sales_contract', 'vin', 'regex',
     'SELECT contract_no AS business_key,
       CONCAT(''vin='', vin, '' len='', CAST(LEN(vin) AS VARCHAR(4))) AS detail
FROM silver.sales_contract
WHERE vin IS NOT NULL AND vin <> '''' AND vin_well_formed = 0',
     'critical', 1, 0.15, 1, 'VIN is 17 characters and contains no I, O or Q (sales)', '2026-09-13 21:37:24');
GO

--  3. VIN_CHECK_DIGIT :: VIN check digit matches ISO 3779
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (3, 'VIN_CHECK_DIGIT', 'VIN check digit matches ISO 3779', 'silver',
     'silver.repair_order', 'vin', 'business',
     'SELECT repair_order_no AS business_key,
       CONCAT(''vin='', vin, '' fails the ISO 3779 check digit'') AS detail
FROM silver.repair_order
WHERE vin_check_digit_valid = 0',
     'warning', 0, 0.15, 1, 'The rule that separates ''I wrote a data quality check'' from ''I understood the domain''. A VIN can be exactly 17 legal characters and still be wrong; only position 9 catches a transposition, which is what human transcription actually produces. Warning rather than critical: the vehicle is probably real and the VIN probably has one digit wrong, so quarantining the repair order would lose genuine revenue to fix a typo. The check digit is computed once in Silver and stored, so this rule is a boolean test that runs identically in the Warehouse procedure and in the Spark runner. Pointing it at ctl.vw_vin_check_digit instead would tie every DQ run to the Warehouse and to ADR-0002 item 4, which is unverified - and rules as data only pays off if the rules do not secretly depend on one engine.', '2026-09-13 21:37:24');
GO

--  4. VIN_CHECK_DIGIT :: VIN check digit matches ISO 3779 (sales)
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (4, 'VIN_CHECK_DIGIT', 'VIN check digit matches ISO 3779 (sales)', 'silver',
     'silver.sales_contract', 'vin', 'business',
     'SELECT contract_no AS business_key,
       CONCAT(''vin='', vin, '' fails the ISO 3779 check digit'') AS detail
FROM silver.sales_contract
WHERE vin_check_digit_valid = 0',
     'warning', 0, 0.15, 1, 'VIN check digit matches ISO 3779 (sales)', '2026-09-13 21:37:24');
GO

--  5. VIN_DUPLICATE_NEW_SALE :: A VIN can be sold as new only once
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (5, 'VIN_DUPLICATE_NEW_SALE', 'A VIN can be sold as new only once', 'silver',
     'silver.sales_contract', 'vin', 'unique',
     'SELECT contract_no AS business_key,
       CONCAT(''vin='', vin, '' appears on '',
              CAST(sale_count AS VARCHAR(6)), '' new-vehicle contracts'') AS detail
FROM (
    SELECT contract_no, vin,
           COUNT(*) OVER (PARTITION BY vin) AS sale_count
    FROM silver.sales_contract
    WHERE sale_type = ''NEW'' AND vin IS NOT NULL AND vin <> ''''
) AS d
WHERE sale_count > 1',
     'critical', 1, 0.15, 1, 'Physically impossible and genuinely common. A vehicle leaves the factory once; a second ''NEW'' contract for the same VIN is either a duplicated record or a used car booked under the wrong type. Either way it double-counts a unit sale and inflates revenue.', '2026-09-13 21:37:24');
GO

--  6. VIN_ORPHAN :: Repair order VIN exists in the vehicle master
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (6, 'VIN_ORPHAN', 'Repair order VIN exists in the vehicle master', 'silver',
     'silver.repair_order', 'vin', 'referential',
     'SELECT ro.repair_order_no AS business_key,
       CONCAT(''vin='', ro.vin, '' not present in silver.vehicle'') AS detail
FROM silver.repair_order AS ro
WHERE ro.vin IS NOT NULL AND ro.vin <> ''''
  AND NOT EXISTS (SELECT 1 FROM silver.vehicle AS v WHERE v.vin = ro.vin)',
     'warning', 0, 0.3, 1, 'Fabric Warehouse constraints are NOT ENFORCED, so referential integrity is our job. Deliberately a warning and NOT quarantined: in automotive this is often legitimate - a car bought from another dealer in the network arrives for service and the vehicle master has genuinely never seen it. Gold creates an inferred member for these rather than dropping the fact. The rule exists to measure how often it happens, not to reject it.', '2026-09-13 21:37:24');
GO

--  7. PLATE_FORMAT :: Plate matches the Turkish format
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (7, 'PLATE_FORMAT', 'Plate matches the Turkish format', 'silver',
     'silver.repair_order', 'plate_masked', 'regex',
     'SELECT repair_order_no AS business_key,
       CONCAT(''plate='', plate_masked) AS detail
FROM silver.repair_order
WHERE plate_masked IS NOT NULL AND plate_masked <> ''''
  AND plate_masked NOT LIKE ''[0-9][0-9] *** [0-9][0-9]''
  AND plate_masked NOT LIKE ''[0-9][0-9] *** [0-9][0-9][0-9]''
  AND plate_masked NOT LIKE ''[0-9][0-9] *** [0-9][0-9][0-9][0-9]''
  AND plate_masked NOT LIKE ''[0-9][0-9] *** [0-9][0-9][0-9][0-9][0-9]''',
     'warning', 0, 0.15, 1, 'Turkish plates are a province code, then one to three letters, then two to five digits, with the letter and digit counts constrained together. The letter class excludes Q, W and X, which do not exist in the Turkish alphabet. T-SQL has no regex, so this was five LIKE patterns - but Silver only ever exposes the PII-masked plate (mask_plate collapses every letter run to a literal ''***'', regardless of whether it was 1, 2 or 3 letters), so the letter/digit-count correlation this rule was designed to check is gone by the time it can run. What''s left checkable is the coarser shape: two digits, ''***'', two-to-five digits.', '2026-09-13 21:37:24');
GO

--  8. PLATE_PROVINCE :: Plate province code is between 01 and 81
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (8, 'PLATE_PROVINCE', 'Plate province code is between 01 and 81', 'silver',
     'silver.repair_order', 'plate_masked', 'range',
     'SELECT repair_order_no AS business_key,
       CONCAT(''plate='', plate_masked, '' province='',
              LEFT(plate_masked, 2)) AS detail
FROM silver.repair_order
WHERE plate_masked IS NOT NULL AND LEN(plate_masked) >= 2
  AND (TRY_CAST(LEFT(plate_masked, 2) AS INT) IS NULL
       OR TRY_CAST(LEFT(plate_masked, 2) AS INT) < 1
       OR TRY_CAST(LEFT(plate_masked, 2) AS INT) > 81)',
     'warning', 0, 0.15, 1, 'Turkey has 81 provinces. A plate beginning 84 is not a formatting problem, it is a value that cannot exist - which is why this is a separate rule from the format check and would be actioned differently. Reads plate_masked rather than the raw plate: mask_plate only touches the letter run, so the province digits survive masking untouched and this check loses nothing by running after PII masking, unlike PLATE_FORMAT.', '2026-09-13 21:37:24');
GO

--  9. ODOMETER_ROLLBACK :: Odometer never decreases for a VIN
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (9, 'ODOMETER_ROLLBACK', 'Odometer never decreases for a VIN', 'silver',
     'silver.repair_order', 'odometer_km', 'business',
     'SELECT repair_order_no AS business_key,
       CONCAT(''vin='', vin, '' reading='', CAST(odometer_km AS VARCHAR(12)),
              '' previous='', CAST(previous_km AS VARCHAR(12)),
              '' on '', CAST(previous_ts AS VARCHAR(10))) AS detail
FROM (
    SELECT repair_order_no, vin, odometer_km, checkin_ts,
           LAG(odometer_km) OVER (PARTITION BY vin ORDER BY checkin_ts) AS previous_km,
           LAG(checkin_ts)  OVER (PARTITION BY vin ORDER BY checkin_ts) AS previous_ts
    FROM silver.repair_order
    WHERE vin IS NOT NULL AND vin <> '''' AND odometer_km IS NOT NULL
) AS r
WHERE previous_km IS NOT NULL AND odometer_km < previous_km',
     'critical', 1, 0.15, 1, 'The best argument in this project for why data quality belongs in the platform rather than in source-system field validation. Each individual reading is perfectly plausible; the value is only wrong in the context of the same VIN''s other readings, which no single form can see. Critical because a rolled-back odometer corrupts every mileage-based measure downstream - service interval compliance, average km at repair, warranty distance eligibility.', '2026-09-13 21:37:24');
GO

-- 10. RO_DATE_SEQUENCE :: Repair order stages run in order
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (10, 'RO_DATE_SEQUENCE', 'Repair order stages run in order', 'silver',
     'silver.repair_order', NULL, 'business',
     'SELECT repair_order_no AS business_key,
       CONCAT(''checkin='', LEFT(CAST(checkin_ts AS VARCHAR(30)), 19),
              '' repair_start='', COALESCE(LEFT(CAST(repair_start_ts AS VARCHAR(30)), 19), ''-''),
              '' delivery='', COALESCE(LEFT(CAST(delivery_ts AS VARCHAR(30)), 19), ''-'')) AS detail
FROM silver.repair_order
WHERE (appointment_date IS NOT NULL AND appointment_date > CAST(checkin_ts AS DATE))
   OR (inspection_ts   IS NOT NULL AND inspection_ts   < checkin_ts)
   OR (repair_start_ts IS NOT NULL AND repair_start_ts < checkin_ts)
   OR (repair_end_ts   IS NOT NULL AND repair_end_ts   < repair_start_ts)
   OR (qc_ts           IS NOT NULL AND qc_ts           < repair_end_ts)
   OR (delivery_ts     IS NOT NULL AND delivery_ts     < checkin_ts)',
     'critical', 1, 0.15, 1, 'The accumulating snapshot''s stage columns are the source of every duration measure in the aftersales report. A delivery timestamp before check-in does not just look wrong, it produces a negative cycle time that silently drags the average down. Nulls are allowed throughout - an unfinished order legitimately has no later stages.', '2026-09-13 21:37:24');
GO

-- 11. LABOUR_HOURS_NEGATIVE :: Labour hours are not negative
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (11, 'LABOUR_HOURS_NEGATIVE', 'Labour hours are not negative', 'silver',
     'silver.repair_order_line', 'labour_hours', 'range',
     'SELECT CONCAT(repair_order_no, ''#'', CAST(line_no AS VARCHAR(6))) AS business_key,
       CONCAT(''labour_hours='', CAST(labour_hours AS VARCHAR(20))) AS detail
FROM silver.repair_order_line
WHERE labour_hours < 0',
     'critical', 1, 0.15, 1, 'Labour hours are not negative', '2026-09-13 21:37:24');
GO

-- 12. LABOUR_HOURS_EXCESSIVE :: A single labour line stays under 100 hours
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (12, 'LABOUR_HOURS_EXCESSIVE', 'A single labour line stays under 100 hours', 'silver',
     'silver.repair_order_line', 'labour_hours', 'range',
     'SELECT CONCAT(repair_order_no, ''#'', CAST(line_no AS VARCHAR(6))) AS business_key,
       CONCAT(''labour_hours='', CAST(labour_hours AS VARCHAR(20))) AS detail
FROM silver.repair_order_line
WHERE labour_hours > 100',
     'warning', 0, 0.15, 1, 'One operation line cannot plausibly take two and a half working weeks. The threshold is set well above the longest real job in this dataset - body and paint tops out around 30 hours - so it flags data entry, not busy workshops. A warning rather than critical because the labour was probably done; the number is what is wrong.', '2026-09-13 21:37:24');
GO

-- 13. WARRANTY_AMOUNT_OVERFLOW :: Warranty amount does not exceed the line total
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (13, 'WARRANTY_AMOUNT_OVERFLOW', 'Warranty amount does not exceed the line total', 'silver',
     'silver.repair_order_line', 'warranty_amount', 'business',
     'SELECT CONCAT(repair_order_no, ''#'', CAST(line_no AS VARCHAR(6))) AS business_key,
       CONCAT(''warranty='', CAST(warranty_amount AS VARCHAR(24)),
              '' line='', CAST(line_amount AS VARCHAR(24))) AS detail
FROM silver.repair_order_line
WHERE warranty_amount > line_amount + 0.01',
     'critical', 1, 0.15, 1, 'The manufacturer cannot reimburse more than the work is worth. This one is also a cascade: because the repair order header carries its own warranty total, a line pushed above its value also breaks HEADER_LINE_MISMATCH. The injection log records that cascade so the second detection is scored as expected rather than as a false positive.', '2026-09-13 21:37:24');
GO

-- 14. HEADER_LINE_MISMATCH :: Repair order header totals equal the sum of their lines
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (14, 'HEADER_LINE_MISMATCH', 'Repair order header totals equal the sum of their lines', 'silver',
     'silver.repair_order', NULL, 'business',
     'SELECT h.repair_order_no AS business_key,
       CONCAT(''header_warranty='', CAST(h.total_warranty_amount AS VARCHAR(24)),
              '' line_sum='', CAST(COALESCE(l.warranty_sum, 0) AS VARCHAR(24))) AS detail
FROM silver.repair_order AS h
LEFT JOIN (
    SELECT repair_order_no,
           SUM(warranty_amount) AS warranty_sum,
           SUM(line_amount)     AS line_sum
    FROM silver.repair_order_line
    GROUP BY repair_order_no
) AS l ON l.repair_order_no = h.repair_order_no
WHERE ABS(h.total_warranty_amount - COALESCE(l.warranty_sum, 0)) > 0.02
   OR ABS(h.total_labour_amount + h.total_part_amount
          - COALESCE(l.line_sum, 0)) > 0.02',
     'warning', 0, 0.15, 1, 'The header stores totals its lines already add up to. That redundancy is how real dealer systems work, and it is deliberate here: it gives the platform a reconciliation with a knowable answer. The generator proves the totals tie before injection, so every mismatch found is one that was created on purpose.', '2026-09-13 21:37:24');
GO

-- 15. PART_NO_ORPHAN :: Repair order line part exists in the part master
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (15, 'PART_NO_ORPHAN', 'Repair order line part exists in the part master', 'silver',
     'silver.repair_order_line', 'part_no', 'referential',
     'SELECT CONCAT(l.repair_order_no, ''#'', CAST(l.line_no AS VARCHAR(6))) AS business_key,
       CONCAT(''part_no='', l.part_no, '' not present in silver.part'') AS detail
FROM silver.repair_order_line AS l
WHERE l.line_type = ''PART'' AND l.part_no IS NOT NULL AND l.part_no <> ''''
  AND NOT EXISTS (SELECT 1 FROM silver.part AS p WHERE p.part_no = l.part_no)',
     'critical', 1, 0.15, 1, 'Repair order line part exists in the part master', '2026-09-13 21:37:24');
GO

-- 16. PART_NO_ORPHAN :: Purchase order line part exists in the part master
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (16, 'PART_NO_ORPHAN', 'Purchase order line part exists in the part master', 'silver',
     'silver.purchase_order_line', 'part_no', 'referential',
     'SELECT CONCAT(l.po_no, ''#'', CAST(l.po_line_no AS VARCHAR(6))) AS business_key,
       CONCAT(''part_no='', l.part_no, '' not present in silver.part'') AS detail
FROM silver.purchase_order_line AS l
WHERE l.part_no IS NOT NULL AND l.part_no <> ''''
  AND NOT EXISTS (SELECT 1 FROM silver.part AS p WHERE p.part_no = l.part_no)',
     'critical', 1, 0.15, 1, 'Purchase order line part exists in the part master', '2026-09-13 21:37:24');
GO

-- 17. DEALER_ORPHAN :: Repair order dealer exists in the dealer master
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (17, 'DEALER_ORPHAN', 'Repair order dealer exists in the dealer master', 'silver',
     'silver.repair_order', 'dealer_code', 'referential',
     'SELECT ro.repair_order_no AS business_key,
       CONCAT(''dealer_code='', ro.dealer_code) AS detail
FROM silver.repair_order AS ro
WHERE ro.dealer_code IS NOT NULL AND ro.dealer_code <> ''''
  AND NOT EXISTS (SELECT 1 FROM silver.dealer AS d
                  WHERE d.dealer_code = ro.dealer_code)',
     'critical', 1, 0.15, 1, 'Not an injected defect - this rule exists to prove the framework reports zero when the data is clean. A DQ suite in which every rule always fires is indistinguishable from a DQ suite that is broken.', '2026-09-13 21:37:24');
GO

-- 18. BUSINESS_KEY_NULL :: Repair order carries a VIN
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (18, 'BUSINESS_KEY_NULL', 'Repair order carries a VIN', 'silver',
     'silver.repair_order', 'vin', 'not_null',
     'SELECT repair_order_no AS business_key,
       ''vin is null or blank'' AS detail
FROM silver.repair_order
WHERE vin IS NULL OR vin = ''''',
     'critical', 1, 0.15, 1, 'Repair order carries a VIN', '2026-09-13 21:37:24');
GO

-- 19. BUSINESS_KEY_NULL :: Sales contract carries a customer
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (19, 'BUSINESS_KEY_NULL', 'Sales contract carries a customer', 'silver',
     'silver.sales_contract', 'customer_id', 'not_null',
     'SELECT contract_no AS business_key,
       ''customer_id is null or blank'' AS detail
FROM silver.sales_contract
WHERE customer_id IS NULL OR customer_id = ''''',
     'critical', 1, 0.15, 1, 'Sales contract carries a customer', '2026-09-13 21:37:24');
GO

-- 20. DATE_FORMAT_INCONSISTENT :: Contract dates parsed to a real date
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (20, 'DATE_FORMAT_INCONSISTENT', 'Contract dates parsed to a real date', 'silver',
     'silver.sales_contract', 'contract_date', 'business',
     'SELECT contract_no AS business_key,
       CONCAT(''raw contract_date='', COALESCE(contract_date_raw, ''<null>'')) AS detail
FROM silver.sales_contract
WHERE contract_date IS NULL
  AND contract_date_raw IS NOT NULL AND contract_date_raw <> ''''',
     'critical', 1, 0.15, 1, 'The source file mixes ISO dates with Turkish dd.mm.yyyy in the same column. Silver parses both; this rule catches whatever it could not. The danger being guarded against is not a failed load - it is a silent NULL for the minority format, which nobody notices until a month is missing from a report.', '2026-09-13 21:37:24');
GO

-- 21. MODEL_YEAR_RANGE :: Model year is within one year of production
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (21, 'MODEL_YEAR_RANGE', 'Model year is within one year of production', 'silver',
     'silver.vehicle', 'model_year', 'range',
     'SELECT vin AS business_key,
       CONCAT(''model_year='', CAST(model_year AS VARCHAR(6)),
              '' production='', CAST(production_date AS VARCHAR(10))) AS detail
FROM silver.vehicle
WHERE model_year IS NOT NULL AND production_date IS NOT NULL
  AND (model_year - YEAR(production_date) > 1
       OR model_year - YEAR(production_date) < 0)',
     'warning', 0, 0.15, 1, 'A car built in the last quarter is normally registered as next year''s model, so a gap of one is expected and a gap of four is a defect. The rule encodes the industry practice rather than a generic ''is it a plausible year'' check.', '2026-09-13 21:37:24');
GO

-- 22. FX_RATE_MISSING :: Every foreign-currency amount has a rate to convert it
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (22, 'FX_RATE_MISSING', 'Every foreign-currency amount has a rate to convert it', 'silver',
     'silver.sales_contract', 'currency_code', 'referential',
     'SELECT c.contract_no AS business_key,
       CONCAT(''currency='', c.currency_code,
              '' date='', CAST(c.contract_date AS VARCHAR(10))) AS detail
FROM silver.sales_contract AS c
WHERE c.currency_code <> ''TRY''
  AND c.net_sale_amount IS NULL',
     'critical', 1, 0.15, 1, 'Rates are published on business days only, so a contract signed at a weekend has no rate of its own and Silver forward-fills the last published one. This rule proves the forward fill actually covered every row - a missed conversion does not fail loudly, it reports a lira amount that is really euros.', '2026-09-13 21:37:24');
GO

-- 23. SALE_DATE_SEQUENCE :: Contract, delivery and registration run in order
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (23, 'SALE_DATE_SEQUENCE', 'Contract, delivery and registration run in order', 'silver',
     'silver.sales_contract', NULL, 'business',
     'SELECT contract_no AS business_key,
       CONCAT(''contract='', CAST(contract_date AS VARCHAR(10)),
              '' delivery='', COALESCE(CAST(delivery_date AS VARCHAR(10)), ''-''),
              '' registration='', COALESCE(CAST(registration_date AS VARCHAR(10)), ''-'')) AS detail
FROM silver.sales_contract
WHERE (delivery_date IS NOT NULL AND delivery_date < contract_date)
   OR (registration_date IS NOT NULL AND delivery_date IS NOT NULL
       AND registration_date < delivery_date)',
     'warning', 0, 0.15, 1, 'Contract, delivery and registration run in order', '2026-09-13 21:37:24');
GO

-- 24. DISCOUNT_RATE_RANGE :: Discount is between zero and the list price
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (24, 'DISCOUNT_RATE_RANGE', 'Discount is between zero and the list price', 'silver',
     'silver.sales_contract', 'discount_amount', 'range',
     'SELECT contract_no AS business_key,
       CONCAT(''list='', CAST(list_price AS VARCHAR(24)),
              '' discount='', CAST(discount_amount AS VARCHAR(24))) AS detail
FROM silver.sales_contract
WHERE discount_amount < 0 OR discount_amount > list_price',
     'warning', 0, 0.15, 1, 'Discount is between zero and the list price', '2026-09-13 21:37:24');
GO

-- 25. MASTER_CUSTOMER_ASSIGNED :: Every contract resolves to an MDM golden record
INSERT INTO ctl.dq_rule
    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,
     rule_type, violation_sql, severity, quarantine_on_fail,
     max_violation_rate, is_active, description, created_ts)
VALUES
    (25, 'MASTER_CUSTOMER_ASSIGNED', 'Every contract resolves to an MDM golden record', 'silver',
     'silver.sales_contract', 'master_customer_id', 'referential',
     'SELECT contract_no AS business_key,
       CONCAT(''customer_id='', COALESCE(customer_id, ''<null>''),
              '' has no master_customer_id'') AS detail
FROM silver.sales_contract
WHERE master_customer_id IS NULL
  AND customer_id IS NOT NULL AND customer_id <> ''''',
     'warning', 0, 0.25, 1, 'Measures MDM coverage, not source data quality. A contract whose customer could not be resolved to a golden record still loads and points at the Unknown member - but the rate is the honest headline number for how well the matching worked, and it belongs on the data quality page rather than in a slide.', '2026-09-13 21:37:24');
GO
