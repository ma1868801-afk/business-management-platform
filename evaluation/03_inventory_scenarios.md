# Evaluation Scenarios: Inventory

- Document ID: EV-INV
- Suite: inventory
- Scenarios: 46 (EV-INV-001 to EV-INV-046)
- Languages: 24 English, 22 Arabic, 0 mixed
- Difficulty: 7 easy, 23 medium, 16 hard
- Fields and grading rules: `00_index.md` and `docs/06_evaluation_plan.md`

## Purpose

Checks stock, purchase order, lifecycle and forecasting questions answered by the Inventory subgraph. The regression tool must run only when a forecast is requested. Forecast answers are graded on structure, horizon rules, confidence label and warnings, not on exact numbers.

## Categories

| Category | Scenarios |
|---|---|
| stock_status | 8 |
| purchase_orders | 7 |
| lifecycle_dead_stock | 6 |
| forecast | 12 |
| reorder_advice | 6 |
| edge_case | 7 |

## Category: stock_status

### EV-INV-001

```yaml
id: EV-INV-001
suite: inventory
category: stock_status
language: en
difficulty: easy
prompt: "What quantity of ELEC-0001 is available at RYD-DC?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "on-hand and available quantity equal the oracle for RYD-DC"
      - "states that stock is as of 2026-10-31"
basis: {type: oracle_sql, reference: INV-SQL-01}
```

### EV-INV-002

```yaml
id: EV-INV-002
suite: inventory
category: stock_status
language: ar
difficulty: easy
prompt: "ما المنتجات النافدة من المخزون في أي موقع؟"
prompt_en: "Which products are out of stock at any location?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "lists positions with status Out of Stock (available quantity 0 or below)"
      - "at least 5 positions"
      - "each with location and SKU"
basis: {type: oracle_and_guarantee, reference: "INV-SQL-02; G-31"}
```

### EV-INV-003

```yaml
id: EV-INV-003
suite: inventory
category: stock_status
language: en
difficulty: easy
prompt: "Give me the value of our inventory at cost, split by product line."
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include: ["eight product lines", "value is on hand times unit cost in SAR"]
basis: {type: oracle_sql, reference: INV-SQL-03}
```

### EV-INV-004

```yaml
id: EV-INV-004
suite: inventory
category: stock_status
language: ar
difficulty: medium
prompt: "ما المنتجات التي في حالة حرجة أو تحتاج إلى إعادة طلب في مركز التوزيع؟"
prompt_en: "Which products are Critical or at Reorder Now at the Distribution Center?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "lists status Critical and Reorder Now separately"
      - "stock status order applied: Out of Stock, Critical, Reorder Now"
basis: {type: oracle_and_guarantee, reference: "INV-SQL-04; G-31"}
```

### EV-INV-005

```yaml
id: EV-INV-005
suite: inventory
category: stock_status
language: en
difficulty: medium
prompt: "How much money is tied up in overstock by product line?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "excess units are available quantity above the maximum stock level"
      - "value at cost per product line"
basis: {type: oracle_and_guarantee, reference: "INV-SQL-05; G-31"}
```

### EV-INV-006

```yaml
id: EV-INV-006
suite: inventory
category: stock_status
language: ar
difficulty: medium
prompt: "أي عشرين منتجًا ستنفد مخزوناتها أولًا؟"
prompt_en: "Which twenty products will run out of stock first?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "weeks of cover = available units divided by average weekly units of the last 8 complete weeks"
      - "Discontinued SKUs are left out"
      - "regression is not used"
basis: {type: oracle_sql, reference: INV-SQL-06}
```

### EV-INV-007

```yaml
id: EV-INV-007
suite: inventory
category: stock_status
language: en
difficulty: easy
prompt: "How many Home Appliances units and what value do we hold at each location?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "nine locations or those that stock Home Appliances"
      - "units on hand and value at cost"
basis: {type: oracle_sql, reference: INV-SQL-13}
```

### EV-INV-008

