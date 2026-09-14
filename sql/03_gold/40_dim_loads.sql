SELECT 'dim_dealer' t, COUNT(*) n FROM gold.dim_dealer WHERE dealer_sk > 0
UNION ALL SELECT 'dim_customer', COUNT(*) FROM gold.dim_customer WHERE customer_sk > 0
UNION ALL SELECT 'dim_vehicle', COUNT(*) FROM gold.dim_vehicle WHERE vehicle_sk > 0
UNION ALL SELECT 'dim_employee', COUNT(*) FROM gold.dim_employee WHERE employee_sk > 0
UNION ALL SELECT 'dim_model_trim', COUNT(*) FROM gold.dim_model_trim WHERE model_trim_sk > 0
UNION ALL SELECT 'dim_part', COUNT(*) FROM gold.dim_part WHERE part_sk > 0
UNION ALL SELECT 'dim_supplier', COUNT(*) FROM gold.dim_supplier WHERE supplier_sk > 0
UNION ALL SELECT 'dim_date', COUNT(*) FROM gold.dim_date
UNION ALL SELECT 'fact_vehicle_sale', COUNT(*) FROM gold.fact_vehicle_sale
UNION ALL SELECT 'fact_repair_order', COUNT(*) FROM gold.fact_repair_order
UNION ALL SELECT 'fact_repair_order_line', COUNT(*) FROM gold.fact_repair_order_line
UNION ALL SELECT 'fact_part_purchase', COUNT(*) FROM gold.fact_part_purchase
UNION ALL SELECT 'fact_recall_coverage', COUNT(*) FROM gold.fact_recall_coverage
UNION ALL SELECT 'fact_vehicle_inventory_daily', COUNT(*) FROM gold.fact_vehicle_inventory_daily;