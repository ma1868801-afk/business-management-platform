# Inventory: Domain Knowledge

- Document ID: INV-06
- Index: inventory
- Purpose: the inventory concepts, policies and measures used at Nakhla Retail Group, so the Inventory subgraph interprets stock data correctly and explains it in business terms.

## Network and Stock Positions

- Nine locations: eight stores (two Flagship, four Standard, two Express) and the Distribution Center `RYD-DC`. The Distribution Center holds all 120 SKUs, receives most purchase orders and fulfills Online, Mobile App and B2B orders. Each store holds 80 to 100 SKUs.
- Flagship stores: `RYD-OLY` and `JED-THL`. Standard stores: `RYD-MLQ`, `DMM-FSL`, `KHB-COR` and `MED-QBA`. Express stores: `JED-OBH` and `ABH-CTY`.
- The data has one current stock position per location and SKU (about 840 rows) and weekly Saturday snapshots from 2024-01-06 to 2026-10-31.
- Transfers from the Distribution Center to stores are not recorded as separate movements. Do not describe transfer history; describe only stock positions, snapshots, purchase orders and adjustments.

## Product Lines and Stock Characteristics

| Line | Code | Stock characteristics |
|---|---|---|
| Consumer Electronics | ELEC | High unit value, low volume; large stock value; peaks at White Friday. |
| Home Appliances | APPL | Seasonal cooling products (fans, air conditioners) peak in June to August. |
| Fashion and Apparel | FASH | Peaks at Eid al-Fitr; winter lines in December to February; a declining old collection. |
| Grocery and Gourmet | GROC | Highest unit volume; shelf-life items; Ramadan peak (dates, baskets). |
| Beauty and Fragrance | BEAU | Shelf-life items (skincare, perfume); peaks at Eid al-Fitr and National Day. |
| Sports and Outdoor | SPRT | Camping gear peaks from November to February. |
| Kids and School | KIDS | School supplies and backpacks peak from 1 August to 15 September. |
| Home Decor and Furnishing | HOME | Peaks before Ramadan and at White Friday; a declining old collection. |

Shelf life: 23 SKUs (in Grocery and Beauty) have `shelf_life_days`. Only these SKUs can have an Expiry adjustment. Stock of these SKUs should be sold first-expired-first-out, and cover above the shelf life is a risk.

## Lifecycle

| Status | Meaning | Treatment |
|---|---|---|
| New | Launched in 2026, fewer than 26 weeks of sales (four SKUs). | Forecast with cold start; mention the short history. |
| Active | Regular range. | Normal. |
| Declining | Falling demand (eight SKUs). Two of them, the old collections FASH-0013 and HOME-0013, have had no sale in the last 13 weeks. | Do not build stock; consider markdown. |
| Discontinued | No longer sold or replenished (four SKUs). | Excluded from reorder lists and forecasts; remaining stock is reported as run-off. |

Dead stock is stock with no Completed sale in the last 13 weeks (3 August to 31 October 2026). Six SKUs fit this description at the reference date: the four discontinued SKUs and the two declining old collections FASH-0013 and HOME-0013. See INV-SQL-07.

## Replenishment Policy

- Reorder point = demand during the supplier lead time plus safety stock.
- Safety stock protects against variation in weekly demand and in delivery time. It is based on a service level (the target probability of not running out during a replenishment cycle). The service level depends on the ABC class of the SKU: class A 98 percent (z 2.05), class B 95 percent (z 1.65) and class C 90 percent (z 1.28). Classes follow net revenue: A holds the SKUs that make the first 80 percent of revenue, B the next 15 percent and C the rest (the Pareto method of DA-PY-07).
- Max stock level = reorder point plus reorder quantity.
- A replenishment order is triggered when `quantity_available` is at or below the reorder point (status Reorder Now) and is urgent at or below safety stock (Critical).
- Order quantities are rounded up to the supplier's minimum order quantity (`min_order_qty`).
- Lead times (`lead_time_days`) are 4 to 45 days depending on the supplier. Purchase orders carry `expected_delivery_date = order_date + lead_time_days`.

### Safety Stock and Reorder Point Formulas