```yaml
id: EV-INV-008
suite: inventory
category: stock_status
language: ar
difficulty: medium
prompt: "كم عدد مراكز المخزون في كل حالة؟"
prompt_en: "How many stock positions are in each status?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "five statuses: Out of Stock, Critical, Reorder Now, Overstock, Healthy"
      - "at least 60 percent of positions are Healthy"
basis: {type: oracle_and_guarantee, reference: "INV-SQL-02; G-31"}
```

## Category: purchase_orders

### EV-INV-009

```yaml
id: EV-INV-009
suite: inventory
category: purchase_orders
language: en
difficulty: easy
prompt: "List the purchase orders that are past their expected delivery date."
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "overdue means status Open or In Transit with an expected delivery date before 2026-10-31"
      - "shows days overdue and supplier"
basis: {type: oracle_and_guarantee, reference: "INV-SQL-11; G-36"}
```

### EV-INV-010

```yaml
id: EV-INV-010
suite: inventory
category: purchase_orders
language: ar
difficulty: medium
prompt: "أي مورد يلتزم بمواعيد التسليم بأقل نسبة؟"
prompt_en: "Which supplier delivers on time least often?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "measured on-time rate from Received and Partially Received orders"
      - "lowest supplier is SUP-08 or SUP-04, each within 3 points of 82.5 and 84.0 percent"
basis: {type: oracle_and_guarantee, reference: "INV-SQL-18; G-35"}
```

### EV-INV-011

```yaml
id: EV-INV-011
suite: inventory
category: purchase_orders
language: en
difficulty: medium
prompt: "How many purchase orders from SUP-04 arrived late, and by how many days on average?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "late means actual delivery after expected delivery"
      - "count and average delay equal the oracle"
basis: {type: oracle_sql, reference: INV-SQL-19}
```

### EV-INV-012

```yaml
id: EV-INV-012
suite: inventory
category: purchase_orders
language: ar
difficulty: medium
prompt: "ما الكمية المطلوبة من GROC-0001 لدى الموردين ولم تصل بعد؟"
prompt_en: "What quantity of GROC-0001 has been ordered from suppliers and has not arrived yet?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "sums quantity ordered minus quantity received on Open, In Transit and Partially Received orders"
basis: {type: oracle_sql, reference: INV-SQL-20}
```

### EV-INV-013

```yaml
id: EV-INV-013
suite: inventory
category: purchase_orders
language: en
difficulty: medium
prompt: "Which purchase orders are open for the Distribution Center and when are they expected?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "Open and In Transit orders"
      - "expected delivery date = order date plus supplier lead time"
basis:
  type: oracle_and_guarantee
  reference: "INV-SQL-11 without the overdue filter; G-36"
```

### EV-INV-014

```yaml
id: EV-INV-014
suite: inventory
category: purchase_orders
language: ar
difficulty: hard
prompt: "ما متوسط مدة التوريد الفعلية مقارنة بمدة التوريد المتفق عليها للمورد SUP-07؟"
prompt_en: "What is the average actual lead time compared with the agreed lead time for supplier SUP-07?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "agreed lead time is 4 days"
      - "actual lead time is measured from order date to actual delivery date"
basis: {type: oracle_sql, reference: INV-SQL-19}
```

### EV-INV-015

```yaml
id: EV-INV-015
suite: inventory
category: purchase_orders
language: en
difficulty: medium
prompt: "Which suppliers have partially received purchase orders?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "a line is partially received when quantity received is below quantity ordered"
basis:
  type: oracle_sql
  reference: "purchase_order_lines with status Partially Received"
```

## Category: lifecycle_dead_stock

### EV-INV-016

```yaml
id: EV-INV-016
suite: inventory
category: lifecycle_dead_stock
language: ar
difficulty: medium
prompt: "ما هي المنتجات الراكدة التي لم تُبع خلال آخر 13 أسبوعًا؟"
prompt_en: "Which dead-stock products have not sold in the last 13 weeks?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "window is 2026-08-03 to 2026-10-31"
      - "six SKUs: ELEC-0013, FASH-0014, SPRT-0014, HOME-0014, FASH-0013, HOME-0013"
      - "value at cost"
basis: {type: oracle_and_guarantee, reference: "INV-SQL-07; G-32"}
```

