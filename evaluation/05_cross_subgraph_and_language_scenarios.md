# Evaluation Scenarios: Cross-Subgraph and Language

- Document ID: EV-XS
- Suite: cross_subgraph
- Scenarios: 20 (EV-XS-001 to EV-XS-020)
- Languages: 6 English, 11 Arabic, 3 mixed
- Difficulty: 0 easy, 15 medium, 5 hard
- Fields and grading rules: `00_index.md` and `docs/06_evaluation_plan.md`

## Purpose

Checks questions that need more than one subgraph, the order and merging of the answers, and language handling: Arabic output, digit conversion, mixed-language messages, Gulf dialect and an explicit answer-language request.

## Categories

| Category | Scenarios |
|---|---|
| multi_subgraph | 13 |
| language | 7 |

## Category: multi_subgraph

### EV-XS-001

```yaml
id: EV-XS-001
suite: cross_subgraph
category: multi_subgraph
language: en
difficulty: medium
prompt: "For 2025, what was the net revenue of Beauty and Fragrance, and what stock of that line do we hold today?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis, inventory]
    hints:
      data_analysis: {needs_computation: false}
      inventory: {forecast_requested: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "revenue equals the oracle for BEAU in 2025"
      - "units are available quantity over all locations as of 2026-10-31"
      - "answers the parts in the order asked, one short paragraph per part"
basis: {type: oracle_sql, reference: "DA-SQL-05; INV-SQL-13"}
```

### EV-XS-002

```yaml
id: EV-XS-002
suite: cross_subgraph
category: multi_subgraph
language: ar
difficulty: medium
prompt: "كم بلغ صافي إيرادات فئة الإلكترونيات في 2025، وكم وحدة من ELEC-0003 متوفرة حاليًا؟"
prompt_en: "What was the net revenue of Consumer Electronics in 2025, and how many units of ELEC-0003 are currently available?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis, inventory]
    hints:
      data_analysis: {needs_computation: false}
      inventory: {forecast_requested: false}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "answers the parts in the order asked, one short paragraph per part"
      - "figures are identical to the English answer"
basis: {type: oracle_sql, reference: "DA-SQL-05; INV-SQL-01"}
```

### EV-XS-003

```yaml
id: EV-XS-003
suite: cross_subgraph
category: multi_subgraph
language: en
difficulty: medium
prompt: "Which store had the highest 2025 net revenue, and how many staff does it have?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis, knowledge_base]
    hints:
      data_analysis: {needs_computation: true}
      knowledge_base: {}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
    knowledge_base:
      tools_used: [rag]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "Riyadh Olaya Flagship (RYD-OLY) ranks first"
      - "78 staff"
      - "the second part uses the store found by the first part"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-06; KB-BR-01; G-12"}
```

### EV-XS-004

```yaml
id: EV-XS-004
suite: cross_subgraph
category: multi_subgraph
language: ar
difficulty: medium
prompt: "ما هو الفرع الأقل مبيعًا في 2025 ومن هو مديره؟"
prompt_en: "Which store had the lowest sales in 2025 and who is its manager?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis, knowledge_base]
    hints:
      data_analysis: {needs_computation: true}
      knowledge_base: {}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
    knowledge_base:
      tools_used: [rag]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "Abha City Express (ABH-CTY) is the lowest store"
      - "manager Mohammed Al-Asmari"
basis: {type: oracle_and_guarantee, reference: "DA-SQL-06; KB-BR-08; G-12"}
```

### EV-XS-005

