# Data Analysis: Seasonality and Calendar Knowledge

- Document ID: DA-08
- Index: data_analysis
- Purpose: how Saudi retail seasons are defined in the data, which patterns to expect, and how to compare seasons correctly. Use it for questions about Ramadan, Eid, Hajj, White Friday, National Day, Founding Day, Back to School, summer, winter, weekends and paydays.

## Season Definitions

Every calendar day has exactly one commercial season, stored in `calendar.season` and copied to `sales_orders.season`. When windows overlap, the season with the highest precedence wins. Precedence from highest to lowest: White Friday, Eid al-Fitr, Hajj and Eid al-Adha, Ramadan, National Day, Founding Day, Back to School, Summer, Winter, Regular. A day with no event is `Regular`. Winter (December to February) applies only to days that no event covers.

Consequences of the precedence rule:

- The last 7 days of Ramadan and the first 3 days of Shawwal count as Eid al-Fitr, so the `Ramadan` season is shorter than the 29 or 30 days of the month.
- In 2026 Founding Day (20 to 23 February) falls inside Ramadan, so those days are Ramadan days.
- In June 2025 the Hajj and Eid al-Adha window replaces the first ten days of Summer.
- All of August belongs to Back to School, so Summer days are the days of June and July that no higher event covers (in 2024 and 2025 the Hajj window removes ten June days).
- White Friday 2026 (20 to 29 November) lies after the end of the data (2026-10-31); no 2026 White Friday sales exist.

## Season Windows by Year

| Year | Season | Start | End | Definition |
|---|---|---|---|---|
| 2024 | Founding Day | 2024-02-20 | 2024-02-23 | 20 to 23 February; public holiday on 22 February |
| 2024 | Ramadan | 2024-03-11 | 2024-04-09 | 1 to 29/30 Ramadan; the last 7 days are classified as Eid al-Fitr by precedence |
| 2024 | Eid al-Fitr | 2024-04-03 | 2024-04-12 | last 7 days of Ramadan plus 1 to 3 Shawwal |
| 2024 | Summer | 2024-06-01 | 2024-08-31 | 1 June to 31 August, lowest precedence among events (August is overridden by Back to School) |
| 2024 | Hajj and Eid al-Adha | 2024-06-11 | 2024-06-20 | Arafat Day minus 4 days to Arafat Day plus 5 days |
| 2024 | Back to School | 2024-08-01 | 2024-09-15 | 1 August to 15 September |
| 2024 | National Day | 2024-09-18 | 2024-09-24 | 18 to 24 September; public holiday on 23 September |
| 2024 | White Friday | 2024-11-22 | 2024-12-01 | Friday one week before White Friday to the Sunday after |
| 2025 | Founding Day | 2025-02-20 | 2025-02-23 | 20 to 23 February; public holiday on 22 February |
| 2025 | Ramadan | 2025-03-01 | 2025-03-29 | 1 to 29/30 Ramadan; the last 7 days are classified as Eid al-Fitr by precedence |
| 2025 | Eid al-Fitr | 2025-03-23 | 2025-04-01 | last 7 days of Ramadan plus 1 to 3 Shawwal |
| 2025 | Hajj and Eid al-Adha | 2025-06-01 | 2025-06-10 | Arafat Day minus 4 days to Arafat Day plus 5 days |
| 2025 | Summer | 2025-06-01 | 2025-08-31 | 1 June to 31 August, lowest precedence among events (August is overridden by Back to School) |
| 2025 | Back to School | 2025-08-01 | 2025-09-15 | 1 August to 15 September |
| 2025 | National Day | 2025-09-18 | 2025-09-24 | 18 to 24 September; public holiday on 23 September |
| 2025 | White Friday | 2025-11-21 | 2025-11-30 | Friday one week before White Friday to the Sunday after |
| 2026 | Ramadan | 2026-02-18 | 2026-03-19 | 1 to 29/30 Ramadan; the last 7 days are classified as Eid al-Fitr by precedence |
| 2026 | Founding Day | 2026-02-20 | 2026-02-23 | 20 to 23 February; public holiday on 22 February |
| 2026 | Eid al-Fitr | 2026-03-13 | 2026-03-22 | last 7 days of Ramadan plus 1 to 3 Shawwal |
| 2026 | Hajj and Eid al-Adha | 2026-05-22 | 2026-05-31 | Arafat Day minus 4 days to Arafat Day plus 5 days |
| 2026 | Summer | 2026-06-01 | 2026-08-31 | 1 June to 31 August, lowest precedence among events (August is overridden by Back to School) |
| 2026 | Back to School | 2026-08-01 | 2026-09-15 | 1 August to 15 September |
| 2026 | National Day | 2026-09-18 | 2026-09-24 | 18 to 24 September; public holiday on 23 September |
| 2026 | White Friday | 2026-11-20 | 2026-11-29 | Friday one week before White Friday to the Sunday after (planning estimate) |

