# Inventory: Reorder Advice Rules

- Document ID: INV-09
- Index: inventory
- Purpose: how to turn a forecast, the current stock and the open purchase orders into a reorder recommendation. The subgraph recommends only. It never creates, approves or changes a purchase order, a transfer or a stock level (those requests are rejected as write requests).

## When to Give Reorder Advice

Give advice when the user asks what to order, how much to order, when to order or whether stock will last. The routing hint `forecast_requested` is true in these cases, and the tool input has `with_reorder_advice = true`. For a plain "which items are at the reorder point" question, use the stock status list (INV-SQL-04) and no forecast.

## Inputs

| Input | Source |
|---|---|
| Forecast units per week for the horizon | Regression tool (INV-05) |
| Available stock | Sum of `quantity_available` over all locations for the SKU (`v_inventory_status`) |
| Safety stock, reorder point, reorder quantity | `inventory_levels` of the Distribution Center, since replenishment orders are received there |
| Lead time and minimum order quantity | `suppliers` (INV-08) |
| Quantity on order | Open and In Transit purchase order lines (INV-SQL-20) |
| Lifecycle status, shelf life | `products` |

Advice is given at chain level: the forecast covers all locations, and the stock is the total available stock. Store-level shortages are reported from the stock status list; transfers from the Distribution Center are not modelled.

## Calculation

1. Lead time in weeks = lead time days divided by 7, rounded up.
2. Cover period = lead time weeks plus one review week, limited to the horizon.
3. Required stock = forecast units over the cover period + safety stock.
4. Net requirement = required stock minus available stock minus quantity on order.
5. Recommended order = net requirement rounded up to a multiple of the supplier's minimum order quantity; zero when the net requirement is not positive.
6. Projected available stock by week = available stock minus cumulative forecast, plus the quantity on order from the week of the lead time onwards. The first week below safety stock is the breach week.
7. Order-by week = breach week minus lead time weeks. If that week has already started, the order is needed now.

## Rules and Limits

- Discontinued SKUs: no order. Show remaining stock and weeks of cover.
- Declining SKUs: recommend the minimum (minimum order quantity) or no order, and say that demand is falling.
- New SKUs (fewer than 26 weeks of sales): give the advice with the cold-start warning and Low confidence.
- Shelf-life SKUs (23 in Grocery and Beauty): the stock after delivery should not exceed the demand of half the shelf life. If the recommendation does exceed it, reduce it to that limit and say so.
- Seasonal SKUs before a peak: check that the peak is inside the cover period; for a peak after the horizon, follow the event planning steps in INV-07.
- If the supplier has a recorded on-time rate below 90 percent, add one sentence about the delivery risk and mention the safety stock.
- Always show the standard `reorder_quantity` next to the recommendation, because the user may choose it.
- If a stock position is already Out of Stock or Critical, say so first; the order is urgent.
- The advice depends on the forecast. State the confidence label and the interval range; for Low confidence suggest reviewing the order after the next weekly data.
- A recommendation is not an order. Close with "this is a recommendation for the planning team to review", or equivalent wording.

## Example

### INV-PY-08: Reorder recommendation from a forecast

Use after a forecast to compute the recommended order and the order-by week. The forecast rows are `df`, the current position of the SKU is `dfs["position"]` (one row) and the open purchase order lines are `dfs["pipeline"]`. The result is a weekly projection of available stock; the facts hold the recommendation.

```python
# fixture: reorder_forecast
f = df.copy()
f["week_start_date"] = pd.to_datetime(f["week_start_date"])
pos = dfs["position"].iloc[0]
pipe = dfs["pipeline"]
available = float(pos["quantity_available"])
safety = float(pos["safety_stock"])
moq = int(pos["min_order_qty"])
on_order = float(pd.to_numeric(pipe["quantity_on_order"]).sum()) if len(pipe) else 0.0
lead_weeks = int(math.ceil(float(pos["lead_time_days"]) / 7))
cover_weeks = min(lead_weeks + 1, len(f))
required = float(f["forecast"].iloc[:cover_weeks].sum()) + safety
net_requirement = required - available - on_order
order_units = int(math.ceil(net_requirement / moq) * moq) if net_requirement > 0 else 0
arrivals = np.where(np.arange(len(f)) >= lead_weeks, on_order, 0.0)
projected = available - f["forecast"].cumsum().to_numpy() + arrivals
breach = np.flatnonzero(projected < safety)
breach_week = f["week_start_date"].iloc[int(breach[0])].strftime("%Y-%m-%d") if len(breach) else None
order_by_idx = max(int(breach[0]) - lead_weeks, 0) if len(breach) else None
order_by = f["week_start_date"].iloc[order_by_idx].strftime("%Y-%m-%d") if order_by_idx is not None else None
result = pd.DataFrame({
    "week_start_date": f["week_start_date"].dt.strftime("%Y-%m-%d").to_numpy(),
    "forecast_units": f["forecast"].to_numpy(),
    "projected_available_units": np.round(projected, 0),
})
facts = {
    "recommended_order_units": order_units,
    "standard_reorder_quantity": int(pos["reorder_quantity"]),
    "cover_weeks": cover_weeks,
    "on_order_units": int(on_order),
    "below_reorder_point_now": bool(available <= float(pos["reorder_point"])),
    "first_week_below_safety_stock": breach_week,
    "order_by_week": order_by,
}
```

## Writing the Advice

The node response states, in this order:

1. The current position (available units, status, units on order) as of 2026-10-31.
2. The forecast total for the horizon and the confidence label.
3. The recommendation: units to order, the supplier and the order-by week, with the lead time and the expected delivery week.
4. The reason in one sentence (for example "available stock covers about 3 weeks of forecast demand, and the lead time is 6 weeks").
5. Risks: supplier on-time rate, event weeks, short history, shelf life.
6. The closing recommendation wording.

Key figures: recommended order units, standard reorder quantity, weeks of cover, forecast total, order-by week (as a date in `assumptions` or the answer text).