```yaml
id: EV-XS-005
suite: cross_subgraph
category: multi_subgraph
language: en
difficulty: medium
prompt: "What penalty does the SUP-04 contract set for late deliveries, and how many of SUP-04's purchase orders were delivered late?"
expected:
  route:
    decision: route
    subgraphs: [knowledge_base, inventory]
    hints:
      knowledge_base: {}
      inventory: {forecast_requested: false}
  method:
    knowledge_base:
      tools_used: [rag]
      bypassed: []
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: en
    must_include:
      - "penalty of 0.5 percent of the late line value per day, capped at 5 percent"
      - "late count equals the oracle for SUP-04"
      - "does not mix contract wording with measured data"
basis:
  type: oracle_and_document
  reference: "INV-SQL-19; KB-SC-04 section 7"
```

### EV-XS-006

```yaml
id: EV-XS-006
suite: cross_subgraph
category: multi_subgraph
language: ar
difficulty: hard
prompt: "ما مدة التوريد المنصوص عليها في عقد المورد SUP-08، وكم كانت مدة التسليم الفعلية في أوامر الشراء؟"
prompt_en: "What lead time does the contract with supplier SUP-08 state, and what was the actual delivery time in purchase orders?"
expected:
  route:
    decision: route
    subgraphs: [knowledge_base, inventory]
    hints:
      knowledge_base: {}
      inventory: {forecast_requested: false}
  method:
    knowledge_base:
      tools_used: [rag]
      bypassed: []
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "contract lead time is 9 days"
      - "actual lead time is measured from purchase orders and is stated separately"
basis:
  type: oracle_and_document
  reference: "INV-SQL-19; KB-SC-08 section 1"
```

### EV-XS-007

```yaml
id: EV-XS-007
suite: cross_subgraph
category: multi_subgraph
language: ar
difficulty: medium
prompt: "ما الحد الائتماني لشركة Red Sea Resorts and Spa وكم بلغت مشترياتها في 2025؟"
prompt_en: "What is the credit limit of Red Sea Resorts and Spa and how much did it buy in 2025?"
expected:
  route:
    decision: route
    subgraphs: [knowledge_base, data_analysis]
    hints:
      knowledge_base: {}
      data_analysis: {needs_computation: false}
  method:
    knowledge_base:
      tools_used: [rag]
      bypassed: []
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
  status: ok
  answer:
    language: ar
    must_include:
      - "credit limit SAR 1,200,000"
      - "2025 spend equals the oracle for CUST-B004"
basis:
  type: oracle_and_document
  reference: "DA-SQL-28; KB-CC-04 section 1"
```

### EV-XS-008

```yaml
id: EV-XS-008
suite: cross_subgraph
category: multi_subgraph
language: en
difficulty: hard
prompt: "Forecast the next 8 weeks of demand for the Summit 65L Trekking Backpack and tell me the minimum order quantity of its supplier."
expected:
  route:
    decision: route
    subgraphs: [inventory, knowledge_base]
    hints:
      inventory: {forecast_requested: true, horizon_weeks: 8}
      knowledge_base: {}
  method:
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
    knowledge_base:
      tools_used: [rag]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - SPRT-0005
      - "forecast of eight weeks"
      - "SUP-12 minimum order quantity is 80 units"
basis:
  type: oracle_and_document
  reference: "INV-SQL-14; KB-SC-12 section 1"
```

### EV-XS-009

```yaml
id: EV-XS-009
suite: cross_subgraph
category: multi_subgraph
language: ar
difficulty: medium
prompt: "ما نسبة تحقيق الهدف لفرع الرياض العليا في أكتوبر 2026، وكيف يُحسب الهدف؟"
prompt_en: "What was the target attainment of the Riyadh Olaya store in October 2026, and how is the target calculated?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis, knowledge_base]
    hints:
      data_analysis: {needs_computation: true}
      knowledge_base: {}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
    knowledge_base:
      tools_used: [rag]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "attainment equals the oracle"
      - "target equals the same month of the previous year times 1.10"
basis:
  type: oracle_and_document
  reference: "DA-SQL-12; KB-POL-22 section 2"
```

### EV-XS-010

