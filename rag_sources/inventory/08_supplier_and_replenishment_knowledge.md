# Inventory: Supplier and Replenishment Knowledge

- Document ID: INV-08
- Index: inventory
- Purpose: facts and rules about the 16 contracted suppliers, how their delivery performance is measured from purchase orders, and how supplier lead times drive replenishment. Contract wording (penalties, renewals, payment terms) belongs to the Knowledge Base; measured performance belongs here.

## Supplier Master

Each supplier serves one product line. Lead time is the contractual number of days from the order date to the expected delivery date. The recorded on-time rate is the rate stated in the supplier master (`suppliers.on_time_delivery_pct`); the measured rate comes from purchase orders (INV-SQL-18) and is within 3 points of it.

| Code | Supplier | Country | Line | Lead time (days) | Minimum order qty | Recorded on-time rate (%) | Billing currency |
|---|---|---|---|---|---|---|---|
| SUP-01 | Gulf Digital Trading Co. | Saudi Arabia | ELEC | 7 | 40 | 96.5 | SAR |
| SUP-02 | Shenzhen Nova Electronics Ltd. | China | ELEC | 42 | 200 | 91.0 | USD |
| SUP-03 | Al Jazeera Home Appliances Co. | Saudi Arabia | APPL | 6 | 25 | 94.0 | SAR |
| SUP-04 | Istanbul Cooling Systems A.S. | Turkey | APPL | 21 | 60 | 84.0 | EUR |
| SUP-05 | Levant Fashion House | Jordan | FASH | 14 | 120 | 93.0 | USD |
| SUP-06 | Bosphorus Textile Group | Turkey | FASH | 24 | 150 | 87.5 | EUR |
| SUP-07 | Al Qassim Dates Cooperative | Saudi Arabia | GROC | 4 | 300 | 97.5 | SAR |
| SUP-08 | Mediterranean Gourmet Imports | United Arab Emirates | GROC | 9 | 250 | 82.5 | AED |
| SUP-09 | Dubai Oud and Perfumes FZE | United Arab Emirates | BEAU | 8 | 80 | 95.0 | AED |
| SUP-10 | Paris Beaute Distribution SARL | France | BEAU | 30 | 100 | 91.0 | EUR |
| SUP-11 | Tabuk Outdoor Gear Co. | Saudi Arabia | SPRT | 7 | 50 | 92.5 | SAR |
| SUP-12 | Munich Sport Systems GmbH | Germany | SPRT | 35 | 80 | 89.0 | EUR |
| SUP-13 | Cairo Educational Supplies | Egypt | KIDS | 18 | 200 | 90.5 | USD |
| SUP-14 | Bright Minds Toys Ltd. | China | KIDS | 45 | 250 | 91.5 | USD |
| SUP-15 | Jeddah Home Interiors Co. | Saudi Arabia | HOME | 5 | 30 | 98.0 | SAR |
| SUP-16 | Milan Casa Design S.r.l. | Italy | HOME | 33 | 40 | 93.5 | EUR |

- Four suppliers have a recorded on-time rate below 90 percent: SUP-08 (82.5), SUP-04 (84.0), SUP-06 (87.5) and SUP-12 (89.0). The first two are also below 85 percent.
- The longest lead times are SUP-14 (45 days), SUP-02 (42 days) and SUP-12 (35 days); the shortest are SUP-07 (4 days), SUP-15 (5 days) and SUP-03 (6 days).
- Each purchase order line meets the supplier's minimum order quantity. `expected_delivery_date` is `order_date` plus the supplier's lead time.

## Measured Delivery Performance

| Measure | Definition |
|---|---|
| On-time order | A Received or Partially Received purchase order with `actual_delivery_date` on or before `expected_delivery_date`. |
| Measured on-time rate | On-time orders divided by Received and Partially Received orders of the supplier, in percent. |
| Delay days | `actual_delivery_date` minus `expected_delivery_date`. Negative or zero means on time or early. |
| Actual lead time | `actual_delivery_date` minus `order_date`. |
| Delay variability | The standard deviation of delay days; it feeds the safety stock formula (INV-06). |
| Fill rate by quantity | Sum of `quantity_received` divided by sum of `quantity_ordered` for Received and Partially Received orders. |

