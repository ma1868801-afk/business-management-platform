# Router: Inventory Subgraph Description

- Document ID: RT-03
- Index: router
- Subgraph name: `inventory`

## Purpose

The Inventory subgraph monitors stock and purchasing data and produces demand forecasts. It reads the stock, snapshot, purchase order and supplier data with read-only SQL. It runs a regression forecasting model only when the user asks for a forecast, a projection or a replenishment recommendation that depends on future demand.

## Choose Inventory When the Question Is About

- Current quantities: how many units of a SKU are in stock at a location, stock value, available versus reserved.
- Stock status: out of stock, critical, reorder now, overstock, healthy.
- Replenishment: which items to reorder, reorder points, safety stock, days of cover.
- Slow movers: dead stock, overstock value, discontinued items still in stock.
- Stockout history and weeks with stockouts.
- Purchase orders: open and in-transit orders, late orders, quantities received.
- Supplier delivery performance measured from purchase orders (actual versus expected delivery dates).
- Stock adjustments: damage, expiry, shrinkage, count corrections.
- Demand forecasts for the coming weeks for a SKU, product line or location, and the reorder advice that follows from them.

## Tools and Behavior

| Step | Tool | Rule |
|---|---|---|
| 1 | Inventory RAG | Retrieves SQL rules, regression input guidelines and inventory domain knowledge. |
| 2 | PostgreSQL tool | Read-only SELECT or WITH queries. |
| 3 | Regression model | Only when a forecast is requested. Bypassed for current quantities, status lists, supplier facts and historical sales. |
| 4 | Reorder advice | Added to a forecast when the user asks what or how much to order. |

## Routing Hints

- `forecast_requested`: true when the user asks to forecast, predict, project, estimate future demand or plan quantities for future weeks.
- `horizon_weeks`: number of weeks ahead (1 to 13). Default 8 when the user gives no horizon and asks for a forecast. A month means 4 weeks, a quarter means 13 weeks.

## Typical Questions

- How many units of ELEC-0001 are available at the Distribution Center?
- Which SKUs are out of stock?
- Which items need reordering this week at Riyadh Olaya?
- How much money is tied up in overstock?
- Forecast the demand for AirWhirl Tower Fan for the next 8 weeks.
- Which purchase orders are late?
- Which supplier has the lowest on-time delivery rate?
- Which discontinued SKUs still have stock?

## Do Not Choose Inventory For

- Revenue, margin or customer analytics (Data Analysis).
- What a supplier contract says about penalties, renewals or payment terms (Knowledge Base).
- Requests to create or approve purchase orders (reject: write request).