```yaml
id: EV-XS-010
suite: cross_subgraph
category: multi_subgraph
language: en
difficulty: medium
prompt: "How many customers are in each loyalty tier, and what spend defines each tier?"
expected:
  route:
    decision: route
    subgraphs: [data_analysis, knowledge_base]
    hints:
      data_analysis: {needs_computation: false}
      knowledge_base: {}
  method:
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
    knowledge_base:
      tools_used: [rag]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "tier counts equal the oracle"
      - "Silver 3,000, Gold 10,000 and Platinum 25,000 SAR of trailing 12-month net spend"
basis:
  type: oracle_and_document
  reference: "DA-SQL-25; KB-POL-08 section 2; G-20"
```

### EV-XS-011

```yaml
id: EV-XS-011
suite: cross_subgraph
category: multi_subgraph
language: ar
difficulty: medium
prompt: "كم عدد أوامر الشراء المتأخرة، وما هي غرامة التأخير؟"
prompt_en: "How many purchase orders are overdue, and what is the late delivery penalty?"
expected:
  route:
    decision: route
    subgraphs: [inventory, knowledge_base]
    hints:
      inventory: {forecast_requested: false}
      knowledge_base: {}
  method:
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
    knowledge_base:
      tools_used: [rag]
      bypassed: []
  status: ok
  answer:
    language: ar
    must_include:
      - "overdue count equals the oracle for 2026-10-31"
      - "penalty is 0.5 percent per day capped at 5 percent"
basis:
  type: oracle_and_document
  reference: "INV-SQL-11; KB-POL-14 section 4"
```

### EV-XS-012

```yaml
id: EV-XS-012
suite: cross_subgraph
category: multi_subgraph
language: en
difficulty: hard
prompt: "Compare Ramadan 2025 grocery sales with regular days, and forecast the next 4 weeks of demand for Qassim Gold Khalas Dates."
expected:
  route:
    decision: route
    subgraphs: [data_analysis, inventory]
    hints:
      data_analysis: {needs_computation: true}
      inventory: {forecast_requested: true, horizon_weeks: 4}
  method:
    data_analysis:
      tools_used: [rag, postgres, pandas]
      bypassed: []
    inventory:
      tools_used: [rag, postgres, regression]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "Ramadan uplift of at least 1.4 times"
      - "forecast for GROC-0001 for four weeks"
      - "the two parts are independent and both answered"
basis:
  type: oracle_and_guarantee
  reference: "DA-SQL-20; INV-SQL-14; G-16"
```

### EV-XS-013

```yaml
id: EV-XS-013
suite: cross_subgraph
category: multi_subgraph
language: ar
difficulty: hard
prompt: "من هو مدير فرع جدة التحلية، وكم بلغت إيراداته في 2025، وكم وحدة من ELEC-0001 لديه؟"
prompt_en: "Who is the manager of the Jeddah Tahlia store, what was its revenue in 2025, and how many units of ELEC-0001 does it have?"
expected:
  route:
    decision: route
    subgraphs: [knowledge_base, data_analysis, inventory]
    hints:
      knowledge_base: {}
      data_analysis: {needs_computation: false}
      inventory: {forecast_requested: false}
  method:
    knowledge_base:
      tools_used: [rag]
      bypassed: []
    data_analysis:
      tools_used: [rag, postgres]
      bypassed: [pandas]
    inventory:
      tools_used: [rag, postgres]
      bypassed: [regression]
  status: ok
  answer:
    language: ar
    must_include:
      - "manager Nasser Al-Ghamdi"
      - "2025 revenue of JED-THL equals the oracle"
      - "stock of ELEC-0001 at JED-THL as of 2026-10-31"
      - "answers the parts in the order asked, one short paragraph per part"
basis:
  type: oracle_and_document
  reference: "DA-SQL-06; INV-SQL-01; KB-BR-02"
note: "Phase 2 dependency: JED-THL must hold a stock position for ELEC-0001."
```

## Category: language

### EV-XS-014

