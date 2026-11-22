# Inventory: Schema Reference

- Document ID: INV-02
- Source: generated from the data dictionary in `docs/03_database_design.md`; the two documents cannot disagree.
- Dialect: PostgreSQL 16. All text values are English. Currency SAR. Revenue excludes 15 percent VAT.

This reference describes the stock, history, purchasing and supplier data used by the Inventory subgraph. Use `v_inventory_status` for current stock questions and `v_weekly_product_demand` as the input for forecasts.

## Objects the SQL Tool May Use

Tables: `branches`, `product_categories`, `suppliers`, `products`, `calendar`, `inventory_levels`, `inventory_snapshots`, `purchase_orders`, `purchase_order_items`, `stock_adjustments`.

Views: `v_inventory_status`, `v_weekly_product_demand`, `v_sales_detail`.

## Reading Rules

- Current stock lives in `inventory_levels` (one row per location and product, snapshot date 2026-10-31). Weekly history lives in `inventory_snapshots` (Saturday end-of-week).
- Use `quantity_available` (on hand minus reserved) for stock status and reorder decisions; `quantity_on_hand` is the physical count.
- All 120 SKUs are held at `RYD-DC`; each store holds about 90 SKUs. A SKU missing at a store means it is not stocked there, not that it is out of stock.
- `v_weekly_product_demand` only contains weeks with at least one completed sale. Missing weeks are zero sales and must be filled before forecasting.
- `inventory_snapshots.stockout_days` shows weeks where demand was censored by a stockout; adjust history before forecasting.
- Supplier lead time is `suppliers.lead_time_days`; purchase order delivery performance compares `actual_delivery_date` with `expected_delivery_date` for Received or Partially Received orders.
- Stock value is at cost: `quantity_on_hand * unit_cost`.
- The data ends on 2026-10-31 and the first forecast week starts on 2026-11-01. Never use the system clock.

## Join Map

- `inventory_levels.branch_id` = `branches.branch_id`; `inventory_levels.product_id` = `products.product_id`.
- `inventory_snapshots` joins to `branches` and `products` the same way; its series key is (`product_id`, `branch_id`, `snapshot_date`).
- `products.supplier_id` = `suppliers.supplier_id`; `products.category_id` = `product_categories.category_id`.
- `purchase_orders.supplier_id` = `suppliers.supplier_id`; `purchase_order_items.po_id` = `purchase_orders.po_id`; `purchase_order_items.product_id` = `products.product_id`.
- `purchase_orders.destination_branch_id` = `branches.branch_id` (mostly the Distribution Center).
- `stock_adjustments.branch_id` and `product_id` join to `branches` and `products`.
- `v_weekly_product_demand.week_start_date` = `calendar.week_start_date` when season flags are needed.

## Value Lists

- `stock_status`: Out of Stock, Critical, Reorder Now, Overstock, Healthy (evaluated in this order).
- `lifecycle_status`: New, Active, Declining, Discontinued.
- Purchase order `status`: Received, Partially Received, In Transit, Open, Cancelled.
- Adjustment `reason`: Damage, Expiry, Shrinkage, Count Correction, Display Sample.
- Product line codes: ELEC, APPL, FASH, GROC, BEAU, SPRT, KIDS, HOME. SKU format: line code, a dash and four digits (for example ELEC-0001).
- Branch codes: RYD-OLY, JED-THL, RYD-MLQ, DMM-FSL, KHB-COR, MED-QBA, JED-OBH, ABH-CTY, RYD-DC.
- `calendar.season`: Ramadan, Eid al-Fitr, Hajj and Eid al-Adha, White Friday, National Day, Founding Day, Back to School, Summer, Winter, Regular.

## View `v_inventory_status`

Current stock per location and product with product, category and supplier attributes and a computed stock_status.

- stock_value = quantity_on_hand x unit_cost (SAR, at cost).
- stock_status is evaluated in this order: Out of Stock, Critical, Reorder Now, Overstock, Healthy.

