# Data Analysis: Schema Reference

- Document ID: DA-02
- Source: generated from the data dictionary in `docs/03_database_design.md`; the two documents cannot disagree.
- Dialect: PostgreSQL 16. All text values are English. Currency SAR. Revenue excludes 15 percent VAT.

This reference describes the Sales, Customers, Promotions, Calendar and Targets data used by the Data Analysis subgraph. Start from `v_sales_detail` for almost every sales question. Inventory tables are not listed here; stock and forecasting questions belong to the Inventory subgraph.

## Objects the SQL Tool May Use

Tables: `branches`, `product_categories`, `suppliers`, `products`, `customers`, `promotions`, `calendar`, `monthly_sales_targets`, `sales_orders`, `sales_order_items`, `sales_returns`.

Views: `v_sales_detail`, `v_weekly_product_demand`.

## Reading Rules

- Net revenue means `SUM(line_total)` for orders with `status = 'Completed'`. Gross sales before discount is net revenue plus `sales_orders.discount_amount`.
- `v_sales_detail` has one row per order line and includes every order status, so every revenue query must filter `status = 'Completed'`.
- Count orders with `COUNT(DISTINCT order_id)`, never `COUNT(*)` on the view, because the view has one row per line.
- Order header amounts (`subtotal_amount`, `total_amount`) are on `sales_orders`. Joining header amounts to lines multiplies them by the number of lines; aggregate headers separately.
- `customers.email` and `customers.phone` are not readable. Select explicit customer columns; `SELECT *` on `customers` fails by design.
- Online, Mobile App and B2B orders are attributed to branch `RYD-DC`. Store rankings must exclude `RYD-DC`.
- Weeks start on Sunday. `calendar.day_of_week` is 0 for Sunday to 6 for Saturday; the weekend is Friday (5) and Saturday (6).
- The data ends on 2026-10-31. Never use the system clock; resolve relative dates from the reference date 2026-10-31.

## Join Map

- `sales_order_items.order_id` = `sales_orders.order_id`; `sales_order_items.product_id` = `products.product_id`.
- `sales_orders.branch_id` = `branches.branch_id`; `sales_orders.customer_id` = `customers.customer_id` (LEFT JOIN, nullable); `sales_orders.promotion_id` = `promotions.promotion_id` (LEFT JOIN, nullable).
- `products.category_id` = `product_categories.category_id`; `products.supplier_id` = `suppliers.supplier_id`.
- `sales_orders.order_date` = `calendar.date_key` for season, weekday, payday and Ramadan flags.
- `monthly_sales_targets.branch_id` = `branches.branch_id`; match `target_month` to the first day of the month of `order_date`.
- `sales_returns.order_item_id` = `sales_order_items.order_item_id`; returns also carry `order_id`, `product_id` and `branch_id`.

## Value Lists

- `channel`: In-Store, Online, Mobile App, B2B.
- `status`: Completed, Cancelled, Returned (fully returned), Processing (only 2026-10-29 to 2026-10-31).
- `payment_method`: Mada, Credit Card, Apple Pay, STC Pay, Cash, Cash on Delivery, Buy Now Pay Later, Bank Transfer.
- `season`: Ramadan, Eid al-Fitr, Hajj and Eid al-Adha, White Friday, National Day, Founding Day, Back to School, Summer, Winter, Regular.
- `loyalty_tier`: None, Silver, Gold, Platinum. `customer_type`: Individual, Business. `customer_segment`: Premium, Core, Occasional.
- Product line codes: ELEC, APPL, FASH, GROC, BEAU, SPRT, KIDS, HOME (use `product_categories.category_name` for display).
- Branch codes: RYD-OLY, JED-THL, RYD-MLQ, DMM-FSL, KHB-COR, MED-QBA, JED-OBH, ABH-CTY, RYD-DC.
- `return_reason`: Defective, Wrong Item, Changed Mind, Late Delivery, Not as Described, Damaged in Transit.

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

## Table `customers`

About 6,000 registered customers: individual consumers and business accounts. Twelve business accounts have contracts documented in the knowledge base.

