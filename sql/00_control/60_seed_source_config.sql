-- üretilmiş dosya, elle düzenleme - bkz. tools/generate_ctl_seed.py
-- 2026-09-13 21:37:24 tarihinde data/_manifest.json'dan üretildi (17 varlık)

DELETE FROM ctl.source_config;
GO

INSERT INTO ctl.source_config
    (source_id, source_system, entity, target_table,
     file_pattern, is_date_partitioned,
     file_format, delimiter, decimal_mark, encoding, has_header, sheet_name,
     load_type, watermark_column, watermark_value, key_columns,
     is_active, load_order, retry_limit, description, created_ts, updated_ts)
SELECT * FROM (VALUES
    (1, 'dms', 'dealer', 'bronze.dms_dealer', 'dms/dealer_*.csv', 0, 'csv', ';', ',', 'windows-1254', 1, NULL, 'full', NULL, NULL, 'dealer_code', 1, 10, 2, 'DMS dealer (full, 44 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (2, 'dms', 'employee', 'bronze.dms_employee', 'dms/employee_*.csv', 0, 'csv', ';', ',', 'windows-1254', 1, NULL, 'full', NULL, NULL, 'employee_id', 1, 20, 2, 'DMS employee (full, 44 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (3, 'dms', 'model_trim', 'bronze.dms_model_trim', 'dms/model_trim_*.csv', 0, 'csv', ';', ',', 'windows-1254', 1, NULL, 'full', NULL, NULL, 'model_trim_code', 1, 30, 2, 'DMS model trim (full, 44 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (4, 'parts', 'supplier', 'bronze.parts_supplier', 'parts/supplier_*.csv', 0, 'csv', ',', '.', 'utf-8', 1, NULL, 'full', NULL, NULL, 'supplier_id', 1, 40, 2, 'PARTS supplier (full, 44 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (5, 'parts', 'part', 'bronze.parts_part', 'parts/part_*.csv', 0, 'csv', ',', '.', 'utf-8', 1, NULL, 'incremental', 'last_modified_ts', NULL, 'part_no', 1, 50, 2, 'PARTS part (incremental, 44 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (6, 'dms', 'customer', 'bronze.dms_customer', 'dms/customer_*.csv', 0, 'csv', ';', ',', 'windows-1254', 1, NULL, 'incremental', 'last_modified_ts', NULL, 'customer_id', 1, 60, 2, 'DMS customer (incremental, 44 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (7, 'crm', 'customer', 'bronze.crm_customer', 'crm/customer_*.json', 0, 'json', NULL, NULL, 'utf-8', 1, NULL, 'incremental', 'last_modified_ts', NULL, 'crm_id', 1, 70, 2, 'CRM customer (incremental, 44 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (8, 'dms', 'vehicle_stock', 'bronze.dms_vehicle_stock', 'dms/vehicle_stock_*.csv', 0, 'csv', ';', ',', 'windows-1254', 1, NULL, 'incremental', 'last_modified_ts', NULL, 'vin', 1, 80, 2, 'DMS vehicle stock (incremental, 44 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (9, 'finance', 'fx_rate', 'bronze.finance_fx_rate', 'finance/finance_plan_*.xlsx', 0, 'xlsx', NULL, NULL, 'utf-8', 1, 'fx_rate', 'full', NULL, NULL, 'rate_date,currency_code', 1, 90, 2, 'FINANCE fx rate (full, 1 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (10, 'finance', 'budget', 'bronze.finance_budget', 'finance/finance_plan_*.xlsx', 0, 'xlsx', NULL, NULL, 'utf-8', 1, 'budget', 'full', NULL, NULL, 'dealer_code,budget_year,budget_month,metric_code', 1, 100, 2, 'FINANCE budget (full, 1 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (11, 'dms', 'sales_contract', 'bronze.dms_sales_contract', 'dms/sales_contract_*.csv', 0, 'csv', ';', ',', 'windows-1254', 1, NULL, 'incremental', 'contract_date', NULL, 'contract_no', 1, 110, 2, 'DMS sales contract (incremental, 44 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (12, 'workshop', 'repair_order', 'bronze.workshop_repair_order', 'workshop/repair_order/*/repair_order_*.csv', 1, 'csv', ',', '.', 'utf-8', 1, NULL, 'incremental', 'checkin_ts', NULL, 'repair_order_no', 1, 120, 2, 'WORKSHOP repair order (incremental, 918 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (13, 'workshop', 'repair_order_line', 'bronze.workshop_repair_order_line', 'workshop/repair_order_line/*/repair_order_line_*.csv', 1, 'csv', ',', '.', 'utf-8', 1, NULL, 'incremental', 'checkin_ts', NULL, 'repair_order_no,line_no', 1, 130, 2, 'WORKSHOP repair order line (incremental, 918 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (14, 'parts', 'purchase_order_line', 'bronze.parts_purchase_order_line', 'parts/purchase_order_line_*.csv', 0, 'csv', ',', '.', 'utf-8', 1, NULL, 'incremental', 'order_date', NULL, 'po_no,po_line_no', 1, 140, 2, 'PARTS purchase order line (incremental, 43 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (15, 'portal', 'warranty_claim', 'bronze.portal_warranty_claim', 'portal/warranty_claim_*.jsonl', 0, 'jsonl', NULL, NULL, 'utf-8', 1, NULL, 'incremental', 'claim_date', NULL, 'claim_no', 1, 150, 2, 'PORTAL warranty claim (incremental, 44 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (16, 'portal', 'recall_campaign', 'bronze.portal_recall_campaign', 'portal/recall_campaign_*.json', 0, 'json', NULL, NULL, 'utf-8', 1, NULL, 'full', NULL, NULL, 'campaign_code', 1, 160, 2, 'PORTAL recall campaign (full, 1 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24'),
    (17, 'portal', 'recall_coverage', 'bronze.portal_recall_coverage', 'portal/recall_coverage_*.jsonl', 0, 'jsonl', NULL, NULL, 'utf-8', 1, NULL, 'full', NULL, NULL, 'campaign_code,vin', 1, 170, 2, 'PORTAL recall coverage (full, 1 file(s) at generation time)', '2026-09-13 21:37:24', '2026-09-13 21:37:24')
) AS v (source_id, source_system, entity, target_table,
        file_pattern, is_date_partitioned,
        file_format, delimiter, decimal_mark, encoding, has_header, sheet_name,
        load_type, watermark_column, watermark_value, key_columns,
        is_active, load_order, retry_limit, description, created_ts, updated_ts);
GO
