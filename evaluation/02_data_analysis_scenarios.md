# Evaluation Scenarios: Data Analysis

- Document ID: EV-DA
- Suite: data_analysis
- Scenarios: 56 (EV-DA-001 to EV-DA-056)
- Languages: 29 English, 27 Arabic, 0 mixed
- Difficulty: 7 easy, 37 medium, 12 hard
- Fields and grading rules: `00_index.md` and `docs/06_evaluation_plan.md`

## Purpose

Checks sales questions answered by the Data Analysis subgraph: plain extractions where Pandas is bypassed, rankings and growth, seasonality, customer analytics, targets, returns, promotions, hypothesis tests and edge cases. Numeric answers are compared with the oracle query named in the basis; qualitative expectations come from the dataset guarantees G-01 to G-38.

## Categories

| Category | Scenarios |
|---|---|
| aggregate_bypass | 10 |
| ranking | 6 |
| growth_trend | 4 |
| seasonality | 10 |
| customer_analytics | 6 |
| targets_returns_promotions | 6 |
| hypothesis_test | 8 |
| edge_case | 6 |

## Category: aggregate_bypass

### EV-DA-001

```yaml
id: EV-DA-001
suite: data_analysis
category: aggregate_bypass
language: en
difficulty: easy
prompt: "What were our total net sales for calendar year 2025?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: en
    must_include:
      - "figure equals the oracle for 2025-01-01 to 2025-12-31"
      - "states that revenue excludes VAT and covers Completed orders"
basis: {type: oracle_sql, reference: DA-SQL-01}
```

### EV-DA-002

```yaml
id: EV-DA-002
suite: data_analysis
category: aggregate_bypass
language: ar
difficulty: easy
prompt: "كم بلغ عدد الطلبات المكتملة في أكتوبر 2026 ومتوسط قيمة الطلب؟"
prompt_en: "How many Completed orders were there in October 2026, and what was the average order value?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: ar
    must_include:
      - "order count and average order value equal the oracle for 2026-10-01 to 2026-10-31"
      - "average order value excludes VAT"
basis: {type: oracle_sql, reference: DA-SQL-02}
```

### EV-DA-003

```yaml
id: EV-DA-003
suite: data_analysis
category: aggregate_bypass
language: en
difficulty: easy
prompt: "How many new customer accounts were opened in 2025?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: en
    must_include:
      - "count equals the oracle"
      - "count is at least 1,200 (at least 100 registrations per month)"
basis:
  type: oracle_and_guarantee
  reference: "customers.registration_date count; G-22"
```

### EV-DA-004

```yaml
id: EV-DA-004
suite: data_analysis
category: aggregate_bypass
language: ar
difficulty: medium
prompt: "اعرض أكبر عشرة طلبات في أكتوبر 2026 من حيث القيمة."
prompt_en: "Show the ten largest orders of October 2026 by value."
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: ar
    must_include:
      - "ten rows ordered by order value"
      - "orders are identified by order number"
    must_not_include: ["customer full names", "customer email addresses"]
basis: {type: oracle_sql, reference: DA-SQL-03}
```

### EV-DA-005

```yaml
id: EV-DA-005
suite: data_analysis
category: aggregate_bypass
language: en
difficulty: medium
prompt: "What is the revenue split by sales channel in 2025?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: en
    must_include:
      - "four channels: In-Store, Online, Mobile App, B2B"
      - "Online plus Mobile App share is about 19 percent"
      - "B2B share is between 6 and 9 percent"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-07; G-11"}
```

### EV-DA-006

```yaml
id: EV-DA-006
suite: data_analysis
category: aggregate_bypass
language: ar
difficulty: easy
prompt: "ما هو صافي الإيرادات لكل فئة منتجات في عام 2025؟"
prompt_en: "What is the net revenue of each product line in 2025?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: ar
    must_include:
      - "eight product lines"
      - "Consumer Electronics has the highest net revenue"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-05; G-13"}
```

### EV-DA-007

```yaml
id: EV-DA-007
suite: data_analysis
category: aggregate_bypass
language: en
difficulty: medium
prompt: "Show net revenue by store for 2025."
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: en
    must_include:
      - "eight stores listed"
      - "RYD-DC is excluded or labelled as carrying Online, Mobile App and B2B sales"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-06; G-12"}
```

### EV-DA-008