- Group: Customers. Primary key: `customer_id`.
- Foreign keys: `preferred_branch_id -> branches.branch_id`.
- Note: The read-only database role has column-level SELECT on every column of this table except email and phone, so SELECT * on customers fails and column lists must be explicit.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `customer_id` | INTEGER | no | Primary key. |
| `customer_code` | VARCHAR(12) | no | Unique code: CUST-000001 style for individuals and CUST-B001 style for contract business accounts. |
| `customer_type` | VARCHAR(12) | no | Individual or Business. |
| `full_name` | VARCHAR(120) | no | Customer name or company name (synthetic). |
| `gender` | VARCHAR(10) | yes | Male or Female for individuals; NULL for businesses. |
| `age_group` | VARCHAR(10) | yes | 18-24, 25-34, 35-44, 45-54 or 55+; NULL for businesses. |
| `city` | VARCHAR(40) | no | Home city of the customer. |
| `region` | VARCHAR(20) | no | Macro region of the customer city. |
| `customer_segment` | VARCHAR(12) | no | Marketing value segment assigned at registration review: Premium, Core or Occasional. |
| `loyalty_tier` | VARCHAR(10) | no | None, Silver, Gold or Platinum (Nakhla Rewards programme). |
| `loyalty_points` | INTEGER | no | Current loyalty points balance. |
| `registration_date` | DATE | no | Date the customer registered; ranges from before 2024 to October 2026. |
| `acquisition_channel` | VARCHAR(20) | no | Walk-in, Website, Mobile App, Social Media, Referral or B2B Sales. |
| `preferred_branch_id` | INTEGER | yes | Most frequently used branch at registration. |
| `marketing_opt_in` | BOOLEAN | no | True when the customer agreed to receive marketing messages. |
| `contract_number` | VARCHAR(20) | yes | Contract number for the twelve contract business accounts; NULL otherwise. |
| `credit_limit` | NUMERIC(12,2) | yes | Approved credit limit in SAR for business accounts; NULL for individuals. |
| `payment_terms_days` | INTEGER | yes | Payment terms for business accounts; NULL for individuals. |
| `email` | VARCHAR(120) | yes | PII. Not readable by the read-only role. |
| `phone` | VARCHAR(20) | yes | PII. Not readable by the read-only role. |
| `is_active` | BOOLEAN | no | False for accounts closed on customer request. |

## Table `promotions`

Promotion master used to explain discounts and promotional uplift. About 40 promotions between 2024 and October 2026.

- Group: Sales. Primary key: `promotion_id`.
- Foreign keys: `category_id -> product_categories.category_id`.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `promotion_id` | INTEGER | no | Primary key. |
| `promotion_code` | VARCHAR(20) | no | Unique code such as PROMO-WF-2025. |
| `promotion_name` | VARCHAR(100) | no | Display name such as 'White Friday 2025'. |
| `promotion_type` | VARCHAR(20) | no | Percentage Off, Bundle Deal, Seasonal Sale, Loyalty Bonus or Clearance. |
| `discount_pct` | NUMERIC(5,2) | no | Headline discount percentage. |
| `start_date` | DATE | no | First day of the promotion. |
| `end_date` | DATE | no | Last day of the promotion. |
| `season` | VARCHAR(30) | yes | Commercial season the promotion belongs to. |
| `category_id` | INTEGER | yes | Product line the promotion applies to; NULL means store-wide. |
| `channel_scope` | VARCHAR(10) | no | All, In-Store or Online. |
| `min_basket_amount` | NUMERIC(10,2) | yes | Minimum basket value to qualify, if any. |

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

## Table `monthly_sales_targets`

Monthly revenue target for each location (9 locations x 34 months = 306 rows).

- Group: Sales. Primary key: `target_id`.
- Foreign keys: `branch_id -> branches.branch_id`.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `target_id` | INTEGER | no | Primary key. |
| `branch_id` | INTEGER | no | Location. |
| `target_month` | DATE | no | First day of the target month. |
| `target_revenue` | NUMERIC(14,2) | no | Net revenue target in SAR, excluding VAT. |

## Table `sales_orders`

Order header, one row per customer order or in-store transaction (about 120,000 rows, 2024-01-01 to 2026-10-31).