Cancelled, Open and In Transit orders are excluded from on-time measures, because they have no actual delivery date. Overdue open orders are reported separately (INV-SQL-11). State the period and the number of orders behind any rate; a rate on fewer than 10 orders is only indicative.

## How Lead Time Drives Replenishment

- Longer lead times need higher reorder points and earlier orders. A SKU from a supplier with a 45-day lead time needs about 6.4 weeks of demand on order or in stock when it reaches the reorder point.
- A supplier with a low on-time rate needs extra safety stock, because the real lead time varies. Use the delay variability from INV-SQL-19.
- Orders are placed roughly every 2 to 6 weeks per supplier, depending on lead time. Combine SKUs of the same supplier into one order when it helps to reach minimum order quantities.
- For imported goods (China, Turkey, Europe) allow for customs and transport inside the contractual lead time; the data does not model them separately.

## Using Supplier Data in Answers

- "Which supplier delivers on time least often" is answered from INV-SQL-18 (measured). Mention the recorded rate if it differs.
- "What does the contract say about late delivery" is a Knowledge Base question. When both are asked, the answer has two parts: the contract wording from the Knowledge Base and the measured performance from here.
- A supplier with a low rate is a risk for the SKUs it supplies. List the SKUs and their stock status when the user asks about the impact.
- Do not recommend changing or ending a contract. Describe the performance and let the user decide.

## SQL Patterns

### INV-SQL-18: Supplier on-time delivery measured from purchase orders

Use for "which supplier delivers late most often". Counts Received and Partially Received orders and the orders delivered on or before the expected date, and shows the recorded rate for comparison. The worst supplier comes first.

```sql
SELECT s.supplier_code,
       s.supplier_name,
       s.lead_time_days,
       COUNT(*) AS received_orders,
       COUNT(*) FILTER (WHERE po.actual_delivery_date <= po.expected_delivery_date) AS on_time_orders,
       ROUND(100.0 * COUNT(*) FILTER (WHERE po.actual_delivery_date <= po.expected_delivery_date) / NULLIF(COUNT(*), 0), 1) AS measured_on_time_pct,
       s.on_time_delivery_pct AS recorded_on_time_pct
FROM purchase_orders po
JOIN suppliers s ON s.supplier_id = po.supplier_id
WHERE po.status IN ('Received', 'Partially Received')
GROUP BY s.supplier_code, s.supplier_name, s.lead_time_days, s.on_time_delivery_pct
ORDER BY measured_on_time_pct, s.supplier_code;
```

### INV-SQL-19: Delay statistics per supplier

Use for the actual lead time and its variability, for example before checking a reorder point. Returns the average actual lead time, the average and maximum delay and the standard deviation of the delay in days for each supplier.

```sql
SELECT s.supplier_code,
       s.lead_time_days AS contract_lead_time_days,
       ROUND(AVG(po.actual_delivery_date - po.order_date), 1) AS avg_actual_lead_time_days,
       ROUND(AVG(po.actual_delivery_date - po.expected_delivery_date), 1) AS avg_delay_days,
       ROUND(COALESCE(STDDEV_SAMP(po.actual_delivery_date - po.expected_delivery_date), 0), 1) AS delay_sd_days,
       MAX(po.actual_delivery_date - po.expected_delivery_date) AS max_delay_days
FROM purchase_orders po
JOIN suppliers s ON s.supplier_id = po.supplier_id
WHERE po.status IN ('Received', 'Partially Received')
GROUP BY s.supplier_code, s.lead_time_days
ORDER BY avg_delay_days DESC, s.supplier_code;
```

### INV-SQL-20: Quantity on order for one SKU

Use before giving reorder advice: the units already ordered and not yet received. Lists the Open and In Transit purchase order lines of the SKU with the expected delivery date and the outstanding quantity. Partially Received orders are treated as closed.

```sql
SELECT p.sku,
       po.po_number,
       po.status,
       po.expected_delivery_date,
       (poi.quantity_ordered - poi.quantity_received) AS quantity_on_order
FROM purchase_order_items poi
JOIN purchase_orders po ON po.po_id = poi.po_id
JOIN products p ON p.product_id = poi.product_id
WHERE po.status IN ('Open', 'In Transit')
  AND p.sku = 'GROC-0001'
ORDER BY po.expected_delivery_date, po.po_number
LIMIT 50;
```