### EV-INV-017

```yaml
id: EV-INV-017
suite: inventory
category: lifecycle_dead_stock
language: en
difficulty: easy
prompt: "Do we still have stock of products that have been discontinued?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "at least 3 discontinued SKUs still hold stock"
      - "stock is run-off and is excluded from reorder lists"
basis: {type: oracle_and_guarantee, reference: "INV-SQL-08; G-31"}
```

### EV-INV-018

```yaml
id: EV-INV-018
suite: inventory
category: lifecycle_dead_stock
language: ar
difficulty: medium
prompt: "ما المنتجات الجديدة التي أُطلقت في 2026 وكم أسبوعًا من المبيعات لكل منها؟"
prompt_en: "Which products were launched in 2026 and how many weeks of sales does each have?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "four new SKUs: ELEC-0015, APPL-0015, BEAU-0015, KIDS-0015"
      - "each has fewer than 26 weeks of sales"
basis: {type: oracle_and_guarantee, reference: "INV-SQL-17; G-32"}
```

### EV-INV-019

```yaml
id: EV-INV-019
suite: inventory
category: lifecycle_dead_stock
language: en
difficulty: medium
prompt: "How much did we lose to damage, expiry and shrinkage in the last 12 months?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "period is 2025-11-01 to 2026-10-31"
      - "losses are negative cost impact by reason"
basis: {type: oracle_sql, reference: INV-SQL-12}
```

### EV-INV-020

```yaml
id: EV-INV-020
suite: inventory
category: lifecycle_dead_stock
language: ar
difficulty: medium
prompt: "أي المنتجات سُجلت لها تسويات بسبب انتهاء الصلاحية؟"
prompt_en: "Which products have stock adjustments because of expiry?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include: ["only products with a shelf life appear (Grocery and Beauty)"]
basis:
  type: oracle_and_guarantee
  reference: "stock_adjustments where reason = Expiry; G-37"
```

### EV-INV-021

```yaml
id: EV-INV-021
suite: inventory
category: lifecycle_dead_stock
language: en
difficulty: medium
prompt: "Which products ran out of stock most often at the Distribution Center in 2025?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "counts weekly snapshots with stockout days above zero"
      - "at least 12 SKUs have three or more stockout weeks"
basis: {type: oracle_and_guarantee, reference: "INV-SQL-09; G-33"}
```

## Category: forecast

### EV-INV-022

```yaml
id: EV-INV-022
suite: inventory
category: forecast
language: en
difficulty: medium
prompt: "Forecast demand for the AirWhirl Tower Fan for the next 8 weeks."
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 8}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "eight weekly forecasts from week 2026-11-01 to week 2026-12-20"
      - "each week has a lower and an upper bound"
      - "total, peak week, model name, confidence label and holdout WAPE are stated"
      - "says expected demand, not sales"
basis:
  type: oracle_and_guarantee
  reference: "INV-SQL-14; INV-PY-01 to INV-PY-06; G-38"
```

### EV-INV-023

```yaml
id: EV-INV-023
suite: inventory
category: forecast
language: ar
difficulty: hard
prompt: "كم وحدة من Qassim Gold Khalas Dates 1kg يجب أن نطلب لرمضان القادم؟"
prompt_en: "How many units of Qassim Gold Khalas Dates 1kg should we order for the next Ramadan?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 13}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "horizon is clamped to 13 weeks and the answer says so"
      - "Ramadan 2027 starts about 8 February 2027, after the horizon"
      - "order-by date is about 2027-01-21 (event start minus 4 days lead time minus 2 weeks)"
      - "event estimate is based on Ramadan 2026 and is labelled Low or Medium confidence, not a model forecast"
basis:
  type: rule
  reference: "INV-07 Planning Stock for an Event Beyond the Horizon; INV-05"
```

### EV-INV-024