With mean weekly demand `m`, weekly demand standard deviation `s`, lead time `L` weeks, lead-time standard deviation `sL` weeks and service level factor `z` (2.05 for class A, 1.65 for class B, 1.28 for class C):

- Safety stock = z x square root of (L x s squared + (m x sL) squared).
- Reorder point = m x L + safety stock.

A higher service level or a less reliable supplier raises safety stock. The measured standard deviation of delivery delays comes from INV-SQL-19.

### INV-PY-07: Check a reorder point against demand and supplier reliability

Use for "is the reorder point for this SKU adequate". The history is the stockout-adjusted weekly demand of the location (`df`, from INV-PY-02), the supplier figures come from INV-SQL-19 and the current policy values from `inventory_levels` (`dfs["supplier"]` and `dfs["position"]`). The calculation uses the last 26 weeks and the class B service level of 95 percent; use 0.98 for a class A SKU and 0.90 for a class C SKU.

```python
# fixture: policy_demand
d = df.copy()
sup = dfs["supplier"].iloc[0]
pos = dfs["position"].iloc[0]
recent = pd.to_numeric(d["units_adjusted"]).tail(26)
mean_weekly = float(recent.mean())
sd_weekly = float(recent.std(ddof=1))
lead_weeks = float(sup["lead_time_days"]) / 7
lead_sd_weeks = float(sup["lead_time_sd_days"]) / 7
service_level = 0.95
z = float(stats.norm.ppf(service_level))
safety_stock = z * math.sqrt(lead_weeks * sd_weekly ** 2 + (mean_weekly * lead_sd_weeks) ** 2)
reorder_point = mean_weekly * lead_weeks + safety_stock
result = pd.DataFrame({
    "measure": ["Safety stock", "Reorder point"],
    "calculated_units": [math.ceil(safety_stock), math.ceil(reorder_point)],
    "stored_units": [int(pos["safety_stock"]), int(pos["reorder_point"])],
})
result["difference_units"] = result["calculated_units"] - result["stored_units"]
facts = {
    "mean_weekly_demand": round(mean_weekly, 1),
    "weekly_demand_sd": round(sd_weekly, 1),
    "lead_time_weeks": round(lead_weeks, 2),
    "service_level": service_level,
}
```

If the calculated reorder point is clearly above the stored one, the stored value may leave the location exposed to stockouts; if it is far below, stock may be held unnecessarily. Say that a policy change is a decision for the planning team; the subgraph recommends and does not change values.

## Inventory Measures

| Measure | Definition |
|---|---|
| Weeks of cover | Available units divided by average weekly units sold (INV-SQL-06). |
| Stock value | On hand multiplied by unit cost, in SAR at cost. |
| Stock turnover | Cost of goods sold of the last 12 months divided by average stock value at cost. It is approximate: it uses the current unit cost for the whole period. Annual turnover is 12 months of cost, not the calendar year. |
| In-stock rate | Share of weekly snapshots with no stockout days. |
| Stockout rate | One minus the in-stock rate. |
| Overstock ratio | Stock value of Overstock positions divided by total stock value. |
| Dead stock value | Stock value at cost of SKUs without a Completed sale in the last 13 weeks. |
| Shrinkage and loss rate | Negative cost impact of adjustments (Damage, Expiry, Shrinkage) divided by stock value. |
| Supplier on-time rate | Share of Received or Partially Received purchase orders with `actual_delivery_date` on or before `expected_delivery_date` (INV-SQL-18). |

Not measurable from the data: unmet demand (lost sales), fill rate and customer waiting time. Say so if asked.

## Purchase Orders

- Statuses: Received, Partially Received, In Transit, Open, Cancelled.
- Received orders have an actual delivery date; Open and In Transit orders do not.
- At the reference date at least 40 orders are Open or In Transit. An order is overdue when its expected delivery date has passed (INV-SQL-11).
- A line is partially received when `quantity_received` is below `quantity_ordered`.
- Purchase order totals are the sum of quantity ordered times unit cost, in SAR, and are always stored in SAR (converted at the order date), even when the supplier invoices in another currency.

## Stock Adjustments

Reasons: Damage, Expiry, Shrinkage, Count Correction and Display Sample. The quantity change is negative for losses. `cost_impact` equals the quantity change times the unit cost. A positive Count Correction adds stock found in a count.
