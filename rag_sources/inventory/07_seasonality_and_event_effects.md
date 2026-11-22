# Inventory: Seasonality and Event Effects

- Document ID: INV-07
- Index: inventory
- Purpose: how Saudi retail seasons and religious events change demand and stock needs, which products are affected, and how to plan stock before an event that is outside the 13-week forecast horizon.

## Seasons in the Data

Every day has one commercial season (`calendar.season`): Ramadan, Eid al-Fitr, Hajj and Eid al-Adha, White Friday, National Day, Founding Day, Back to School, Summer, Winter or Regular. The windows and the precedence rule are in DA-08. Weeks start on Sunday; a week is flagged as a Ramadan, Eid or White Friday week when any of its days is in that season.

Hijri events (Ramadan, Eid al-Fitr, Hajj and Eid al-Adha) move about 11 days earlier each year. Compare an event with the same event in the previous year, never with the same calendar dates.

## Demand Effects by Product

| Event or season | Products affected | Expected effect |
|---|---|---|
| Ramadan | Grocery and Gourmet (dates, Ramadan baskets, staples) | Average daily revenue at least 1.4 times the Regular-day level; the peak weeks of Ramadan SKUs are at least 2 times their off-season median. |
| Four weeks before Ramadan | Home Decor and Furnishing | At least 1.3 times the monthly average (hosting and decoration). |
| Eid al-Fitr | Fashion and Apparel; Beauty and Fragrance | Fashion at least 1.4 times and Beauty at least 1.3 times the monthly average. |
| Hajj and Eid al-Adha | Madinah store (`MED-QBA`) and gifts | The Madinah uplift is at least 1.2 times the chain-wide uplift. |
| White Friday | Consumer Electronics; Home Decor and Furnishing; online orders | Total daily revenue at least 1.8 times the Regular level; Electronics gains at least 5 points of share; Home Decor at least 1.3 times. |
| National Day | Beauty and Fragrance | At least 1.3 times the monthly average. |
| Back to School (1 August to 15 September) | Kids and School (backpacks, school supplies) | At least 1.6 times the monthly average. |
| Summer (June to August) | Home Appliances (fans, air conditioners); Abha and Obhur stores | Cooling units at least 1.5 times the monthly average; `ABH-CTY` and `JED-OBH` at least 1.2 times their own monthly average. |
| Winter (November to February) | Sports and Outdoor (camping gear, tents) | At least 1.4 times the monthly average. |
| Weekends and paydays | All stores | Friday and Saturday at least 1.2 times, days 25 to 28 at least 1.15 times the other days. |

Seasonal SKUs (31 in total, among them dates, Ramadan baskets, cooling fans, camping tents and school bags) have `is_seasonal = true` and a `peak_season`. For these SKUs the weeks inside the peak season are at least 2 times the off-season median.

## Upcoming Events (Planning Estimates)

The data ends on 2026-10-31 and the forecast starts on 2026-11-01. Event dates after October 2026 are planning estimates: Islamic dates depend on moon sighting and can shift by a day.

| Event | Estimated window | Position relative to the 13-week horizon (2026-11-01 to 2027-01-30) |
|---|---|---|
| White Friday 2026 | 20 to 29 November 2026 | Inside the horizon (weeks starting 15, 22 and 29 November) |
| Winter | December 2026 to February 2027 | Inside (camping demand rises) |
| Ramadan 2027 | About 8 February to 9 March 2027 | After the horizon; order lead times fall inside it |
| Founding Day 2027 | 20 to 23 February 2027 | After the horizon |
| Eid al-Fitr 2027 | About 3 to 12 March 2027 | After the horizon |
| Hajj and Eid al-Adha 2027 | About 11 to 20 May 2027 | After the horizon |

## Planning Stock for an Event Beyond the Horizon

The regression tool forecasts at most 13 weeks. For a question such as "how much should we order for the next Ramadan", the subgraph does the following:

1. Say when the event starts and that it lies after the 13-week horizon.
2. Compute the order-by date: event start minus the supplier lead time, minus one week for receiving and one week as a buffer. For a supplier with a 30-day lead time and Ramadan starting about 8 February 2027, the order-by date is in early January 2027, which is inside the horizon.
3. Estimate the event demand from last year's event: the units sold in the same event window of 2026 (Ramadan 2026 ran from 18 February to 19 March; its last seven days, 13 to 19 March, and the first days of Shawwal, to 22 March, are classified as Eid al-Fitr), scaled by the trend, which is the ratio of the last 13 weeks to the same 13 weeks of the previous year.
4. Add safety stock and subtract available stock and open purchase orders, following INV-09.
5. State clearly that this is an estimate based on last year's event, with Low or Medium confidence, and show the 13-week forecast for the weeks before the event separately.

Never extend the regression model beyond 13 weeks and never present the event estimate as a model forecast.

## Reading Event Effects in Data

- Use `v_weekly_product_demand.is_ramadan_week` and `is_eid_week` for weekly flags; White Friday weeks come from `calendar.season = 'White Friday'`.
- A single week can contain days of two seasons (for example the last days of Ramadan and the first days of Eid). The flags treat the week as both.
- Compare event weeks with the average of the Regular weeks of the same year, not with the previous week.
- When a SKU shows no uplift in an event where it should, check for stockout weeks (INV-SQL-09, INV-SQL-15) before concluding that demand was low.