| Column | Type | Meaning |
|---|---|---|
| `branch_id` | integer | Primary key. |
| `branch_code` | text | Short code of the location. |
| `branch_name` | text | Display name of the location. |
| `product_id` | integer | Primary key. |
| `sku` | text | Unique stock keeping unit such as ELEC-0001. |
| `product_name` | text | Product display name. |
| `category_name` | text | Product line name. |
| `subcategory` | text | Sub-range inside the product line, for example 'Camping Gear'. |
| `brand` | text | Brand name. |
| `lifecycle_status` | text | New, Active, Declining or Discontinued. |
| `supplier_id` | integer | Primary key. |
| `supplier_name` | text | Name of the supplier of the product. |
| `lead_time_days` | integer | Contractual lead time of the supplier in days. |
| `quantity_on_hand` | integer | Physical units in stock. |
| `quantity_reserved` | integer | Units reserved for open orders or transfers. |
| `quantity_available` | integer | quantity_on_hand - quantity_reserved (stored generated column). |
| `reorder_point` | integer | Available quantity at or below which a replenishment order is triggered. |
| `safety_stock` | integer | Buffer quantity protecting against demand and lead-time variability. |
| `max_stock_level` | integer | Upper stock limit; above it the item is overstocked. |
| `reorder_quantity` | integer | Standard replenishment quantity. |
| `last_restock_date` | date | Date of the latest goods receipt. |
| `unit_cost` | numeric | Current standard landed cost per unit in SAR. |
| `unit_price` | numeric | Current list selling price per unit in SAR, excluding VAT. Always above unit_cost. |
| `stock_value` | numeric | quantity_on_hand multiplied by unit_cost (SAR, at cost). |
| `stock_status` | text | Computed: Out of Stock, Critical, Reorder Now, Overstock or Healthy. |

## View `v_weekly_product_demand`

Weekly units sold per location and product from Completed orders, with the Sunday week start and Saturday week end. Direct input for forecasting.

- Only weeks with at least one completed sale appear; forecasting code must fill missing weeks with zero units.
- Weeks start on Sunday and end on Saturday; promo_units counts units on orders that carried a promotion.

| Column | Type | Meaning |
|---|---|---|
| `week_start_date` | date | Sunday that starts the retail week. |
| `week_end_date` | date | Saturday that ends the retail week. |
| `branch_id` | integer | Primary key. |
| `branch_code` | text | Short code of the location. |
| `product_id` | integer | Primary key. |
| `sku` | text | Unique stock keeping unit such as ELEC-0001. |
| `category_id` | integer | Primary key. |
| `units_sold` | bigint | Units sold in the week from Completed orders. |
| `orders_count` | bigint | Distinct orders in the week for the series. |
| `net_revenue` | numeric | Net revenue of the week for the series, excluding VAT. |
| `avg_selling_price` | numeric | net_revenue divided by units_sold. |
| `promo_units` | bigint | Units sold on orders that carried a promotion. |
| `is_ramadan_week` | boolean | True when any day of the week is in Ramadan. |
| `is_eid_week` | boolean | True when any day of the week is in an Eid season. |

## View `v_sales_detail`

One row per order line with order, branch, customer (non-PII), product and category attributes already joined. Preferred starting point for almost every sales question.

- One row per order line; all order statuses are included, so every revenue query must filter status = 'Completed'.
- Customer columns are left-joined: they are NULL for anonymous in-store orders.
- Contact details (email, phone) and full names are intentionally not exposed by the view.

| Column | Type | Meaning |
|---|---|---|
| `order_id` | bigint | Primary key. |
| `order_number` | text | Unique business number such as SO-2025-0004512. |
| `order_timestamp` | timestamp | Local Riyadh time (UTC+3) when the order was placed. |
| `order_date` | date | Date part of order_timestamp. |
| `year` | integer | Calendar year of order_date. |
| `month` | integer | Calendar month number 1 to 12 of order_date. |
| `season` | text | Commercial season the promotion belongs to. |
| `channel` | text | In-Store, Online, Mobile App or B2B. |
| `status` | text | Order status; filter status = 'Completed' for revenue. |
| `payment_method` | text | Mada, Credit Card, Apple Pay, STC Pay, Cash, Cash on Delivery, Buy Now Pay Later or Bank Transfer. |
| `promotion_id` | integer | Primary key. |
| `branch_id` | integer | Primary key. |
| `branch_code` | text | Short code of the location. |
| `branch_name` | text | Display name of the location. |
| `branch_city` | text | City of the selling branch. |
| `branch_region` | text | Region of the selling branch. |
| `customer_id` | integer | NULL for anonymous in-store orders. |
| `customer_code` | text | Customer code (NULL for anonymous orders). |
| `customer_type` | text | Individual or Business (NULL for anonymous orders). |
| `customer_segment` | text | Premium, Core or Occasional (NULL for anonymous orders). |
| `loyalty_tier` | text | NULL for anonymous orders; otherwise None, Silver, Gold or Platinum. |
| `customer_city` | text | Home city of the customer (NULL for anonymous orders). |
| `customer_region` | text | Region of the customer city (NULL for anonymous orders). |
| `product_id` | integer | Primary key. |
| `sku` | text | Unique stock keeping unit such as ELEC-0001. |
| `product_name` | text | Product display name. |
| `category_id` | integer | Primary key. |
| `category_name` | text | Product line name. |
| `subcategory` | text | Sub-range inside the product line, for example 'Camping Gear'. |
| `brand` | text | Brand name. |
| `supplier_id` | integer | Primary key. |
| `quantity` | integer | Units sold on the line. |
| `unit_price` | numeric | Current list selling price per unit in SAR, excluding VAT. Always above unit_cost. |
| `unit_cost` | numeric | Current standard landed cost per unit in SAR. |
| `discount_pct` | numeric | Headline discount percentage. |
| `line_total` | numeric | Net line revenue, excluding VAT. The revenue column. |
| `line_cost` | numeric | Cost of goods on the line. |
| `line_margin` | numeric | line_total minus line_cost. |