```yaml
id: EV-INV-024
suite: inventory
category: forecast
language: en
difficulty: medium
prompt: "What unit demand do you expect for Beauty and Fragrance over the next four weeks?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 4}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "line-level series, horizon 4 weeks from 2026-11-01"
      - "National Day and Eid effects are not inside the horizon"
basis:
  type: oracle_and_guarantee
  reference: "INV-SQL-16; INV-PY-03; G-38"
```

### EV-INV-025

```yaml
id: EV-INV-025
suite: inventory
category: forecast
language: ar
difficulty: hard
prompt: "ما توقعات الطلب على الإلكترونيات خلال أسابيع الجمعة البيضاء؟"
prompt_en: "What is the demand forecast for electronics during the White Friday weeks?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 8}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "White Friday 2026 is a planning estimate of 20 to 29 November"
      - "weeks starting 2026-11-15, 2026-11-22 and 2026-11-29 are flagged as White Friday weeks"
      - "the answer says the dates are estimates"
basis:
  type: rule
  reference: "INV-07 Upcoming Events; INV-05 Sanity Checks"
```

### EV-INV-026

```yaml
id: EV-INV-026
suite: inventory
category: forecast
language: en
difficulty: medium
prompt: "Forecast demand for the TrailNest 4-Person Camping Tent for the next 12 weeks."
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 12}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - SPRT-0001
      - "horizon 12 weeks from 2026-11-01 to 2027-01-23"
      - "winter camping peak is reflected"
basis: {type: oracle_and_guarantee, reference: "INV-SQL-14; G-38"}
```

### EV-INV-027

```yaml
id: EV-INV-027
suite: inventory
category: forecast
language: ar
difficulty: hard
prompt: "توقع مبيعات BreezeMax Split AC 24000 BTU في فرع جدة التحلية للأسابيع الأربعة القادمة."
prompt_en: "Forecast sales of the BreezeMax Split AC 24000 BTU at the Jeddah Tahlia store for the next four weeks."
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 4}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "location-level series for JED-THL and APPL-0002"
      - "off-season level for cooling products in November"
basis: {type: oracle_sql, reference: "INV-SQL-14 with a location filter"}
note: "Phase 2 dependency: JED-THL must hold a stock position and sales history for APPL-0002."
```

### EV-INV-028

```yaml
id: EV-INV-028
suite: inventory
category: forecast
language: en
difficulty: medium
prompt: "Forecast demand for the next 6 months for GROC-0004."
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 13}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "six months is 26 weeks, so the horizon is clamped to 13 weeks and the answer says so"
basis: {type: rule, reference: "RT-05 Hints; 02_architecture section 6.3"}
```

### EV-INV-029

```yaml
id: EV-INV-029
suite: inventory
category: forecast
language: ar
difficulty: hard
prompt: "توقع الطلب على المنتج الجديد HomeSense Smart Hub Gen 2 للأسابيع الثمانية القادمة."
prompt_en: "Forecast demand for the new product HomeSense Smart Hub Gen 2 for the next eight weeks."
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 8}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "ELEC-0015 launched on 2026-05-17 and has fewer than 26 weeks of sales"
      - "cold-start estimate with a range and Low confidence"
basis:
  type: rule
  reference: "INV-04 history classes; INV-05 confidence label"
```

### EV-INV-030

```yaml
id: EV-INV-030
suite: inventory
category: forecast
language: en
difficulty: medium
prompt: "Forecast demand for the Marasim Evening Clutch."
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 8}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "FASH-0014 is Discontinued since 2026-05-31"
      - "no forecast is produced"
      - "offers the remaining stock run-off instead"
basis:
  type: rule
  reference: "INV-05 Explaining a Forecast: never forecast a Discontinued SKU"
```

### EV-INV-031

```yaml
id: EV-INV-031
suite: inventory
category: forecast
language: ar
difficulty: medium
prompt: "توقع الطلب على كرة القدم PlayZone Football Size 5 للأسابيع الثمانية القادمة."
prompt_en: "Forecast demand for the PlayZone Football Size 5 for the next eight weeks."
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 8}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "SPRT-0013 has lifecycle status Declining"
      - "forecast is given with a warning that demand is falling and stock should not be built"
basis: {type: rule, reference: "INV-06 Lifecycle"}
```