Islamic dates move about 10 to 11 days earlier each Gregorian year, so Ramadan, Eid and Hajj fall on different dates every year. Compare "Ramadan 2025 with Ramadan 2024" using each year's own window, never the same calendar dates. Use `calendar.is_ramadan` and `calendar.is_eid` for the flags and `calendar.season` for the season.

Public holidays (`calendar.is_holiday`, `holiday_name`): Founding Day (22 February), Eid al-Fitr Holiday, Arafat Day, Eid al-Adha Holiday and National Day (23 September).

## Calendar Columns

| Column | Use |
|---|---|
| `date_key` | The date; join to `order_date`. |
| `year`, `quarter`, `month`, `month_name` | Calendar grouping. |
| `week_start_date`, `week_of_year` | Retail weeks start on Sunday. |
| `day_of_week`, `day_name` | 0 is Sunday, 5 is Friday, 6 is Saturday. |
| `is_weekend` | True on Friday and Saturday. |
| `is_holiday`, `holiday_name` | Official public holidays. |
| `season` | One of the ten seasons above. |
| `climate_season` | Winter (December to February), Spring (March to May), Summer (June to September), Autumn (October and November). |
| `is_ramadan`, `is_eid` | Event flags. |
| `is_payday` | True from the 25th to the 28th of each month. |

## Expected Patterns

These patterns are built into the Nakhla data. Verify with a query before stating a number.

| Topic | Expected pattern |
|---|---|
| Weekend | Average daily store net revenue on Friday and Saturday is at least 1.2 times the Sunday to Thursday average outside Ramadan. |
| Payday | Average daily net revenue on days 25 to 28 is at least 1.15 times the average on other days of the same months outside event windows. |
| Ramadan and Grocery | Grocery and Gourmet average daily net revenue in Ramadan is at least 1.4 times its Regular-day average of the same year; its best month contains Ramadan days. |
| White Friday | Total average daily net revenue in the window is at least 1.8 times the Regular-day average of the same year. Consumer Electronics gains at least 5 points of share, and the digital (Online plus Mobile App) share is above its usual level. |
| Cooling | Home Appliances units for cooling and fans in June to August are at least 1.5 times the monthly average of the year. |
| Camping | Sports and Outdoor camping gear in November to February is at least 1.4 times the monthly average. |
| School | Kids and School units for school supplies and backpacks between 1 August and 15 September are at least 1.6 times the monthly average of the year. |
| Fashion | Fashion and Apparel units in Eid al-Fitr are at least 1.4 times the monthly average of the year. |
| Beauty | Beauty and Fragrance units in Eid al-Fitr and in National Day are at least 1.3 times the monthly average of the year. |
| Home Decor | Home Decor and Furnishing units in the four weeks before Ramadan and in White Friday are at least 1.3 times the monthly average of the year. |
| Madinah | MED-QBA has a Ramadan and Hajj uplift at least 1.2 times the chain-wide uplift. |
| Abha and Obhur | ABH-CTY and JED-OBH have a June to August uplift at least 1.2 times their own monthly average (summer tourism). |

## How to Compare Seasons Correctly

1. Compare average daily net revenue, not totals, because seasons differ in length (Founding Day has 4 days, Back to School 46).
2. Use the `Regular` days of the same year as the baseline. This removes growth between years. The uplift is the season average divided by the Regular average.
3. Count days with no orders as zero by starting from `calendar` with a left join (DA-SQL-20).
4. Do not mix years inside one baseline. For a multi-year view, show each year separately and then compare uplifts.
5. For a store question exclude `RYD-DC`; for a channel question include it.
6. Say which days were classified as which season when overlap matters (for example "the Eid al-Fitr days at the end of Ramadan are counted as Eid al-Fitr").
7. Seasonal indexes of months need complete years (DA-PY-06). Season uplifts need only the baseline year.
8. Weekend and payday comparisons are tested with a Welch t-test or Mann-Whitney test on daily values (DA-06, DA-PY-10) only when the user asks for significance.