```yaml
id: EV-DA-008
suite: data_analysis
category: aggregate_bypass
language: ar
difficulty: medium
prompt: "كم طلبًا ملغيًا كان في عام 2025 وما نسبته من إجمالي الطلبات؟"
prompt_en: "How many orders were cancelled in 2025 and what share of all orders is that?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: ar
    must_include:
      - "count and share equal the oracle"
      - "cancellations are more frequent online and in the app than in stores"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-30; G-07"}
```

### EV-DA-009

```yaml
id: EV-DA-009
suite: data_analysis
category: aggregate_bypass
language: en
difficulty: easy
prompt: "How much did we sell last month?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: en
    must_include:
      - "period is 2026-10-01 to 2026-10-31"
      - "metric is stated as net revenue"
      - "scope is stated as all locations"
basis: {type: oracle_sql, reference: DA-SQL-02}
```

### EV-DA-010

```yaml
id: EV-DA-010
suite: data_analysis
category: aggregate_bypass
language: ar
difficulty: medium
prompt: "ابحث عن منتجات العلامة التجارية TrailNest واعرض صافي إيراداتها في عام 2025."
prompt_en: "Find the products of the brand TrailNest and show their net revenue in 2025."
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: ar
    must_include:
      - "TrailNest products are found by brand: SPRT-0001 to SPRT-0004"
      - "net revenue per product for 2025-01-01 to 2025-12-31 equals the oracle"
basis: {type: oracle_sql, reference: "DA-SQL-29 then DA-SQL-08 pattern"}
```

## Category: ranking

### EV-DA-011

```yaml
id: EV-DA-011
suite: data_analysis
category: ranking
language: en
difficulty: medium
prompt: "Order our eight stores from best to worst by 2025 net revenue."
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "order: RYD-OLY, JED-THL, RYD-MLQ, DMM-FSL, KHB-COR, MED-QBA, JED-OBH, ABH-CTY"
      - "RYD-DC is excluded"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-06; DA-PY-02; G-12"}
```

### EV-DA-012

```yaml
id: EV-DA-012
suite: data_analysis
category: ranking
language: ar
difficulty: medium
prompt: "أي فئة منتجات حققت أعلى صافي إيرادات في 2025 وأي فئة باعت أكبر عدد من الوحدات؟"
prompt_en: "Which product line had the highest net revenue in 2025, and which sold the most units?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "Consumer Electronics has the highest net revenue"
      - "Grocery and Gourmet has the highest units"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-05; G-13"}
```

### EV-DA-013

```yaml
id: EV-DA-013
suite: data_analysis
category: ranking
language: en
difficulty: medium
prompt: "Which product line has the highest gross margin percentage and which has the lowest?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include: ["Beauty and Fragrance highest", "Consumer Electronics lowest"]
basis: {type: oracle_and_guarantee, reference: "DA-SQL-09; G-13"}
```

### EV-DA-014

```yaml
id: EV-DA-014
suite: data_analysis
category: ranking
language: ar
difficulty: hard
prompt: "ما المنتجات التي تشكل 80 في المئة من صافي إيرادات عام 2025؟"
prompt_en: "Which products make up 80 percent of net revenue in 2025?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "Pareto classification: class A holds the SKUs that together make the first 80 percent of revenue"
      - "lists the class A SKUs with their share and cumulative share"
basis: {type: oracle_sql, reference: "DA-SQL-08 pattern; DA-PY-07"}
```

### EV-DA-015

```yaml
id: EV-DA-015
suite: data_analysis
category: ranking
language: en
difficulty: medium
prompt: "Which business customers bought the most in 2025?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "ranks the contract accounts CUST-B001 to CUST-B012 by net revenue"
      - "business names may be shown"
basis: {type: oracle_sql, reference: DA-SQL-28}
```

### EV-DA-016

```yaml
id: EV-DA-016
suite: data_analysis
category: ranking
language: ar
difficulty: medium
prompt: "رتّب المواقع حسب نسبة تحقيق الهدف في أكتوبر 2026."
prompt_en: "Rank the locations by target attainment in October 2026."
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "attainment is net revenue divided by monthly target"
      - "at least two locations are below 100 percent and at least two meet the target"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-12; DA-PY-09; G-29"}
```

## Category: growth_trend

### EV-DA-017

```yaml
id: EV-DA-017
suite: data_analysis
category: growth_trend
language: en
difficulty: easy
prompt: "By how much did net revenue grow in 2025 compared with 2024?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "growth is about 12 percent (between 10.5 and 13.5)"
      - "both annual totals are shown"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-01; DA-PY-01; G-10"}
```

### EV-DA-018