## Table `branches`

One row per business location: eight retail stores plus the Riyadh Distribution Center (which also fulfils online and B2B orders).

- Group: Reference. Primary key: `branch_id`.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `branch_id` | INTEGER | no | Primary key. |
| `branch_code` | VARCHAR(10) | no | Unique short code such as RYD-OLY, JED-THL, DMM-FSL, RYD-DC. |
| `branch_name` | VARCHAR(80) | no | Display name, for example 'Riyadh Olaya Flagship'. |
| `city` | VARCHAR(40) | no | City: Riyadh, Jeddah, Dammam, Al Khobar, Madinah or Abha. |
| `region` | VARCHAR(20) | no | Macro region: Central, Western, Eastern or Southern. |
| `branch_type` | VARCHAR(30) | no | Flagship Store, Standard Store, Express Store or Distribution Center. |
| `opening_date` | DATE | no | Date the location opened (all earlier than 2024-01-01). |
| `area_sqm` | INTEGER | no | Floor area in square meters. |
| `staff_count` | INTEGER | no | Number of employees at the location. |
| `manager_name` | VARCHAR(80) | no | Current branch manager; matches the employee records in the knowledge base. |
| `fulfills_online` | BOOLEAN | no | True only for the Distribution Center. |
| `opening_hours` | VARCHAR(20) | yes | Daily opening hours. |
| `is_active` | BOOLEAN | no | True for all nine locations. |

## Table `product_categories`

The eight product lines of the company. Product line and category mean the same thing.

- Group: Reference. Primary key: `category_id`.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `category_id` | INTEGER | no | Primary key. |
| `category_code` | VARCHAR(10) | no | ELEC, APPL, FASH, GROC, BEAU, SPRT, KIDS or HOME. |
| `category_name` | VARCHAR(60) | no | Consumer Electronics, Home Appliances, Fashion and Apparel, Grocery and Gourmet, Beauty and Fragrance, Sports and Outdoor, Kids and School, Home Decor and Furnishing. |
| `department` | VARCHAR(40) | no | Technology, Lifestyle, Consumables or Family and Leisure. |
| `target_margin_pct` | NUMERIC(5,2) | no | Target gross margin percentage for the line. |
| `peak_season` | VARCHAR(60) | yes | Main commercial season(s) in which the line peaks. |
| `description` | TEXT | yes | Short description of the line. |

## Table `suppliers`

Sixteen contracted suppliers, two per product line. Values match the supplier contracts in the knowledge base.

- Group: Reference. Primary key: `supplier_id`.
- Foreign keys: `primary_category_id -> product_categories.category_id`.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `supplier_id` | INTEGER | no | Primary key. |
| `supplier_code` | VARCHAR(10) | no | SUP-01 to SUP-16. |
| `supplier_name` | VARCHAR(100) | no | Legal name of the supplier. |
| `country` | VARCHAR(40) | no | Country of the supplier. |
| `city` | VARCHAR(40) | yes | City of the supplier. |
| `primary_category_id` | INTEGER | no | Main product line supplied. |
| `lead_time_days` | INTEGER | no | Contractual standard lead time from order to delivery at the Distribution Center, from 4 to 45 days. |
| `min_order_qty` | INTEGER | no | Minimum order quantity in units per purchase order line. |
| `payment_terms_days` | INTEGER | no | Payment terms in days from invoice date. |
| `on_time_delivery_pct` | NUMERIC(5,2) | no | Contractual or measured on-time delivery percentage. |
| `quality_rating` | NUMERIC(2,1) | no | Quality rating from 1.0 to 5.0. |
| `billing_currency` | VARCHAR(3) | no | Currency used on supplier invoices: SAR, USD, EUR or AED. |
| `contract_number` | VARCHAR(20) | no | Contract number, for example SC-2023-001. |
| `contract_start_date` | DATE | no | Date of the contract. |
| `contract_end_date` | DATE | no | End of the current contract term (after automatic renewals) as of 2026-10-31. |
| `is_active` | BOOLEAN | no | True for all suppliers. |

