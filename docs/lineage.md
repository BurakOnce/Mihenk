# Lineage

**GENERATED FILE — do not edit by hand.**

Produced by `tools/generate_docs.py`. The edges are derived from what the
code actually reads and writes, not from a diagram someone drew:

| Hop | Derived from |
|---|---|
| source file → Bronze | `data/_manifest.json`, written by the generator |
| Bronze → Silver | `spark.table(...)` and `merge_into_silver(...)` calls in the Silver notebooks |
| Silver → Gold | `FROM silver.*` and `INSERT INTO gold.*` in the Gold load procedures |
| Gold → report page | **declared by hand** in `tools/generate_docs.py` — a .pbix carries no machine-readable link back to its tables |

So the first three hops cannot claim a dependency the code does not have,
or miss one it does. The fourth can, and is flagged here rather than
presented as if it were extracted.

Generated: 2026-09-13 09:15:35

**77 nodes, 231 edges.**

---

## Full lineage

```mermaid
flowchart LR
    subgraph SRC["Source systems"]
        direction TB
        crm_customer(["crm<br/>customer<br/><i>json</i>"])
        dms_customer(["dms<br/>customer<br/><i>csv</i>"])
        dms_dealer(["dms<br/>dealer<br/><i>csv</i>"])
        dms_employee(["dms<br/>employee<br/><i>csv</i>"])
        dms_model_trim(["dms<br/>model_trim<br/><i>csv</i>"])
        dms_sales_contract(["dms<br/>sales_contract<br/><i>csv</i>"])
        dms_vehicle_stock(["dms<br/>vehicle_stock<br/><i>csv</i>"])
        finance_budget(["finance<br/>budget<br/><i>xlsx</i>"])
        finance_fx_rate(["finance<br/>fx_rate<br/><i>xlsx</i>"])
        parts_part(["parts<br/>part<br/><i>csv</i>"])
        parts_purchase_order_line(["parts<br/>purchase_order_line<br/><i>csv</i>"])
        parts_supplier(["parts<br/>supplier<br/><i>csv</i>"])
        portal_recall_campaign(["portal<br/>recall_campaign<br/><i>json</i>"])
        portal_recall_coverage(["portal<br/>recall_coverage<br/><i>jsonl</i>"])
        portal_warranty_claim(["portal<br/>warranty_claim<br/><i>jsonl</i>"])
        workshop_repair_order(["workshop<br/>repair_order<br/><i>csv</i>"])
        workshop_repair_order_line(["workshop<br/>repair_order_line<br/><i>csv</i>"])
    end
    subgraph BRZ["Bronze — Lakehouse Delta"]
        direction TB
        bronze_crm_customer["crm_customer"]
        bronze_dms_customer["dms_customer"]
        bronze_dms_dealer["dms_dealer"]
        bronze_dms_employee["dms_employee"]
        bronze_dms_model_trim["dms_model_trim"]
        bronze_dms_sales_contract["dms_sales_contract"]
        bronze_dms_vehicle_stock["dms_vehicle_stock"]
        bronze_finance_budget["finance_budget"]
        bronze_finance_fx_rate["finance_fx_rate"]
        bronze_parts_part["parts_part"]
        bronze_parts_purchase_order_line["parts_purchase_order_line"]
        bronze_parts_supplier["parts_supplier"]
        bronze_portal_recall_campaign["portal_recall_campaign"]
        bronze_portal_recall_coverage["portal_recall_coverage"]
        bronze_portal_warranty_claim["portal_warranty_claim"]
        bronze_workshop_repair_order["workshop_repair_order"]
        bronze_workshop_repair_order_line["workshop_repair_order_line"]
    end
    subgraph SLV["Silver — Lakehouse Delta"]
        direction TB
        silver_budget["budget"]
        silver_customer["customer"]
        silver_customer_xref["customer_xref"]
        silver_dealer["dealer"]
        silver_purchase_order_line["purchase_order_line"]
        silver_recall_campaign["recall_campaign"]
        silver_recall_coverage["recall_coverage"]
        silver_ref_fx_rate["ref_fx_rate"]
        silver_repair_order["repair_order"]
        silver_repair_order_line["repair_order_line"]
        silver_sales_contract["sales_contract"]
        silver_supplier["supplier"]
        silver_vehicle["vehicle"]
        silver_warranty_claim["warranty_claim"]
    end
    subgraph CTL["Control — Warehouse"]
        direction TB
        ctl_dq_result["dq_result"]
        ctl_dq_rule["dq_rule"]
    end
    subgraph GLD["Gold — Warehouse star schema"]
        direction TB
        gold_agg_monthly_dealer_model_sale["agg_monthly_dealer_model_sale"]
        gold_agg_monthly_dealer_target["agg_monthly_dealer_target"]
        gold_agg_monthly_service_summary["agg_monthly_service_summary"]
        gold_dim_customer["dim_customer"]
        gold_dim_date["dim_date"]
        gold_dim_dealer["dim_dealer"]
        gold_dim_employee["dim_employee"]
        gold_dim_model_trim["dim_model_trim"]
        gold_dim_part["dim_part"]
        gold_dim_service_type["dim_service_type"]
        gold_dim_supplier["dim_supplier"]
        gold_dim_transaction_flag["dim_transaction_flag"]
        gold_dim_vehicle["dim_vehicle"]
        gold_fact_data_quality["fact_data_quality"]
        gold_fact_part_purchase["fact_part_purchase"]
        gold_fact_recall_coverage["fact_recall_coverage"]
        gold_fact_repair_order["fact_repair_order"]
        gold_fact_repair_order_line["fact_repair_order_line"]
        gold_fact_vehicle_inventory_daily["fact_vehicle_inventory_daily"]
        gold_fact_vehicle_sale["fact_vehicle_sale"]
        gold_ref_province["ref_province"]
        gold_ref_public_holiday["ref_public_holiday"]
    end
    subgraph RPT["Power BI"]
        direction TB
        report_Aftersales(["Aftersales"])
        report_Data_quality(["Data quality"])
        report_Procurement(["Procurement"])
        report_Sales(["Sales"])
        report_Warranty_and_recall(["Warranty and recall"])
    end
    bronze_crm_customer --> silver_customer
    bronze_crm_customer --> silver_customer_xref
    bronze_dms_customer --> silver_customer
    bronze_dms_customer --> silver_customer_xref
    bronze_dms_dealer --> gold_dim_dealer
    bronze_dms_employee --> gold_dim_employee
    bronze_dms_model_trim --> gold_dim_model_trim
    bronze_dms_sales_contract --> silver_budget
    bronze_dms_sales_contract --> silver_purchase_order_line
    bronze_dms_sales_contract --> silver_recall_campaign
    bronze_dms_sales_contract --> silver_recall_coverage
    bronze_dms_sales_contract --> silver_repair_order
    bronze_dms_sales_contract --> silver_repair_order_line
    bronze_dms_sales_contract --> silver_sales_contract
    bronze_dms_sales_contract --> silver_warranty_claim
    bronze_dms_vehicle_stock --> gold_dim_vehicle
    bronze_finance_budget --> silver_budget
    bronze_finance_budget --> silver_purchase_order_line
    bronze_finance_budget --> silver_recall_campaign
    bronze_finance_budget --> silver_recall_coverage
    bronze_finance_budget --> silver_repair_order
    bronze_finance_budget --> silver_repair_order_line
    bronze_finance_budget --> silver_sales_contract
    bronze_finance_budget --> silver_warranty_claim
    bronze_parts_part --> gold_dim_part
    bronze_parts_purchase_order_line --> silver_budget
    bronze_parts_purchase_order_line --> silver_purchase_order_line
    bronze_parts_purchase_order_line --> silver_recall_campaign
    bronze_parts_purchase_order_line --> silver_recall_coverage
    bronze_parts_purchase_order_line --> silver_repair_order
    bronze_parts_purchase_order_line --> silver_repair_order_line
    bronze_parts_purchase_order_line --> silver_sales_contract
    bronze_parts_purchase_order_line --> silver_warranty_claim
    bronze_portal_recall_campaign --> silver_budget
    bronze_portal_recall_campaign --> silver_purchase_order_line
    bronze_portal_recall_campaign --> silver_recall_campaign
    bronze_portal_recall_campaign --> silver_recall_coverage
    bronze_portal_recall_campaign --> silver_repair_order
    bronze_portal_recall_campaign --> silver_repair_order_line
    bronze_portal_recall_campaign --> silver_sales_contract
    bronze_portal_recall_campaign --> silver_warranty_claim
    bronze_portal_recall_coverage --> silver_budget
    bronze_portal_recall_coverage --> silver_purchase_order_line
    bronze_portal_recall_coverage --> silver_recall_campaign
    bronze_portal_recall_coverage --> silver_recall_coverage
    bronze_portal_recall_coverage --> silver_repair_order
    bronze_portal_recall_coverage --> silver_repair_order_line
    bronze_portal_recall_coverage --> silver_sales_contract
    bronze_portal_recall_coverage --> silver_warranty_claim
    bronze_portal_warranty_claim --> silver_budget
    bronze_portal_warranty_claim --> silver_purchase_order_line
    bronze_portal_warranty_claim --> silver_recall_campaign
    bronze_portal_warranty_claim --> silver_recall_coverage
    bronze_portal_warranty_claim --> silver_repair_order
    bronze_portal_warranty_claim --> silver_repair_order_line
    bronze_portal_warranty_claim --> silver_sales_contract
    bronze_portal_warranty_claim --> silver_warranty_claim
    bronze_workshop_repair_order --> silver_budget
    bronze_workshop_repair_order --> silver_purchase_order_line
    bronze_workshop_repair_order --> silver_recall_campaign
    bronze_workshop_repair_order --> silver_recall_coverage
    bronze_workshop_repair_order --> silver_repair_order
    bronze_workshop_repair_order --> silver_repair_order_line
    bronze_workshop_repair_order --> silver_sales_contract
    bronze_workshop_repair_order --> silver_warranty_claim
    bronze_workshop_repair_order_line --> silver_budget
    bronze_workshop_repair_order_line --> silver_purchase_order_line
    bronze_workshop_repair_order_line --> silver_recall_campaign
    bronze_workshop_repair_order_line --> silver_recall_coverage
    bronze_workshop_repair_order_line --> silver_repair_order
    bronze_workshop_repair_order_line --> silver_repair_order_line
    bronze_workshop_repair_order_line --> silver_sales_contract
    bronze_workshop_repair_order_line --> silver_warranty_claim
    crm_customer --> bronze_crm_customer
    ctl_dq_result --> gold_fact_data_quality
    ctl_dq_rule --> gold_fact_data_quality
    dms_customer --> bronze_dms_customer
    dms_dealer --> bronze_dms_dealer
    dms_employee --> bronze_dms_employee
    dms_model_trim --> bronze_dms_model_trim
    dms_sales_contract --> bronze_dms_sales_contract
    dms_vehicle_stock --> bronze_dms_vehicle_stock
    finance_budget --> bronze_finance_budget
    finance_fx_rate --> bronze_finance_fx_rate
    gold_agg_monthly_dealer_model_sale --> gold_agg_monthly_dealer_model_sale
    gold_agg_monthly_dealer_model_sale --> report_Sales
    gold_agg_monthly_dealer_target --> gold_agg_monthly_dealer_target
    gold_agg_monthly_dealer_target --> report_Sales
    gold_agg_monthly_service_summary --> gold_agg_monthly_service_summary
    gold_agg_monthly_service_summary --> report_Aftersales
    gold_dim_customer --> gold_dim_customer
    gold_dim_customer --> gold_dim_part
    gold_dim_customer --> gold_dim_vehicle
    gold_dim_customer --> gold_fact_repair_order
    gold_dim_customer --> gold_fact_repair_order_line
    gold_dim_customer --> gold_fact_vehicle_sale
    gold_dim_date --> gold_agg_monthly_dealer_model_sale
    gold_dim_date --> gold_agg_monthly_dealer_target
    gold_dim_date --> gold_agg_monthly_service_summary
    gold_dim_date --> gold_dim_date
    gold_dim_date --> gold_fact_data_quality
    gold_dim_date --> gold_fact_part_purchase
    gold_dim_date --> gold_fact_recall_coverage
    gold_dim_date --> gold_fact_repair_order
    gold_dim_date --> gold_fact_repair_order_line
    gold_dim_date --> gold_fact_vehicle_inventory_daily
    gold_dim_date --> gold_fact_vehicle_sale
    gold_dim_date --> gold_ref_public_holiday
    gold_dim_dealer --> gold_agg_monthly_dealer_target
    gold_dim_dealer --> gold_agg_monthly_service_summary
    gold_dim_dealer --> gold_dim_dealer
    gold_dim_dealer --> gold_fact_recall_coverage
    gold_dim_dealer --> gold_fact_repair_order
    gold_dim_dealer --> gold_fact_repair_order_line
    gold_dim_dealer --> gold_fact_vehicle_inventory_daily
    gold_dim_dealer --> gold_fact_vehicle_sale
    gold_dim_employee --> gold_dim_employee
    gold_dim_employee --> gold_fact_repair_order
    gold_dim_employee --> gold_fact_repair_order_line
    gold_dim_employee --> gold_fact_vehicle_sale
    gold_dim_model_trim --> gold_dim_model_trim
    gold_dim_model_trim --> gold_fact_recall_coverage
    gold_dim_model_trim --> gold_fact_vehicle_inventory_daily
    gold_dim_model_trim --> gold_fact_vehicle_sale
    gold_dim_part --> gold_dim_customer
    gold_dim_part --> gold_dim_part
    gold_dim_part --> gold_dim_vehicle
    gold_dim_part --> gold_fact_part_purchase
    gold_dim_part --> gold_fact_repair_order_line
    gold_dim_service_type --> gold_dim_service_type
    gold_dim_service_type --> gold_fact_repair_order
    gold_dim_service_type --> gold_fact_repair_order_line
    gold_dim_supplier --> gold_dim_supplier
    gold_dim_supplier --> gold_fact_part_purchase
    gold_dim_transaction_flag --> gold_dim_transaction_flag
    gold_dim_transaction_flag --> gold_fact_repair_order
    gold_dim_transaction_flag --> gold_fact_vehicle_sale
    gold_dim_vehicle --> gold_dim_customer
    gold_dim_vehicle --> gold_dim_part
    gold_dim_vehicle --> gold_dim_vehicle
    gold_dim_vehicle --> gold_fact_recall_coverage
    gold_dim_vehicle --> gold_fact_repair_order
    gold_dim_vehicle --> gold_fact_repair_order_line
    gold_dim_vehicle --> gold_fact_vehicle_inventory_daily
    gold_dim_vehicle --> gold_fact_vehicle_sale
    gold_fact_data_quality --> gold_fact_data_quality
    gold_fact_data_quality --> report_Data_quality
    gold_fact_part_purchase --> gold_fact_part_purchase
    gold_fact_part_purchase --> report_Procurement
    gold_fact_recall_coverage --> gold_fact_recall_coverage
    gold_fact_recall_coverage --> report_Warranty_and_recall
    gold_fact_repair_order --> gold_agg_monthly_dealer_target
    gold_fact_repair_order --> gold_agg_monthly_service_summary
    gold_fact_repair_order --> gold_fact_repair_order
    gold_fact_repair_order --> report_Aftersales
    gold_fact_repair_order --> report_Warranty_and_recall
    gold_fact_repair_order_line --> gold_fact_repair_order_line
    gold_fact_repair_order_line --> report_Aftersales
    gold_fact_vehicle_inventory_daily --> gold_fact_vehicle_inventory_daily
    gold_fact_vehicle_inventory_daily --> report_Sales
    gold_fact_vehicle_sale --> gold_agg_monthly_dealer_model_sale
    gold_fact_vehicle_sale --> gold_agg_monthly_dealer_target
    gold_fact_vehicle_sale --> gold_fact_vehicle_sale
    gold_fact_vehicle_sale --> report_Sales
    gold_ref_province --> gold_dim_customer
    gold_ref_public_holiday --> gold_dim_date
    gold_ref_public_holiday --> gold_ref_public_holiday
    parts_part --> bronze_parts_part
    parts_purchase_order_line --> bronze_parts_purchase_order_line
    parts_supplier --> bronze_parts_supplier
    portal_recall_campaign --> bronze_portal_recall_campaign
    portal_recall_coverage --> bronze_portal_recall_coverage
    portal_warranty_claim --> bronze_portal_warranty_claim
    silver_budget --> gold_agg_monthly_dealer_target
    silver_customer --> gold_dim_customer
    silver_customer_xref --> gold_dim_vehicle
    silver_customer_xref --> silver_budget
    silver_customer_xref --> silver_customer
    silver_customer_xref --> silver_purchase_order_line
    silver_customer_xref --> silver_recall_campaign
    silver_customer_xref --> silver_recall_coverage
    silver_customer_xref --> silver_repair_order
    silver_customer_xref --> silver_repair_order_line
    silver_customer_xref --> silver_sales_contract
    silver_customer_xref --> silver_warranty_claim
    silver_dealer --> gold_dim_dealer
    silver_purchase_order_line --> gold_fact_part_purchase
    silver_recall_campaign --> gold_fact_recall_coverage
    silver_recall_coverage --> gold_dim_customer
    silver_recall_coverage --> gold_dim_part
    silver_recall_coverage --> gold_dim_vehicle
    silver_recall_coverage --> gold_fact_recall_coverage
    silver_ref_fx_rate --> silver_budget
    silver_ref_fx_rate --> silver_purchase_order_line
    silver_ref_fx_rate --> silver_recall_campaign
    silver_ref_fx_rate --> silver_recall_coverage
    silver_ref_fx_rate --> silver_repair_order
    silver_ref_fx_rate --> silver_repair_order_line
    silver_ref_fx_rate --> silver_sales_contract
    silver_ref_fx_rate --> silver_warranty_claim
    silver_repair_order --> gold_dim_customer
    silver_repair_order --> gold_dim_part
    silver_repair_order --> gold_dim_transaction_flag
    silver_repair_order --> gold_dim_vehicle
    silver_repair_order --> gold_fact_recall_coverage
    silver_repair_order --> gold_fact_repair_order
    silver_repair_order --> gold_fact_repair_order_line
    silver_repair_order_line --> gold_dim_customer
    silver_repair_order_line --> gold_dim_part
    silver_repair_order_line --> gold_dim_vehicle
    silver_repair_order_line --> gold_fact_repair_order
    silver_repair_order_line --> gold_fact_repair_order_line
    silver_sales_contract --> gold_dim_customer
    silver_sales_contract --> gold_dim_part
    silver_sales_contract --> gold_dim_transaction_flag
    silver_sales_contract --> gold_dim_vehicle
    silver_sales_contract --> gold_fact_vehicle_inventory_daily
    silver_sales_contract --> gold_fact_vehicle_sale
    silver_supplier --> gold_dim_supplier
    silver_vehicle --> gold_dim_vehicle
    silver_vehicle --> gold_fact_vehicle_inventory_daily
    silver_vehicle --> silver_budget
    silver_vehicle --> silver_purchase_order_line
    silver_vehicle --> silver_recall_campaign
    silver_vehicle --> silver_recall_coverage
    silver_vehicle --> silver_repair_order
    silver_vehicle --> silver_repair_order_line
    silver_vehicle --> silver_sales_contract
    silver_vehicle --> silver_warranty_claim
    workshop_repair_order --> bronze_workshop_repair_order
    workshop_repair_order_line --> bronze_workshop_repair_order_line
```

