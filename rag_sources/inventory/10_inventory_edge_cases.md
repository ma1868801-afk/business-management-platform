# Inventory: Edge Cases and Data Quality

- Document ID: INV-10
- Index: inventory
- Purpose: what to do when an inventory question is ambiguous, refers to something that is not stocked, falls outside the data, or asks for an action the assistant must not take.

## Dates and Snapshots

| Situation | Handling |
|---|---|
| "Current stock", "today", "now" | `inventory_levels` as of 2026-10-31. Say "as of 2026-10-31". |
| Stock on an earlier date | Weekly snapshots exist for Saturdays from 2024-01-06. Use the latest Saturday on or before the requested date and say which date was used. "Last week" means the snapshot of 2026-10-24. |
| Stock before 2024-01-06, or at a date after 2026-10-31 | Not available. For a future date offer a forecast of demand and a projection of stock, labelled as an estimate. |
| "Next week", "next month", "next quarter" | The weeks starting 2026-11-01: 1 week, 4 weeks and 13 weeks. |
| Weeks | Sunday to Saturday. Snapshot dates are Saturdays; the week start is the snapshot date minus 6 days. |

## Entities

- A SKU with no row at a store is not stocked there. Say "not stocked", never "zero" or "out of stock". Use INV-SQL-21 to list the locations that do not stock a SKU.
- A product name that matches several SKUs: list the candidates and answer for all of them. A name that matches none: say that no product was found and show the closest names (DA-SQL-29 resolves names).
- A product line request ("beauty stock") covers all SKUs of the line; say how many SKUs and which locations.
- "Warehouse", "DC" and "central warehouse" mean `RYD-DC`. "The store" without a name is ambiguous; ask or list all stores.
- Quantities are in the SKU's unit of measure (Each, Pack, Box, Kg or Set). A "12 pack" SKU counts packs, not bottles.

## Data Quality and Interpretation

- `quantity_available` is on hand minus reserved. A position can be Out of Stock while physical units remain (all reserved).
- The 2026-10-31 snapshot equals the current `quantity_on_hand`; if the two ever differ, report the current table and mention the difference.
- Stock quantities are never negative. A stock adjustment can be negative (a loss) or positive (a count correction).
- `stockout_days` ranges from 0 to 7 in a weekly snapshot. A week with 7 stockout days has zero sales; that zero is a stockout, not a lack of demand.
- Weekly demand views omit weeks without sales. Fill them with zero for series, but do not fill weeks before a SKU's first sale.
- Purchase orders in status Cancelled carry no delivery; never count them in delivery performance.
- Currency is SAR. Purchase orders are converted at the order date.
- Stock value is at cost. If the user asks for value "at retail", multiply the quantity by `unit_price` (excluding VAT) and say so.

## Forecast Requests That Need Care

| Request | Handling |
|---|---|
| No sales history (not launched yet) | No forecast. Say that the SKU has no sales history. |
| Fewer than 26 weeks of sales (New SKU) | Cold start with a range and a Low confidence label (INV-04). |
| Discontinued SKU | No forecast. Show remaining stock and weeks of cover. |
| Horizon above 13 weeks | Forecast 13 weeks and say the horizon was limited. Use the event planning steps of INV-07 when a later event is the reason. |
| Horizon of zero or negative | Ask for a horizon between 1 and 13 weeks, or use 8 weeks. |
| Revenue forecast | The tool forecasts units. Convert at the current list price (excluding VAT) and call it an estimate that ignores discounts. A revenue-focused question goes to Data Analysis for the history. |
| "What if we run a promotion" | Run the forecast with `promo: planned` and show it next to the no-promotion forecast. The promotion effect is estimated from past promotion weeks of the SKU only. |
| "What if the price changes" | Not modelled. Say so. |
| A location with too little history | Forecast at SKU level and allocate by the location's recent share (INV-04). |
| Stockouts in the history | Adjusted before fitting (INV-PY-02). Mention it when more than 25 percent of the weeks were adjusted. |

## Requests That Must Not Be Fulfilled

- Creating, approving, cancelling or changing a purchase order; transferring stock; adjusting a quantity; changing a reorder point. These are write requests; reject them and offer a recommendation instead.
- Employee or contract personal data. Questions about supplier contract wording go to the Knowledge Base.
- Anything that needs the `rag` schema or system information.

## Questions the Data Cannot Answer

| Request | Answer |
|---|---|
| Warehouse capacity, shelf space, storage cost | Not stored. |
| Transfers between locations | Not recorded. |
| Customs and transport times | Not modelled; only the contractual lead time exists. |
| Lost sales and unmet demand | Not measured. Stockout weeks can be shown. |
| Competitor stock or prices | Not stored. |
| Reasons for a stockout | Not stored. Show the pattern (stockout weeks, late orders) and label any explanation as a hypothesis. |

## Failure Handling

- If a query fails validation or times out, regenerate or narrow it (at most two retries), as in DA-10.
- If the regression tool refuses or fails, return `status = "partial"` with the stock facts that are reliable and a plain note, or `failed` when nothing can be answered. Never invent a forecast.
- Put every limitation that changes how a number should be read into `warnings`.

## SQL Pattern

### INV-SQL-21: Locations that do not stock a SKU

Use to answer "is KIDS-0001 available at every store" without confusing "not stocked" with "out of stock". Lists the locations that have no stock position for the SKU.

```sql
SELECT b.branch_code,
       b.branch_name
FROM branches b
WHERE NOT EXISTS (
        SELECT 1
        FROM inventory_levels l
        JOIN products p ON p.product_id = l.product_id
        WHERE l.branch_id = b.branch_id
          AND p.sku = 'KIDS-0001')
ORDER BY b.branch_code
LIMIT 20;
```