## Table `products`

Product master with 120 SKUs, fifteen per product line. Prices exclude VAT.

- Group: Reference. Primary key: `product_id`.
- Foreign keys: `category_id -> product_categories.category_id`; `supplier_id -> suppliers.supplier_id`.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `product_id` | INTEGER | no | Primary key. |
| `sku` | VARCHAR(12) | no | Unique stock keeping unit such as ELEC-0001. |
| `product_name` | VARCHAR(120) | no | Product display name. |
| `category_id` | INTEGER | no | Product line. |
| `subcategory` | VARCHAR(60) | no | Sub-range inside the product line, for example 'Camping Gear'. |
| `brand` | VARCHAR(60) | no | Brand name. |
| `supplier_id` | INTEGER | no | Contracted supplier. |
| `unit_cost` | NUMERIC(10,2) | no | Current standard landed cost per unit in SAR. |
| `unit_price` | NUMERIC(10,2) | no | Current list selling price per unit in SAR, excluding VAT. Always above unit_cost. |
| `unit_of_measure` | VARCHAR(10) | no | Each, Pack, Box, Kg or Set. |
| `shelf_life_days` | INTEGER | yes | Shelf life in days for perishable or dated items; NULL for non-perishable items. |
| `is_seasonal` | BOOLEAN | no | True when demand is concentrated in a specific season. |
| `peak_season` | VARCHAR(40) | yes | Commercial season in which demand peaks. |
| `lifecycle_status` | VARCHAR(15) | no | New, Active, Declining or Discontinued. |
| `launch_date` | DATE | no | Date the SKU was first sold; at least three SKUs launched in 2026. |
| `discontinued_date` | DATE | yes | Date the SKU was discontinued, NULL otherwise. |
| `weight_kg` | NUMERIC(8,2) | yes | Unit weight in kilograms. |
| `origin_country` | VARCHAR(40) | yes | Country of origin. |

## Table `calendar`

One row for every day from 2024-01-01 to 2026-10-31 (1,035 rows) with Saudi retail seasons and event flags.

- Group: Reference. Primary key: `date_key`.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `date_key` | DATE | no | Primary key; the calendar date. |
| `year` | SMALLINT | no | Calendar year. |
| `quarter` | SMALLINT | no | Quarter 1 to 4. |
| `month` | SMALLINT | no | Month 1 to 12. |
| `month_name` | VARCHAR(10) | no | January to December. |
| `week_start_date` | DATE | no | Sunday that starts the retail week containing the date. |
| `week_of_year` | SMALLINT | no | Retail week number (weeks start on Sunday). |
| `day_of_month` | SMALLINT | no | Day number 1 to 31. |
| `day_of_week` | SMALLINT | no | 0 = Sunday, 1 = Monday, ..., 5 = Friday, 6 = Saturday (PostgreSQL DOW convention). |
| `day_name` | VARCHAR(10) | no | Sunday to Saturday. |
| `is_weekend` | BOOLEAN | no | True for Friday and Saturday (the Saudi weekend). |
| `is_holiday` | BOOLEAN | no | True on official public holidays. |
| `holiday_name` | VARCHAR(40) | yes | Founding Day, Eid al-Fitr Holiday, Arafat Day, Eid al-Adha Holiday or National Day. |
| `season` | VARCHAR(30) | no | Single commercial season: Ramadan, Eid al-Fitr, Hajj and Eid al-Adha, White Friday, National Day, Founding Day, Back to School, Summer, Winter or Regular. |
| `climate_season` | VARCHAR(10) | no | Winter (Dec-Feb), Spring (Mar-May), Summer (Jun-Sep) or Autumn (Oct-Nov). |
| `is_ramadan` | BOOLEAN | no | True during Ramadan. |
| `is_eid` | BOOLEAN | no | True during the Eid al-Fitr and Eid al-Adha seasons. |
| `is_payday` | BOOLEAN | no | True from the 25th to the 28th of each month (salary period). |

## Table `inventory_levels`

Current stock position per location and product as of the reference date 2026-10-31 (about 840 rows: all 120 SKUs at the Distribution Center, about 90 SKUs at each store).