---

## Where each Gold table comes from

| Gold table | Reads from |
|---|---|
| `gold.agg_monthly_dealer_model_sale` | `gold.agg_monthly_dealer_model_sale`, `gold.dim_date`, `gold.fact_vehicle_sale` |
| `gold.agg_monthly_dealer_target` | `gold.agg_monthly_dealer_target`, `gold.dim_date`, `gold.dim_dealer`, `gold.fact_repair_order`, `gold.fact_vehicle_sale`, `silver.budget` |
| `gold.agg_monthly_service_summary` | `gold.agg_monthly_service_summary`, `gold.dim_date`, `gold.dim_dealer`, `gold.fact_repair_order` |
| `gold.dim_customer` | `gold.dim_customer`, `gold.dim_part`, `gold.dim_vehicle`, `gold.ref_province`, `silver.customer`, `silver.recall_coverage`, `silver.repair_order`, `silver.repair_order_line`, `silver.sales_contract` |
| `gold.dim_date` | `gold.dim_date`, `gold.ref_public_holiday` |
| `gold.dim_dealer` | `bronze.dms_dealer`, `gold.dim_dealer`, `silver.dealer` |
| `gold.dim_employee` | `bronze.dms_employee`, `gold.dim_employee` |
| `gold.dim_model_trim` | `bronze.dms_model_trim`, `gold.dim_model_trim` |
| `gold.dim_part` | `bronze.parts_part`, `gold.dim_customer`, `gold.dim_part`, `gold.dim_vehicle`, `silver.recall_coverage`, `silver.repair_order`, `silver.repair_order_line`, `silver.sales_contract` |
| `gold.dim_service_type` | `gold.dim_service_type` |
| `gold.dim_supplier` | `gold.dim_supplier`, `silver.supplier` |
| `gold.dim_transaction_flag` | `gold.dim_transaction_flag`, `silver.repair_order`, `silver.sales_contract` |
| `gold.dim_vehicle` | `bronze.dms_vehicle_stock`, `gold.dim_customer`, `gold.dim_part`, `gold.dim_vehicle`, `silver.customer_xref`, `silver.recall_coverage`, `silver.repair_order`, `silver.repair_order_line`, `silver.sales_contract`, `silver.vehicle` |
| `gold.fact_data_quality` | `ctl.dq_result`, `ctl.dq_rule`, `gold.dim_date`, `gold.fact_data_quality` |
| `gold.fact_part_purchase` | `gold.dim_date`, `gold.dim_part`, `gold.dim_supplier`, `gold.fact_part_purchase`, `silver.purchase_order_line` |
| `gold.fact_recall_coverage` | `gold.dim_date`, `gold.dim_dealer`, `gold.dim_model_trim`, `gold.dim_vehicle`, `gold.fact_recall_coverage`, `silver.recall_campaign`, `silver.recall_coverage`, `silver.repair_order` |
| `gold.fact_repair_order` | `gold.dim_customer`, `gold.dim_date`, `gold.dim_dealer`, `gold.dim_employee`, `gold.dim_service_type`, `gold.dim_transaction_flag`, `gold.dim_vehicle`, `gold.fact_repair_order`, `silver.repair_order`, `silver.repair_order_line` |
| `gold.fact_repair_order_line` | `gold.dim_customer`, `gold.dim_date`, `gold.dim_dealer`, `gold.dim_employee`, `gold.dim_part`, `gold.dim_service_type`, `gold.dim_vehicle`, `gold.fact_repair_order_line`, `silver.repair_order`, `silver.repair_order_line` |
| `gold.fact_vehicle_inventory_daily` | `gold.dim_date`, `gold.dim_dealer`, `gold.dim_model_trim`, `gold.dim_vehicle`, `gold.fact_vehicle_inventory_daily`, `silver.sales_contract`, `silver.vehicle` |
| `gold.fact_vehicle_sale` | `gold.dim_customer`, `gold.dim_date`, `gold.dim_dealer`, `gold.dim_employee`, `gold.dim_model_trim`, `gold.dim_transaction_flag`, `gold.dim_vehicle`, `gold.fact_vehicle_sale`, `silver.sales_contract` |
| `gold.ref_province` | — |
| `gold.ref_public_holiday` | `gold.dim_date`, `gold.ref_public_holiday` |