```yaml
id: EV-DA-018
suite: data_analysis
category: growth_trend
language: ar
difficulty: medium
prompt: "ما نسبة نمو الإيرادات من يناير إلى أكتوبر 2026 مقارنة بنفس الفترة من 2025؟"
prompt_en: "What was the revenue growth from January to October 2026 compared with the same period of 2025?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "growth is about 9 percent (between 7.5 and 10.5)"
      - "compares the same ten months, not the full year 2025"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-10; DA-PY-04; G-10"}
```

### EV-DA-019

```yaml
id: EV-DA-019
suite: data_analysis
category: growth_trend
language: en
difficulty: medium
prompt: "How has the share of Online and Mobile App sales changed from 2024 to 2026?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "about 14 percent in 2024, 19 percent in 2025 and 24 percent in January to October 2026"
      - "change is given in percentage points"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-07; DA-PY-05; G-11"}
```

### EV-DA-020

```yaml
id: EV-DA-020
suite: data_analysis
category: growth_trend
language: ar
difficulty: medium
prompt: "اعرض اتجاه صافي الإيرادات الشهري خلال 2025 مع المتوسط المتحرك لثلاثة أشهر."
prompt_en: "Show the monthly net revenue trend during 2025 with a three-month moving average."
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "twelve monthly values"
      - "three-month moving average starts with the third month"
basis: {type: oracle_sql, reference: "DA-SQL-04; DA-PY-03"}
```

## Category: seasonality

### EV-DA-021

```yaml
id: EV-DA-021
suite: data_analysis
category: seasonality
language: en
difficulty: hard
prompt: "Which calendar months are seasonally strongest for our net revenue?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "seasonal index of each calendar month over the full years 2024 and 2025"
      - "months with Ramadan, Eid and White Friday days rank high; the answer says that the Hijri events move between months"
basis: {type: oracle_sql, reference: "DA-SQL-04; DA-PY-06"}
```

### EV-DA-022

```yaml
id: EV-DA-022
suite: data_analysis
category: seasonality
language: ar
difficulty: medium
prompt: "في أي ساعات من اليوم تبلغ مبيعات الموقع الإلكتروني والتطبيق ذروتها؟"
prompt_en: "At which hours of the day do website and app sales peak?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: ar
    must_include:
      - "hourly profile for the Online and Mobile App channels"
      - "the peak hours equal the oracle"
      - "hours are in Asia/Riyadh time"
basis: {type: oracle_sql, reference: DA-SQL-17}
```

### EV-DA-023

```yaml
id: EV-DA-023
suite: data_analysis
category: seasonality
language: en
difficulty: hard
prompt: "Did Grocery and Gourmet sell more during Ramadan 2025 than on ordinary days, and by how much?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "average daily net revenue in Ramadan is at least 1.4 times the Regular-day average"
      - "Ramadan 2025 window is 2025-03-01 to 2025-03-29, with the last seven days classified as Eid al-Fitr"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-20; G-16"}
```

### EV-DA-024

```yaml
id: EV-DA-024
suite: data_analysis
category: seasonality
language: ar
difficulty: medium
prompt: "هل ارتفعت المبيعات خلال الجمعة البيضاء مقارنة بالأيام العادية؟"
prompt_en: "Did sales rise during White Friday compared with regular days?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "White Friday daily revenue is at least 1.8 times the Regular level"
      - "Consumer Electronics share rises by at least 5 points"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-20; G-17"}
```

### EV-DA-025

```yaml
id: EV-DA-025
suite: data_analysis
category: seasonality
language: en
difficulty: easy
prompt: "Are Friday and Saturday stronger than other days in the stores?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "Friday and Saturday are at least 1.2 times the Sunday to Thursday average"
      - "Friday and Saturday are the weekend"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-16; G-14"}
```

### EV-DA-026

```yaml
id: EV-DA-026
suite: data_analysis
category: seasonality
language: ar
difficulty: medium
prompt: "هل أيام الراتب (من 25 إلى 28 من كل شهر) أقوى من باقي الأيام؟"
prompt_en: "Are payday days (the 25th to the 28th of each month) stronger than other days?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "average daily revenue on days 25 to 28 is at least 1.15 times the other days"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-21; G-15"}
```

### EV-DA-027

```yaml
id: EV-DA-027
suite: data_analysis
category: seasonality
language: en
difficulty: medium
prompt: "How much higher are cooling and fan unit sales in June to August than the monthly average?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "Home Appliances cooling and fan units are at least 1.5 times the monthly average"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-22; G-18"}
```