## SQL Patterns

### DA-SQL-20: Season uplift against Regular days for one product line

Use for "how did Grocery sell during Ramadan compared with normal days". Starts from the calendar so that days without sales count as zero. Change the product line and the year as needed. Remove the category filter for total revenue.

```sql
WITH daily AS (
  SELECT order_date, SUM(line_total) AS revenue
  FROM v_sales_detail
  WHERE status = 'Completed'
    AND category_name = 'Grocery and Gourmet'
    AND year = 2025
  GROUP BY order_date
), by_season AS (
  SELECT c.season,
         COUNT(*) AS days,
         AVG(COALESCE(x.revenue, 0)) AS avg_daily
  FROM calendar c
  LEFT JOIN daily x ON x.order_date = c.date_key
  WHERE c.year = 2025
  GROUP BY c.season
)
SELECT season,
       days,
       ROUND(avg_daily, 2) AS avg_daily_net_revenue_sar,
       ROUND(avg_daily / NULLIF((SELECT avg_daily FROM by_season WHERE season = 'Regular'), 0), 2) AS uplift_vs_regular
FROM by_season
ORDER BY uplift_vs_regular DESC
LIMIT 20;
```

### DA-SQL-21: Daily store revenue with weekend and payday flags

Use for weekend, payday and day-level tests. Returns one row per day of 2025 with in-store net revenue, so weekend and weekday groups can be compared in Pandas. To exclude Ramadan, filter `season <> 'Ramadan'` in Pandas.

```sql
SELECT c.date_key,
       c.day_name,
       c.is_weekend,
       c.is_payday,
       c.season,
       ROUND(COALESCE(SUM(v.line_total), 0), 2) AS store_net_revenue_sar
FROM calendar c
LEFT JOIN v_sales_detail v
       ON v.order_date = c.date_key
      AND v.status = 'Completed'
      AND v.channel = 'In-Store'
WHERE c.year = 2025
GROUP BY c.date_key, c.day_name, c.is_weekend, c.is_payday, c.season
ORDER BY c.date_key;
```

### DA-SQL-22: Monthly units for the seasonal product lines

Use for cooling, camping and school-supply seasonality. Returns monthly units for the three most seasonal lines from January 2024 to October 2026. Product-level seasonality (for example fans only) filters on `peak_season` or `is_seasonal` in `products`, or on `sku`.

```sql
SELECT date_trunc('month', order_date)::date AS order_month,
       category_name,
       SUM(quantity) AS units
FROM v_sales_detail
WHERE status = 'Completed'
  AND category_name IN ('Home Appliances', 'Sports and Outdoor', 'Kids and School')
  AND order_date BETWEEN DATE '2024-01-01' AND DATE '2026-10-31'
GROUP BY date_trunc('month', order_date)::date, category_name
ORDER BY category_name, order_month;
```

### DA-SQL-23: Monthly net revenue by store

Use for location-specific seasonality such as Madinah in Ramadan or Abha in summer. Excludes the Distribution Center. The seasonal index per store is computed in Pandas by dividing each month by the store's own monthly average (the DA-PY-06 method applied to each store).

```sql
SELECT branch_code,
       date_trunc('month', order_date)::date AS order_month,
       ROUND(SUM(line_total), 2) AS net_revenue_sar
FROM v_sales_detail
WHERE status = 'Completed'
  AND branch_code <> 'RYD-DC'
  AND order_date BETWEEN DATE '2024-01-01' AND DATE '2026-10-31'
GROUP BY branch_code, date_trunc('month', order_date)::date
ORDER BY branch_code, order_month;
```

## Answering Seasonal Questions

- Ask which season only when the user's wording is ambiguous ("the holiday season" could mean Ramadan, Eid or White Friday). Otherwise resolve the name with the aliases in RT-07.
- If the user asks for a season that has not happened yet (Ramadan 2027, White Friday 2026), no sales exist. Offer the previous year's pattern or a forecast through the Inventory subgraph.
- Always give the window used, for example "Ramadan 2025 (1 to 22 March, excluding the Eid al-Fitr days at the end)".