### EV-INV-032

```yaml
id: EV-INV-032
suite: inventory
category: forecast
language: en
difficulty: hard
prompt: "Forecast demand for Qassim Gold Khalas Dates 1kg for the next 4 weeks, assuming we run a promotion."
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 4}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "the promotion assumption is passed to the model as planned"
      - "the answer states the assumption"
basis: {type: rule, reference: "INV-04 assumptions; INV-05 features"}
```

### EV-INV-033

```yaml
id: EV-INV-033
suite: inventory
category: forecast
language: ar
difficulty: hard
prompt: "هل نتوقع نفاد HomeSense Smart Speaker قبل وصول الطلبية القادمة؟"
prompt_en: "Do we expect the HomeSense Smart Speaker to run out before the next order arrives?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 4}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "compares forecast demand over the supplier lead time with available quantity and open purchase orders"
      - "ELEC-0010 supplier SUP-01 has a 7-day lead time"
basis: {type: rule, reference: "INV-09 Reorder Advice Rules"}
```

## Category: reorder_advice

### EV-INV-034

```yaml
id: EV-INV-034
suite: inventory
category: reorder_advice
language: en
difficulty: hard
prompt: "How many units of APPL-0001 should we order now?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 8}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "accounts for the 21-day lead time of SUP-04 and its minimum order quantity of 60"
      - "quantity is rounded up to a multiple of the minimum order quantity"
      - "subtracts available stock and open purchase orders"
      - "does not create an order"
basis: {type: rule, reference: "INV-09; INV-PY-08"}
```

### EV-INV-035

```yaml
id: EV-INV-035
suite: inventory
category: reorder_advice
language: ar
difficulty: hard
prompt: "هل نقطة إعادة الطلب للمنتج GROC-0005 في مركز التوزيع كافية؟"
prompt_en: "Is the reorder point of GROC-0005 at the Distribution Center adequate?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres, pandas]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "compares the stored reorder point with the calculated value from demand, lead time and supplier delay"
      - "states that policy changes are decided by the planning team"
basis: {type: rule, reference: "INV-06 INV-PY-07"}
```

### EV-INV-036

```yaml
id: EV-INV-036
suite: inventory
category: reorder_advice
language: en
difficulty: hard
prompt: "Which products should we reorder now at the Distribution Center, with suggested quantities?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 8}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "lists Critical and Reorder Now positions ordered by urgency"
      - "quantities are rounded to the minimum order quantity"
      - "Discontinued SKUs are excluded"
basis:
  type: oracle_and_guarantee
  reference: "INV-SQL-04; INV-PY-08; G-31"
```

### EV-INV-037

```yaml
id: EV-INV-037
suite: inventory
category: reorder_advice
language: ar
difficulty: hard
prompt: "ما مخزون الأمان المناسب للمنتج SoundArc Wireless Earbuds؟"
prompt_en: "What is the appropriate safety stock for the SoundArc Wireless Earbuds?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres, pandas]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "ELEC-0006 supplier SUP-01"
      - "formula uses the ABC class service level (A 98, B 95, C 90 percent)"
      - "weekly demand variation and lead time variation are both used"
basis:
  type: rule
  reference: "INV-06 Safety Stock and Reorder Point Formulas"
```

### EV-INV-038

```yaml
id: EV-INV-038
suite: inventory
category: reorder_advice
language: en
difficulty: hard
prompt: "How would safety stock change if supplier SUP-08 delivered late more often?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "higher lead time variation raises safety stock"
      - "uses the measured delay statistics of SUP-08"
      - "does not change any stored parameter"
basis: {type: rule, reference: "INV-06; INV-SQL-19"}
```

### EV-INV-039