- Group: Sales. Primary key: `order_id`.
- Foreign keys: `customer_id -> customers.customer_id (nullable)`; `branch_id -> branches.branch_id`; `promotion_id -> promotions.promotion_id (nullable)`.
- Note: Revenue excludes VAT. Default revenue = SUM(sales_order_items.line_total) for orders with status = 'Completed'.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `order_id` | BIGINT | no | Primary key. |
| `order_number` | VARCHAR(20) | no | Unique business number such as SO-2025-0004512. |
| `customer_id` | INTEGER | yes | Customer; NULL for anonymous in-store walk-in transactions (about 8% of in-store orders). |
| `branch_id` | INTEGER | no | Selling location. Online and B2B orders are attributed to the Distribution Center. |
| `channel` | VARCHAR(12) | no | In-Store, Online, Mobile App or B2B. |
| `order_timestamp` | TIMESTAMP | no | Local Riyadh time (UTC+3) when the order was placed. |
| `order_date` | DATE | no | Date part of order_timestamp. |
| `order_hour` | SMALLINT | no | Hour of day 0-23 of order_timestamp. |
| `season` | VARCHAR(30) | no | Commercial season of order_date (same values as calendar.season). |
| `status` | VARCHAR(12) | no | Completed, Cancelled, Returned (fully returned) or Processing (only the last three days of the dataset). |
| `payment_method` | VARCHAR(20) | no | Mada, Credit Card, Apple Pay, STC Pay, Cash, Cash on Delivery, Buy Now Pay Later or Bank Transfer. |
| `promotion_id` | INTEGER | yes | Promotion applied to the order, if any. |
| `items_count` | SMALLINT | no | Number of order lines. |
| `subtotal_amount` | NUMERIC(12,2) | no | Sum of line_total of the order (net of line discounts, excluding VAT). Equals the order net revenue. |
| `discount_amount` | NUMERIC(12,2) | no | Total line discounts given on the order in SAR (informational). Gross sales before discount = subtotal_amount + discount_amount. |
| `vat_amount` | NUMERIC(12,2) | no | 15% VAT on subtotal_amount. |
| `shipping_fee` | NUMERIC(8,2) | no | Delivery fee in SAR: 25 for Online and Mobile App orders with subtotal_amount under SAR 250 placed by customers who are not Gold or Platinum; 0 for every other order. |
| `total_amount` | NUMERIC(12,2) | no | subtotal_amount + vat_amount + shipping_fee (what the customer pays). |
| `delivery_city` | VARCHAR(40) | yes | Delivery city for Online, Mobile App and B2B orders; NULL for in-store. |
| `currency` | VARCHAR(3) | no | Always SAR. |

## Table `sales_order_items`

Order lines, one row per product on an order (about 300,000 rows).

- Group: Sales. Primary key: `order_item_id`.
- Foreign keys: `order_id -> sales_orders.order_id`; `product_id -> products.product_id`.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `order_item_id` | BIGINT | no | Primary key. |
| `order_id` | BIGINT | no | Parent order. |
| `product_id` | INTEGER | no | Product sold. |
| `quantity` | INTEGER | no | Units sold (at least 1). |
| `unit_price` | NUMERIC(10,2) | no | Selling price per unit before line discount, excluding VAT. |
| `unit_cost` | NUMERIC(10,2) | no | Cost per unit at the time of sale. |
| `discount_pct` | NUMERIC(5,2) | no | Line discount percentage (0 if none). |
| `line_total` | NUMERIC(12,2) | no | quantity x unit_price x (1 - discount_pct/100), excluding VAT. This is the revenue column. |
| `line_cost` | NUMERIC(12,2) | no | quantity x unit_cost. Gross margin = line_total - line_cost. |

## Table `sales_returns`

Product returns and refunds (about 9,000 rows). Returns happen within 14 days of the order, or 30 days for Defective items.

- Group: Sales. Primary key: `return_id`.
- Foreign keys: `order_item_id -> sales_order_items.order_item_id`; `order_id -> sales_orders.order_id`; `product_id -> products.product_id`; `branch_id -> branches.branch_id`.

| Column | Type | Nullable | Meaning |
|---|---|---|---|
| `return_id` | BIGINT | no | Primary key. |
| `order_item_id` | BIGINT | no | Returned order line. |
| `order_id` | BIGINT | no | Parent order. |
| `product_id` | INTEGER | no | Product returned. |
| `branch_id` | INTEGER | no | Location that processed the return. |
| `return_date` | DATE | no | Date the return was processed. |
| `quantity_returned` | INTEGER | no | Units returned (not more than the units sold on the line). |
| `refund_amount` | NUMERIC(12,2) | no | Refund in SAR excluding VAT. |
| `return_reason` | VARCHAR(25) | no | Defective, Wrong Item, Changed Mind, Late Delivery, Not as Described or Damaged in Transit. |
| `restocked` | BOOLEAN | no | True when the returned units went back to sellable stock. |