- Group: Inventory. Primary key: `inventory_id`.
- Foreign keys: `branch_id -> branches.branch_id`; `product_id -> products.product_id`.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `inventory_id` | INTEGER | no | Primary key. |
| `branch_id` | INTEGER | no | Location holding the stock. |
| `product_id` | INTEGER | no | Product. |
| `quantity_on_hand` | INTEGER | no | Physical units in stock. |
| `quantity_reserved` | INTEGER | no | Units reserved for open orders or transfers. |
| `quantity_available` | INTEGER | no | quantity_on_hand - quantity_reserved (stored generated column). |
| `reorder_point` | INTEGER | no | Available quantity at or below which a replenishment order is triggered. |
| `safety_stock` | INTEGER | no | Buffer quantity protecting against demand and lead-time variability. |
| `max_stock_level` | INTEGER | no | Upper stock limit; above it the item is overstocked. |
| `reorder_quantity` | INTEGER | no | Standard replenishment quantity. |
| `last_restock_date` | DATE | yes | Date of the latest goods receipt. |
| `last_count_date` | DATE | yes | Date of the latest cycle count. |
| `snapshot_date` | DATE | no | Date the position was captured: 2026-10-31 for every row. |

## Table `inventory_snapshots`

Weekly end-of-week (Saturday) stock history per location and product, from 2024-01-06 to 2026-10-31 (148 weekly snapshots, about 120,000 rows).

- Group: Inventory. Primary key: `snapshot_id`.
- Foreign keys: `branch_id -> branches.branch_id`; `product_id -> products.product_id`.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `snapshot_id` | BIGINT | no | Primary key. |
| `snapshot_date` | DATE | no | Saturday that closes the retail week. |
| `branch_id` | INTEGER | no | Location. |
| `product_id` | INTEGER | no | Product. |
| `quantity_on_hand` | INTEGER | no | Units on hand at the end of the day on snapshot_date. |
| `stockout_days` | SMALLINT | no | Number of days in the week (0 to 7) with zero stock; used to detect censored demand. |

## Table `purchase_orders`

Purchase order headers placed with suppliers (about 5,000 rows).

- Group: Inventory. Primary key: `po_id`.
- Foreign keys: `supplier_id -> suppliers.supplier_id`; `destination_branch_id -> branches.branch_id`.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `po_id` | INTEGER | no | Primary key. |
| `po_number` | VARCHAR(20) | no | Unique number such as PO-2025-00123. |
| `supplier_id` | INTEGER | no | Supplier. |
| `destination_branch_id` | INTEGER | no | Receiving location (mostly the Distribution Center). |
| `order_date` | DATE | no | Date the PO was placed. |
| `expected_delivery_date` | DATE | no | order_date plus the supplier's contractual lead time. |
| `actual_delivery_date` | DATE | yes | Date goods were received; NULL for Open or In Transit POs. |
| `status` | VARCHAR(20) | no | Received, Partially Received, In Transit, Open or Cancelled. |
| `total_amount` | NUMERIC(14,2) | no | Total PO value in SAR. |
| `currency` | VARCHAR(3) | no | Always SAR (converted at order date). |

## Table `purchase_order_items`

Purchase order lines (about 16,000 rows).

- Group: Inventory. Primary key: `po_item_id`.
- Foreign keys: `po_id -> purchase_orders.po_id`; `product_id -> products.product_id`.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `po_item_id` | INTEGER | no | Primary key. |
| `po_id` | INTEGER | no | Parent purchase order. |
| `product_id` | INTEGER | no | Product ordered. |
| `quantity_ordered` | INTEGER | no | Units ordered. |
| `quantity_received` | INTEGER | no | Units received so far (0 for Open or In Transit lines). |
| `unit_cost` | NUMERIC(10,2) | no | Cost per unit on the PO in SAR. |

## Table `stock_adjustments`

Non-sales stock movements such as damage, expiry, shrinkage and count corrections (about 3,000 rows).

- Group: Inventory. Primary key: `adjustment_id`.
- Foreign keys: `branch_id -> branches.branch_id`; `product_id -> products.product_id`.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `adjustment_id` | INTEGER | no | Primary key. |
| `branch_id` | INTEGER | no | Location. |
| `product_id` | INTEGER | no | Product. |
| `adjustment_date` | DATE | no | Date of the adjustment. |
| `quantity_change` | INTEGER | no | Units added (positive) or removed (negative). |
| `reason` | VARCHAR(20) | no | Damage, Expiry, Shrinkage, Count Correction or Display Sample. |
| `cost_impact` | NUMERIC(12,2) | no | Cost value of the change in SAR (negative for losses). |