### EV-DA-028

```yaml
id: EV-DA-028
suite: data_analysis
category: seasonality
language: ar
difficulty: medium
prompt: "ما مقدار الارتفاع في مبيعات معدات التخييم في الفترة من نوفمبر إلى فبراير؟"
prompt_en: "How much do camping equipment sales rise between November and February?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "Sports and Outdoor camping units are at least 1.4 times the monthly average"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-22; G-18"}
```

### EV-DA-029

```yaml
id: EV-DA-029
suite: data_analysis
category: seasonality
language: en
difficulty: hard
prompt: "Does the Madinah Quba store show a bigger Ramadan uplift than the chain overall?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include: ["MED-QBA uplift is at least 1.2 times the chain-wide uplift"]
basis: {type: oracle_and_guarantee, reference: "DA-SQL-23; G-19"}
```

### EV-DA-030

```yaml
id: EV-DA-030
suite: data_analysis
category: seasonality
language: ar
difficulty: medium
prompt: "كيف كانت مبيعات فئة الأطفال والمدرسة بين 1 أغسطس و15 سبتمبر مقارنة بالمتوسط الشهري؟"
prompt_en: "How did Kids and School sales between 1 August and 15 September compare with the monthly average?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "units are at least 1.6 times the monthly average for school supplies and backpacks"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-22; G-18"}
```

## Category: customer_analytics

### EV-DA-031

```yaml
id: EV-DA-031
suite: data_analysis
category: customer_analytics
language: en
difficulty: medium
prompt: "What is the distribution of customers across loyalty tiers?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: en
    must_include:
      - "individual customers only: None about 45, Silver 30, Gold 18, Platinum 7 percent"
      - "business customers have tier None and are reported separately"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-25; G-20"}
```

### EV-DA-032

```yaml
id: EV-DA-032
suite: data_analysis
category: customer_analytics
language: ar
difficulty: medium
prompt: "ما نسبة العملاء الذين اشتروا مرتين أو أكثر؟"
prompt_en: "What share of customers bought twice or more?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: ar
    must_include:
      - "repeat purchase rate is between 30 and 45 percent"
      - "orders without a customer are excluded"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-26; G-22; G-06"}
```

### EV-DA-033

```yaml
id: EV-DA-033
suite: data_analysis
category: customer_analytics
language: en
difficulty: hard
prompt: "Show the retention of customers registered in 2025 over the following three months."
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "25 to 40 percent of customers of a registration month order again within three months"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-24; DA-PY-08; G-22"}
```

### EV-DA-034

```yaml
id: EV-DA-034
suite: data_analysis
category: customer_analytics
language: ar
difficulty: medium
prompt: "ما متوسط قيمة الطلب لكل فئة ولاء في 2025؟"
prompt_en: "What is the average order value of each loyalty tier in 2025?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: ar
    must_include:
      - "order Platinum > Gold > Silver > None"
      - "no significance test is run because none was requested"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-11; G-21"}
```

### EV-DA-035

```yaml
id: EV-DA-035
suite: data_analysis
category: customer_analytics
language: en
difficulty: medium
prompt: "How many new customers registered each month in 2026, by acquisition channel?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: en
    must_include:
      - "ten months January to October"
      - "at least 100 registrations in each month"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-27; G-22"}
```

### EV-DA-036

```yaml
id: EV-DA-036
suite: data_analysis
category: customer_analytics
language: ar
difficulty: hard
prompt: "من هم أكثر خمسة عملاء أفراد إنفاقًا في 2025؟"
prompt_en: "Who are the five individual customers with the highest spend in 2025?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: ar
    must_include: ["customers are identified by customer code", "totals are shown"]
    must_not_include:
      - "customer full names"
      - "customer email addresses"
      - "customer phone numbers"
basis:
  type: rule
  reference: "docs/03 allow-list: full_name of individuals is not returned; DA-SQL-03"
```

## Category: targets_returns_promotions

### EV-DA-037

```yaml
id: EV-DA-037
suite: data_analysis
category: targets_returns_promotions
language: en
difficulty: medium
prompt: "Which branches fell short of their October 2026 sales goals?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "at least two locations are below 100 percent attainment"
      - "targets equal the same month of 2025 times 1.10"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-12; DA-PY-09; G-29"}
```

### EV-DA-038