---

## Impact analysis — what breaks if a source changes

Read downwards: change the source on the left and everything to the right
of it needs re-testing.

| Source | Bronze | Silver | Gold |
|---|---|---|---|
| `crm:customer` | `bronze.crm_customer` | `silver.budget`, `silver.customer_xref`, `silver.customer`, `silver.purchase_order_line`, `silver.recall_campaign`, `silver.recall_coverage`, `silver.repair_order_line`, `silver.repair_order`, `silver.sales_contract`, `silver.warranty_claim` | `gold.agg_monthly_dealer_model_sale`, `gold.agg_monthly_dealer_target`, `gold.agg_monthly_service_summary`, `gold.dim_customer`, `gold.dim_part`, `gold.dim_transaction_flag`, `gold.dim_vehicle`, `gold.fact_part_purchase`, `gold.fact_recall_coverage`, `gold.fact_repair_order_line`, `gold.fact_repair_order`, `gold.fact_vehicle_inventory_daily`, `gold.fact_vehicle_sale` |
| `dms:customer` | `bronze.dms_customer` | `silver.budget`, `silver.customer_xref`, `silver.customer`, `silver.purchase_order_line`, `silver.recall_campaign`, `silver.recall_coverage`, `silver.repair_order_line`, `silver.repair_order`, `silver.sales_contract`, `silver.warranty_claim` | `gold.agg_monthly_dealer_model_sale`, `gold.agg_monthly_dealer_target`, `gold.agg_monthly_service_summary`, `gold.dim_customer`, `gold.dim_part`, `gold.dim_transaction_flag`, `gold.dim_vehicle`, `gold.fact_part_purchase`, `gold.fact_recall_coverage`, `gold.fact_repair_order_line`, `gold.fact_repair_order`, `gold.fact_vehicle_inventory_daily`, `gold.fact_vehicle_sale` |
| `dms:dealer` | `bronze.dms_dealer` | — | `gold.agg_monthly_dealer_model_sale`, `gold.agg_monthly_dealer_target`, `gold.agg_monthly_service_summary`, `gold.dim_dealer`, `gold.fact_recall_coverage`, `gold.fact_repair_order_line`, `gold.fact_repair_order`, `gold.fact_vehicle_inventory_daily`, `gold.fact_vehicle_sale` |
| `dms:employee` | `bronze.dms_employee` | — | `gold.agg_monthly_dealer_model_sale`, `gold.agg_monthly_dealer_target`, `gold.agg_monthly_service_summary`, `gold.dim_employee`, `gold.fact_repair_order_line`, `gold.fact_repair_order`, `gold.fact_vehicle_sale` |
| `dms:model_trim` | `bronze.dms_model_trim` | — | `gold.agg_monthly_dealer_model_sale`, `gold.agg_monthly_dealer_target`, `gold.dim_model_trim`, `gold.fact_recall_coverage`, `gold.fact_vehicle_inventory_daily`, `gold.fact_vehicle_sale` |
| `dms:sales_contract` | `bronze.dms_sales_contract` | `silver.budget`, `silver.purchase_order_line`, `silver.recall_campaign`, `silver.recall_coverage`, `silver.repair_order_line`, `silver.repair_order`, `silver.sales_contract`, `silver.warranty_claim` | `gold.agg_monthly_dealer_model_sale`, `gold.agg_monthly_dealer_target`, `gold.agg_monthly_service_summary`, `gold.dim_customer`, `gold.dim_part`, `gold.dim_transaction_flag`, `gold.dim_vehicle`, `gold.fact_part_purchase`, `gold.fact_recall_coverage`, `gold.fact_repair_order_line`, `gold.fact_repair_order`, `gold.fact_vehicle_inventory_daily`, `gold.fact_vehicle_sale` |
| `dms:vehicle_stock` | `bronze.dms_vehicle_stock` | — | `gold.agg_monthly_dealer_model_sale`, `gold.agg_monthly_dealer_target`, `gold.agg_monthly_service_summary`, `gold.dim_customer`, `gold.dim_part`, `gold.dim_vehicle`, `gold.fact_part_purchase`, `gold.fact_recall_coverage`, `gold.fact_repair_order_line`, `gold.fact_repair_order`, `gold.fact_vehicle_inventory_daily`, `gold.fact_vehicle_sale` |
| `finance:budget` | `bronze.finance_budget` | `silver.budget`, `silver.purchase_order_line`, `silver.recall_campaign`, `silver.recall_coverage`, `silver.repair_order_line`, `silver.repair_order`, `silver.sales_contract`, `silver.warranty_claim` | `gold.agg_monthly_dealer_model_sale`, `gold.agg_monthly_dealer_target`, `gold.agg_monthly_service_summary`, `gold.dim_customer`, `gold.dim_part`, `gold.dim_transaction_flag`, `gold.dim_vehicle`, `gold.fact_part_purchase`, `gold.fact_recall_coverage`, `gold.fact_repair_order_line`, `gold.fact_repair_order`, `gold.fact_vehicle_inventory_daily`, `gold.fact_vehicle_sale` |
| `finance:fx_rate` | `bronze.finance_fx_rate` | — | — |
| `parts:part` | `bronze.parts_part` | — | `gold.agg_monthly_dealer_model_sale`, `gold.agg_monthly_dealer_target`, `gold.agg_monthly_service_summary`, `gold.dim_customer`, `gold.dim_part`, `gold.dim_vehicle`, `gold.fact_part_purchase`, `gold.fact_recall_coverage`, `gold.fact_repair_order_line`, `gold.fact_repair_order`, `gold.fact_vehicle_inventory_daily`, `gold.fact_vehicle_sale` |
| `parts:purchase_order_line` | `bronze.parts_purchase_order_line` | `silver.budget`, `silver.purchase_order_line`, `silver.recall_campaign`, `silver.recall_coverage`, `silver.repair_order_line`, `silver.repair_order`, `silver.sales_contract`, `silver.warranty_claim` | `gold.agg_monthly_dealer_model_sale`, `gold.agg_monthly_dealer_target`, `gold.agg_monthly_service_summary`, `gold.dim_customer`, `gold.dim_part`, `gold.dim_transaction_flag`, `gold.dim_vehicle`, `gold.fact_part_purchase`, `gold.fact_recall_coverage`, `gold.fact_repair_order_line`, `gold.fact_repair_order`, `gold.fact_vehicle_inventory_daily`, `gold.fact_vehicle_sale` |
| `parts:supplier` | `bronze.parts_supplier` | — | — |
| `portal:recall_campaign` | `bronze.portal_recall_campaign` | `silver.budget`, `silver.purchase_order_line`, `silver.recall_campaign`, `silver.recall_coverage`, `silver.repair_order_line`, `silver.repair_order`, `silver.sales_contract`, `silver.warranty_claim` | `gold.agg_monthly_dealer_model_sale`, `gold.agg_monthly_dealer_target`, `gold.agg_monthly_service_summary`, `gold.dim_customer`, `gold.dim_part`, `gold.dim_transaction_flag`, `gold.dim_vehicle`, `gold.fact_part_purchase`, `gold.fact_recall_coverage`, `gold.fact_repair_order_line`, `gold.fact_repair_order`, `gold.fact_vehicle_inventory_daily`, `gold.fact_vehicle_sale` |
| `portal:recall_coverage` | `bronze.portal_recall_coverage` | `silver.budget`, `silver.purchase_order_line`, `silver.recall_campaign`, `silver.recall_coverage`, `silver.repair_order_line`, `silver.repair_order`, `silver.sales_contract`, `silver.warranty_claim` | `gold.agg_monthly_dealer_model_sale`, `gold.agg_monthly_dealer_target`, `gold.agg_monthly_service_summary`, `gold.dim_customer`, `gold.dim_part`, `gold.dim_transaction_flag`, `gold.dim_vehicle`, `gold.fact_part_purchase`, `gold.fact_recall_coverage`, `gold.fact_repair_order_line`, `gold.fact_repair_order`, `gold.fact_vehicle_inventory_daily`, `gold.fact_vehicle_sale` |
| `portal:warranty_claim` | `bronze.portal_warranty_claim` | `silver.budget`, `silver.purchase_order_line`, `silver.recall_campaign`, `silver.recall_coverage`, `silver.repair_order_line`, `silver.repair_order`, `silver.sales_contract`, `silver.warranty_claim` | `gold.agg_monthly_dealer_model_sale`, `gold.agg_monthly_dealer_target`, `gold.agg_monthly_service_summary`, `gold.dim_customer`, `gold.dim_part`, `gold.dim_transaction_flag`, `gold.dim_vehicle`, `gold.fact_part_purchase`, `gold.fact_recall_coverage`, `gold.fact_repair_order_line`, `gold.fact_repair_order`, `gold.fact_vehicle_inventory_daily`, `gold.fact_vehicle_sale` |
| `workshop:repair_order` | `bronze.workshop_repair_order` | `silver.budget`, `silver.purchase_order_line`, `silver.recall_campaign`, `silver.recall_coverage`, `silver.repair_order_line`, `silver.repair_order`, `silver.sales_contract`, `silver.warranty_claim` | `gold.agg_monthly_dealer_model_sale`, `gold.agg_monthly_dealer_target`, `gold.agg_monthly_service_summary`, `gold.dim_customer`, `gold.dim_part`, `gold.dim_transaction_flag`, `gold.dim_vehicle`, `gold.fact_part_purchase`, `gold.fact_recall_coverage`, `gold.fact_repair_order_line`, `gold.fact_repair_order`, `gold.fact_vehicle_inventory_daily`, `gold.fact_vehicle_sale` |
| `workshop:repair_order_line` | `bronze.workshop_repair_order_line` | `silver.budget`, `silver.purchase_order_line`, `silver.recall_campaign`, `silver.recall_coverage`, `silver.repair_order_line`, `silver.repair_order`, `silver.sales_contract`, `silver.warranty_claim` | `gold.agg_monthly_dealer_model_sale`, `gold.agg_monthly_dealer_target`, `gold.agg_monthly_service_summary`, `gold.dim_customer`, `gold.dim_part`, `gold.dim_transaction_flag`, `gold.dim_vehicle`, `gold.fact_part_purchase`, `gold.fact_recall_coverage`, `gold.fact_repair_order_line`, `gold.fact_repair_order`, `gold.fact_vehicle_inventory_daily`, `gold.fact_vehicle_sale` |