```yaml
id: EV-INV-039
suite: inventory
category: reorder_advice
language: ar
difficulty: hard
prompt: "توقع الطلب خلال الأسابيع الثمانية القادمة للمنتج الذي نفد أكثر من غيره في مركز التوزيع خلال 2025، مع مراعاة أسابيع النفاد."
prompt_en: "Forecast demand for the next eight weeks for the product that ran out most often at the Distribution Center in 2025, taking the stockout weeks into account."
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 8}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "first finds the SKU with the most stockout weeks in 2025"
      - "weeks limited by stockouts are treated as censored and adjusted before fitting"
      - "the notes report the share of adjusted weeks and its effect on the confidence label"
basis:
  type: oracle_and_guarantee
  reference: "INV-SQL-09; INV-SQL-15; INV-PY-02; G-33"
```

## Category: edge_case

### EV-INV-040

```yaml
id: EV-INV-040
suite: inventory
category: edge_case
language: en
difficulty: hard
prompt: "Which products are in stock at the Abha City Express store but not at the Distribution Center?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "result is empty because the Distribution Center holds all 120 SKUs"
basis: {type: oracle_and_guarantee, reference: "INV-SQL-21; G-30"}
```

### EV-INV-041

```yaml
id: EV-INV-041
suite: inventory
category: edge_case
language: ar
difficulty: medium
prompt: "كم وحدة نُقلت من مركز التوزيع إلى فرع المدينة المنورة الشهر الماضي؟"
prompt_en: "How many units were transferred from the Distribution Center to the Madinah store last month?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "states that transfers are not recorded as separate movements"
      - "does not give an estimate"
basis: {type: rule, reference: "INV-06 Network and Stock Positions"}
```

### EV-INV-042

```yaml
id: EV-INV-042
suite: inventory
category: edge_case
language: en
difficulty: medium
prompt: "How many sales did we lose because products were out of stock?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "states that lost sales and unmet demand cannot be measured from the data"
      - "offers stockout days as an alternative"
basis: {type: rule, reference: "INV-06 Inventory Measures"}
```

### EV-INV-043

```yaml
id: EV-INV-043
suite: inventory
category: edge_case
language: ar
difficulty: easy
prompt: "اعرض تاريخ المخزون الأسبوعي للمنتج GROC-0001 خلال آخر ستة أشهر."
prompt_en: "Show the weekly stock history of GROC-0001 over the last six months."
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "26 Saturday snapshots from 2026-05-09 to 2026-10-31"
      - "on-hand units and stockout days"
basis: {type: oracle_sql, reference: INV-SQL-10}
```

### EV-INV-044

```yaml
id: EV-INV-044
suite: inventory
category: edge_case
language: en
difficulty: hard
prompt: "What will our stock of GROC-0001 be on 2027-03-01?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 13}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "the date is 17 weeks away and the horizon is clamped to 13 weeks (to 2027-01-30)"
      - "offers a projection to the end of the horizon using open purchase orders"
basis: {type: rule, reference: "RT-05 Hints; 02_architecture section 8"}
```

### EV-INV-045

```yaml
id: EV-INV-045
suite: inventory
category: edge_case
language: ar
difficulty: medium
prompt: "كم تبلغ قيمة المخزون الراكد بسعر التكلفة؟"
prompt_en: "What is the value of dead stock at cost?"
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "sums stock value of SKUs with no Completed sale in the last 13 weeks"
      - "states the window 2026-08-03 to 2026-10-31"
basis: {type: oracle_and_guarantee, reference: "INV-SQL-07; G-32"}
```

### EV-INV-046

```yaml
id: EV-INV-046
suite: inventory
category: edge_case
language: en
difficulty: hard
prompt: "Compare the stock cover of the Nakhla Select Ramadan Essentials Basket with its shelf life."
expected:
  route:
    decision: route
    subgraphs: [inventory]
    hints:
      inventory: {forecast_requested: false}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "GROC-0003 has a shelf life of 180 days"
      - "flags cover above the shelf life as a risk"
basis:
  type: rule
  reference: "INV-06 Product Lines and Stock Characteristics"
```