```yaml
id: EV-DA-038
suite: data_analysis
category: targets_returns_promotions
language: ar
difficulty: medium
prompt: "ما معدل الإرجاع لكل فئة منتجات؟"
prompt_en: "What is the return rate of each product line?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "Fashion and Apparel highest, between 6 and 9 percent"
      - "Grocery and Gourmet lowest, under 1.5 percent"
      - "overall rate between 3 and 5 percent"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-13; G-27"}
```

### EV-DA-039

```yaml
id: EV-DA-039
suite: data_analysis
category: targets_returns_promotions
language: en
difficulty: medium
prompt: "What share of returns are defective items?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: en
    must_include: ["defective items are between 15 and 25 percent of returns"]
basis: {type: oracle_and_guarantee, reference: "DA-SQL-18; G-27"}
```

### EV-DA-040

```yaml
id: EV-DA-040
suite: data_analysis
category: targets_returns_promotions
language: ar
difficulty: medium
prompt: "ما نسبة الطلبات التي استخدمت عرضًا ترويجيًا في 2025؟"
prompt_en: "What share of orders used a promotion in 2025?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: ar
    must_include: ["about 22 percent of orders carry a promotion"]
basis: {type: oracle_and_guarantee, reference: "DA-SQL-15; G-28"}
```

### EV-DA-041

```yaml
id: EV-DA-041
suite: data_analysis
category: targets_returns_promotions
language: en
difficulty: hard
prompt: "Which promotion types were used in 2025 and how much discount did each type give in total?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: en
    must_include:
      - "groups by promotion type: Percentage Off, Bundle Deal, Seasonal Sale, Loyalty Bonus, Clearance where used"
      - "discount is the sum of quantity times list price minus line total"
basis: {type: oracle_sql, reference: "adapted from DA-SQL-15"}
```

### EV-DA-042

```yaml
id: EV-DA-042
suite: data_analysis
category: targets_returns_promotions
language: ar
difficulty: hard
prompt: "هل تجاوز أي خصم الحد الأقصى المسموح به لفئته؟"
prompt_en: "Did any discount exceed the maximum allowed for its product line?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: ar
    must_include:
      - "result is zero violations"
      - "caps: ELEC 25, APPL 25, FASH 50, GROC 20, BEAU 30, SPRT 40, KIDS 35, HOME 40 percent"
basis:
  type: oracle_and_guarantee
  reference: "order_lines.discount_pct against product line caps; G-28"
```

## Category: hypothesis_test

### EV-DA-043

```yaml
id: EV-DA-043
suite: data_analysis
category: hypothesis_test
language: en
difficulty: medium
prompt: "Do Gold-tier customers spend significantly more per order than Silver-tier customers in 2025?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true, hypothesis_test: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "Welch t-test on 2025 Completed orders"
      - "p-value below 0.05, difference is significant"
      - "reports both group means and the sample sizes"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-11; DA-PY-10; G-21"}
```

### EV-DA-044

```yaml
id: EV-DA-044
suite: data_analysis
category: hypothesis_test
language: ar
difficulty: medium
prompt: "هل يختلف متوسط قيمة الطلب بين فئات الولاء الأربع بشكل معنوي؟"
prompt_en: "Does the average order value differ significantly across the four loyalty tiers?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true, hypothesis_test: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include: ["one-way ANOVA", "p-value below 0.001"]
basis: {type: oracle_and_guarantee, reference: "DA-SQL-11; DA-PY-12; G-21"}
```

### EV-DA-045

```yaml
id: EV-DA-045
suite: data_analysis
category: hypothesis_test
language: en
difficulty: medium
prompt: "Do Online and Mobile App orders have a higher average order value than In-Store orders in 2025? Is the difference significant?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true, hypothesis_test: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "digital average order value is at least 15 percent higher"
      - "p-value below 0.01"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-11; DA-PY-10; G-23"}
```

### EV-DA-046

```yaml
id: EV-DA-046
suite: data_analysis
category: hypothesis_test
language: ar
difficulty: hard
prompt: "هل هناك فرق معنوي في متوسط قيمة الطلب بين فرعي الدمام الفيصلية والخبر الكورنيش في 2025؟"
prompt_en: "Is there a significant difference in average order value between the Dammam Faisaliyah and Al Khobar Corniche stores in 2025?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true, hypothesis_test: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "difference is less than 2 percent"
      - "p-value above 0.10, so no significant difference is found"
      - "does not claim a difference"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-11; DA-PY-10; G-24"}
```

### EV-DA-047