```yaml
id: EV-XS-014
suite: cross_subgraph
category: language
language: ar
difficulty: medium
prompt: "ما هي أعلى ثلاثة أشهر مبيعًا في عام 2025؟"
prompt_en: "Which three months had the highest sales in 2025?"
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
      - "answer is in Arabic"
      - "month names are in Arabic"
      - "amounts, dates in ISO format and SAR are unchanged from the English node response"
      - "digits are Western (0-9)"
basis: {type: oracle_sql, reference: DA-SQL-04}
```

### EV-XS-015

```yaml
id: EV-XS-015
suite: cross_subgraph
category: language
language: ar
difficulty: medium
prompt: "كم بلغ صافي الإيرادات في عام ٢٠٢٥؟"
prompt_en: "How much was net revenue in 2025? (the year is written with Eastern Arabic-Indic digits)"
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
      - "Eastern Arabic-Indic digits are converted to 2025 before routing"
      - "the answer uses Western digits"
basis: {type: rule, reference: "RT-07 Arabic Business Terms"}
```

### EV-XS-016

```yaml
id: EV-XS-016
suite: cross_subgraph
category: language
language: mixed
difficulty: medium
prompt: "كم كانت sales فرع Riyadh Olaya في أكتوبر 2026؟"
prompt_en: "How much were the sales of the Riyadh Olaya store in October 2026?"
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
      - "store resolves to RYD-OLY"
      - "period is 2026-10-01 to 2026-10-31"
      - "answer is in Arabic because most of the message is Arabic"
basis: {type: rule, reference: "06_evaluation_plan.md language convention"}
```

### EV-XS-017

```yaml
id: EV-XS-017
suite: cross_subgraph
category: language
language: mixed
difficulty: medium
prompt: "Give me a summary of مبيعات الجمعة البيضاء in 2025."
prompt_en: "Give me a summary of White Friday sales in 2025."
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
      - "answer is in English because most of the message is English"
      - "White Friday window of 2025 is used"
basis: {type: rule, reference: "06_evaluation_plan.md language convention"}
```

### EV-XS-018

```yaml
id: EV-XS-018
suite: cross_subgraph
category: language
language: ar
difficulty: hard
prompt: "وش أكثر منتج يتباع في رمضان؟"
prompt_en: "What is the best-selling product in Ramadan? (Gulf dialect)"
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
      - "interprets the question as units sold"
      - "assumes the latest Ramadan, 2026-02-18 to 2026-03-19, and states the assumption"
      - "note that the last seven days are classified as Eid al-Fitr"
basis:
  type: rule
  reference: "RT-05 Rule 6 defaults; RT-07 Seasons and Events"
```

### EV-XS-019

```yaml
id: EV-XS-019
suite: cross_subgraph
category: language
language: ar
difficulty: medium
prompt: "كم باقي عندنا من مكيف BreezeMax Split AC 24000 BTU؟"
prompt_en: "How many BreezeMax Split AC 24000 BTU units do we have left? (Gulf dialect)"
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
      - "resolves to APPL-0002"
      - "available quantity over all locations as of 2026-10-31"
      - "regression is bypassed"
basis: {type: oracle_sql, reference: INV-SQL-01}
```

### EV-XS-020

```yaml
id: EV-XS-020
suite: cross_subgraph
category: language
language: mixed
difficulty: medium
prompt: "Answer in English: كم عدد الفروع التي لدينا؟"
prompt_en: "Answer in English: How many branches do we have?"
expected:
  route:
    decision: route
    subgraphs: [knowledge_base]
    hints:
      knowledge_base: {}
  method:
    knowledge_base:
      tools_used: [rag]
      bypassed: []
  status: ok
  answer:
    language: en
    must_include:
      - "answer is in English because the user asked for English"
      - "eight stores and one Distribution Center, nine locations"
basis:
  type: rule
  reference: "02_architecture section 7 rule 7; KB-POL-04"
```
