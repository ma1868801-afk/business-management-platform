# Inventory Policy

- Document ID: KB-POL-13
- Category: Company policy
- Owner: Saad Al-Malki, Inventory Planning Manager (EMP-0013)
- Effective date: 2026-01-01
- Version: 3.1
- Last reviewed: 2026-09-30
- Applies to: Supply chain, stores and Distribution Center
- Classification: Internal

## 1. Objectives

Keep products available for customers while holding as little stock as the service level allows. The inventory team measures availability, overstock, dead stock and losses every week.

## 2. Stock Parameters

Every SKU at every location has four parameters, kept in the inventory records.

| Parameter | Definition |
|---|---|
| Safety stock | Buffer against variation in demand and in supplier delivery time. It is based on the service level of the SKU's ABC class. |
| Reorder point | Demand during the supplier lead time plus safety stock. |
| Reorder quantity | The quantity ordered when the reorder point is reached, rounded up to the supplier's minimum order quantity. |
| Maximum stock level | Reorder point plus reorder quantity. |

Supplier lead times range from 4 to 45 days (see the supplier contracts).

## 3. ABC Classification and Service Levels

SKUs are ranked by net revenue. Class A holds the SKUs that together make the first 80 percent of revenue, class B the next 15 percent and class C the remaining 5 percent. The classification is reviewed every quarter.

| Class | Service level | Safety factor z |
|---|---|---|
| A | 98 percent | 2.05 |
| B | 95 percent | 1.65 |
| C | 90 percent | 1.28 |

Safety stock = z x square root of (lead time in weeks x demand variance + (average weekly demand x lead time variation in weeks) squared). Reorder point = average weekly demand x lead time in weeks + safety stock.

## 4. Stock Status

The status of a stock position is assigned in this order; the first rule that applies wins.

| Order | Status | Rule on available quantity (on hand minus reserved) |
|---|---|---|
| 1 | Out of Stock | At or below 0 |
| 2 | Critical | At or below safety stock |
| 3 | Reorder Now | At or below the reorder point |
| 4 | Overstock | Above the maximum stock level |
| 5 | Healthy | Everything else |

A replenishment order must be raised the same day for Reorder Now and Critical positions. An Out of Stock position is escalated to the Inventory Planning Manager.

## 5. Dead Stock and Markdown

- Dead stock is stock on hand with no completed sale in the last 13 weeks.
- Discontinued SKUs are not reordered. Remaining stock is sold through, then marked down within the discount cap of the line, and finally written off.
- A SKU with declining demand is not replenished above the reorder point without approval of the Inventory Planning Manager.

## 6. Shelf Life

Grocery and Beauty products with a shelf life are issued first-expired-first-out. Stock with less than 25 percent of its shelf life left is marked down or withdrawn. Only products with a shelf life can have an Expiry write-off.

## 7. Stock Adjustments

Adjustments are recorded with one of five reasons: Damage, Expiry, Shrinkage, Count Correction and Display Sample. The Financial Controller reviews adjustments every month. A single adjustment above SAR 10,000 at cost needs the approval of the Head of Supply Chain.

## 8. Counts and Snapshots

- A weekly stock snapshot is taken every Saturday for all locations.
- Each location performs a full count once a year and cycle counts of A-class SKUs every month.
- Differences are booked as Count Correction after the Branch Manager signs the count sheet.

## 9. Forecasting

The Demand Planner forecasts demand up to 13 weeks ahead. Forecasts are used to set reorder points before events such as Ramadan and White Friday (see the promotions calendar, KB-POL-07). Reorder points are changed only by the Inventory Planning Manager.

## 10. Responsibilities

| Role | Responsibility |
|---|---|
| Inventory Planning Manager (Saad Al-Malki) | Owns the parameters, classification and exceptions. |
| Demand Planner (Yara Khoury) | Prepares forecasts. |
| Procurement Manager (Wafa Al-Dosari) | Places purchase orders. |
| Distribution Center Manager (Khalid Al-Mutairi) | Executes receiving, storage and counts at the Distribution Center. |
| Branch Managers | Keep store stock accurate and report damage and losses. |