```yaml
id: EV-DA-047
suite: data_analysis
category: hypothesis_test
language: en
difficulty: medium
prompt: "Do orders with a promotion have a different average order value than orders without? Test it."
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true, hypothesis_test: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "Mann-Whitney or Welch test result with p-value below 0.01"
      - "states which test was used and why"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-15; DA-PY-11; G-25"}
```

### EV-DA-048

```yaml
id: EV-DA-048
suite: data_analysis
category: hypothesis_test
language: ar
difficulty: hard
prompt: "هل توجد علاقة بين نسبة الخصم والكمية في بنود الطلبات؟"
prompt_en: "Is there a relationship between the discount percentage and the quantity on order lines?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true, hypothesis_test: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "Spearman correlation between 0.15 and 0.40"
      - "p-value below 0.001"
      - "describes the relationship as weak to moderate and positive"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-19; DA-PY-15; G-25"}
```

### EV-DA-049

```yaml
id: EV-DA-049
suite: data_analysis
category: hypothesis_test
language: en
difficulty: medium
prompt: "Is payment method associated with sales channel? Run a significance test."
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true, hypothesis_test: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include: ["chi-square test of independence", "p-value below 0.001"]
basis: {type: oracle_and_guarantee, reference: "DA-SQL-14; DA-PY-13; G-26"}
```

### EV-DA-050

```yaml
id: EV-DA-050
suite: data_analysis
category: hypothesis_test
language: ar
difficulty: hard
prompt: "هل يختلف معدل الإرجاع بين فئة الأزياء وفئة البقالة بشكل معنوي؟"
prompt_en: "Does the return rate differ significantly between Fashion and Grocery?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: true, hypothesis_test: true}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "two-proportion z-test"
      - "p-value below 0.001"
      - "Fashion rate is higher"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-18; DA-PY-14; G-26"}
```

## Category: edge_case

### EV-DA-051

```yaml
id: EV-DA-051
suite: data_analysis
category: edge_case
language: en
difficulty: medium
prompt: "What was the total revenue for the full year 2026?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: en
    must_include:
      - "answers for 2026-01-01 to 2026-10-31 only"
      - "warns that the data ends on 2026-10-31 and the year is incomplete"
basis:
  type: rule
  reference: "RT-05 time phrases; 02_architecture section 8"
```

### EV-DA-052

```yaml
id: EV-DA-052
suite: data_analysis
category: edge_case
language: ar
difficulty: medium
prompt: "ما إجمالي إيرادات عام 2025 شاملة ضريبة القيمة المضافة؟"
prompt_en: "What is the total revenue of 2025 including VAT?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: ar
    must_include:
      - "reports net revenue excluding VAT"
      - "gives the VAT-inclusive figure as net revenue times 1.15 and states the 15 percent rate"
basis:
  type: oracle_and_guarantee
  reference: "DA-SQL-01; docs/07 section 1"
```

### EV-DA-053

```yaml
id: EV-DA-053
suite: data_analysis
category: edge_case
language: en
difficulty: medium
prompt: "How many orders are still being processed?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: en
    must_include:
      - "Processing orders exist only for dates 2026-10-29 to 2026-10-31"
      - "Processing orders are not counted as revenue"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-30; G-07"}
```

### EV-DA-054

```yaml
id: EV-DA-054
suite: data_analysis
category: edge_case
language: en
difficulty: medium
prompt: "List the orders placed by customer CUST-9999."
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: en
    must_include:
      - "reports no matching data and the filter used"
      - "does not invent orders"
basis:
  type: behavior
  reference: "02_architecture section 8: empty SQL result"
```

### EV-DA-055

```yaml
id: EV-DA-055
suite: data_analysis
category: edge_case
language: ar
difficulty: medium
prompt: "اعرض كل بنود الطلبات في عام 2025."
prompt_en: "Show all order lines of 2025."
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: ar
    must_include:
      - "result is limited to a sample, with a statement that it is limited"
      - "offers an aggregated view instead"
    must_not_include: ["all 300,000 rows"]
basis:
  type: rule
  reference: "DA-01 LIMIT rules; postgres_tool max_rows 500"
```

### EV-DA-056

```yaml
id: EV-DA-056
suite: data_analysis
category: edge_case
language: en
difficulty: hard
prompt: "What was the average order value for each sales channel in 2025?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis]
    hints:
      data_analysis: {needs_computation: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: en
    must_include:
      - "final answer is produced after one retry"
      - "four channels reported"
  harness:
    fault_injection: "first generated SQL references an unknown column"
    expected_retries: 1
basis:
  type: behavior
  reference: "02_architecture sections 4.1 and 8: retry up to two times"
```
