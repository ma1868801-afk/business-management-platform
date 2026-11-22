# Evaluation Scenarios: Knowledge Base

- Document ID: EV-KB
- Suite: knowledge_base
- Scenarios: 46 (EV-KB-001 to EV-KB-046)
- Languages: 24 English, 22 Arabic, 0 mixed
- Difficulty: 29 easy, 15 medium, 2 hard
- Fields and grading rules: `00_index.md` and `docs/06_evaluation_plan.md`

## Purpose

Checks answers from the 77 company documents. Every expected fact is stated in the named document, so grading is exact. The last two scenarios check that the node refuses to answer from general knowledge.

## Categories

| Category | Scenarios |
|---|---|
| policy | 14 |
| branch | 6 |
| supplier_contract | 7 |
| customer_agreement | 5 |
| employee | 6 |
| product | 6 |
| not_in_documents | 2 |

## Category: policy

### EV-KB-001

```yaml
id: EV-KB-001
suite: knowledge_base
category: policy
language: en
difficulty: easy
prompt: "How many days does a customer have to return a defective product?"
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
      - "30 days from the order date"
      - "other items 14 days"
      - "defective returns are not restocked"
basis: {type: document, reference: "KB-POL-09 section 1"}
```

### EV-KB-002

```yaml
id: EV-KB-002
suite: knowledge_base
category: policy
language: ar
difficulty: medium
prompt: "متى يكون التوصيل مجانيًا للطلبات عبر الموقع الإلكتروني؟"
prompt_en: "When is delivery free for orders placed on the website?"
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
    language: ar
    must_include:
      - "free when the subtotal is SAR 250 or more"
      - "free for Gold and Platinum members"
      - "otherwise SAR 25 for Online and Mobile App orders"
basis: {type: document, reference: "KB-POL-10 section 2"}
```

### EV-KB-003

```yaml
id: EV-KB-003
suite: knowledge_base
category: policy
language: en
difficulty: easy
prompt: "What spend is needed to reach the Platinum tier?"
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
      - "SAR 25,000 of net spend in the trailing 12 months, excluding VAT"
      - "tier is recalculated nightly"
basis: {type: document, reference: "KB-POL-08 section 2"}
```

### EV-KB-004

```yaml
id: EV-KB-004
suite: knowledge_base
category: policy
language: ar
difficulty: easy
prompt: "كم نقطة أحتاج لاسترداد خصم قيمته 5 ريالات؟"
prompt_en: "How many points do I need to redeem a discount of SAR 5?"
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
    language: ar
    must_include:
      - "100 points redeem SAR 5"
      - "1 point is earned per SAR 10 of net spend"
basis: {type: document, reference: "KB-POL-08 section 3"}
```

### EV-KB-005

```yaml
id: EV-KB-005
suite: knowledge_base
category: policy
language: en
difficulty: medium
prompt: "Who approves a purchase order of SAR 120,000?"
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
      - "Head of Supply Chain (Ibrahim Al-Qarni)"
      - "the band is SAR 50,001 to SAR 250,000"
basis: {type: document, reference: "KB-POL-14 section 6"}
```

### EV-KB-006

```yaml
id: EV-KB-006
suite: knowledge_base
category: policy
language: ar
difficulty: easy
prompt: "ما هي غرامة التأخير في التسليم المفروضة على الموردين؟"
prompt_en: "What is the late delivery penalty imposed on suppliers?"
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
    language: ar
    must_include:
      - "0.5 percent of the late line value per day"
      - "capped at 5 percent of the line value"
basis: {type: document, reference: "KB-POL-14 section 4"}
```

### EV-KB-007

```yaml
id: EV-KB-007
suite: knowledge_base
category: policy
language: en
difficulty: easy
prompt: "What service level does the company use for A-class SKUs?"
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
    must_include: ["98 percent", "safety factor z of 2.05"]
basis: {type: document, reference: "KB-POL-13 section 3"}
```

### EV-KB-008

```yaml
id: EV-KB-008
suite: knowledge_base
category: policy
language: ar
difficulty: medium
prompt: "كيف تُحسب أيام الإجازة السنوية للموظف الجديد؟"
prompt_en: "How are annual leave days calculated for a new employee?"
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
    language: ar
    must_include:
      - "1.75 days for each completed month in years 1 to 5"
      - "2.5 days per month after 5 years of service"
      - "example: 8 completed months give 14 days"
basis: {type: document, reference: "KB-POL-18 section 3"}
```

### EV-KB-009

```yaml
id: EV-KB-009
suite: knowledge_base
category: policy
language: en
difficulty: easy
prompt: "On what day are salaries paid?"
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
      - "the 25th of the month"
      - "the last working day before the 25th when it is not a working day"
basis: {type: document, reference: "KB-POL-18 section 5"}
```

### EV-KB-010

```yaml
id: EV-KB-010
suite: knowledge_base
category: policy
language: ar
difficulty: easy
prompt: "ما الحد الأقصى للخصم على منتجات البقالة؟"
prompt_en: "What is the maximum discount on grocery products?"
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
    language: ar
    must_include: ["20 percent", "store-wide promotions never exceed 20 percent"]
basis: {type: document, reference: "KB-POL-06 section 2"}
```

### EV-KB-011

```yaml
id: EV-KB-011
suite: knowledge_base
category: policy
language: en
difficulty: easy
prompt: "How long is the probation period for new employees?"
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
    must_include: ["90 days"]
basis: {type: document, reference: "KB-POL-18 section 2"}
```

### EV-KB-012

```yaml
id: EV-KB-012
suite: knowledge_base
category: policy
language: ar
difficulty: medium
prompt: "ما أقصى قيمة للهدايا التي يمكن قبولها من الموردين؟"
prompt_en: "What is the maximum value of gifts that can be accepted from suppliers?"
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
    language: ar
    must_include: ["below SAR 500", "not during a tender or negotiation"]
basis: {type: document, reference: "KB-POL-19 section 4"}
```

### EV-KB-013

```yaml
id: EV-KB-013
suite: knowledge_base
category: policy
language: en
difficulty: easy
prompt: "Which emergency number should staff call for a fire in Saudi Arabia?"
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
    must_include: ["998 (Civil Defense)"]
basis: {type: document, reference: "KB-POL-20 section 2"}
```

### EV-KB-014

```yaml
id: EV-KB-014
suite: knowledge_base
category: policy
language: ar
difficulty: hard
prompt: "هل يستطيع المساعد عرض رقم هاتف العميل؟"
prompt_en: "Can the assistant show a customer's phone number?"
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
    language: ar
    must_include:
      - "customer phone numbers and email addresses are Restricted"
      - "never exposed to the AI assistant"
    must_not_include: ["any phone number"]
basis: {type: document, reference: "KB-POL-16 section 3"}
note: "A policy question, so it is routed to the Knowledge Base and answered; a request for a specific number would be rejected."
```

## Category: branch

### EV-KB-015

```yaml
id: EV-KB-015
suite: knowledge_base
category: branch
language: en
difficulty: easy
prompt: "Which person manages our Abha City Express store?"
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
    must_include: ["Mohammed Al-Asmari (EMP-0033)"]
basis: {type: document, reference: "KB-BR-08 section 1"}
```

### EV-KB-016

```yaml
id: EV-KB-016
suite: knowledge_base
category: branch
language: ar
difficulty: medium
prompt: "ما ساعات العمل في فروع إكسبرس؟"
prompt_en: "What are the opening hours of the Express stores?"
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
    language: ar
    must_include:
      - "11:00 to 23:00 daily"
      - "applies to Jeddah Obhur Express and Abha City Express"
basis: {type: document, reference: "KB-POL-04 section 5; KB-BR-07"}
```

### EV-KB-017

```yaml
id: EV-KB-017
suite: knowledge_base
category: branch
language: en
difficulty: easy
prompt: "How many staff work at the Madinah Quba Standard store?"
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
    must_include: ["38"]
basis: {type: document, reference: "KB-BR-06 section 1"}
```

### EV-KB-018

```yaml
id: EV-KB-018
suite: knowledge_base
category: branch
language: ar
difficulty: easy
prompt: "متى افتُتح فرع جدة أبحر إكسبرس؟"
prompt_en: "When did the Jeddah Obhur Express store open?"
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
    language: ar
    must_include: ["2021-06-17"]
basis: {type: document, reference: "KB-BR-07 section 1"}
```

### EV-KB-019

```yaml
id: EV-KB-019
suite: knowledge_base
category: branch
language: en
difficulty: easy
prompt: "How large is the Riyadh Distribution Center and how many people work there?"
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
    must_include: ["18,000 sqm", "95 staff", "operates around the clock"]
basis:
  type: document
  reference: "KB-BR-09 section 1; KB-POL-15 section 1"
```

### EV-KB-020

```yaml
id: EV-KB-020
suite: knowledge_base
category: branch
language: ar
difficulty: medium
prompt: "ما دور فرع المدينة المنورة قباء في شبكة الفروع؟"
prompt_en: "What is the role of the Madinah Quba store in the network?"
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
    language: ar
    must_include:
      - "strong pilgrim and visitor effect"
      - "demand rises in Ramadan and the Hajj season"
basis: {type: document, reference: "KB-BR-06 section 2"}
```

## Category: supplier_contract

### EV-KB-021

```yaml
id: EV-KB-021
suite: knowledge_base
category: supplier_contract
language: en
difficulty: easy
prompt: "Which payment terms are written into the supplier agreement with SUP-08?"
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
      - "30 days from the invoice date"
      - "invoice currency AED"
      - "contract SC-2024-008"
basis: {type: document, reference: "KB-SC-08 section 1"}
```

### EV-KB-022

```yaml
id: EV-KB-022
suite: knowledge_base
category: supplier_contract
language: ar
difficulty: easy
prompt: "ما مدة التوريد في عقد المورد SUP-07؟"
prompt_en: "What is the lead time in the contract with supplier SUP-07?"
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
    language: ar
    must_include: ["4 days"]
basis: {type: document, reference: "KB-SC-07 section 1"}
```

### EV-KB-023

```yaml
id: EV-KB-023
suite: knowledge_base
category: supplier_contract
language: en
difficulty: easy
prompt: "What is the minimum order quantity for Munich Sport Systems GmbH?"
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
    must_include: ["80 units per order line (SUP-12)"]
basis: {type: document, reference: "KB-SC-12 section 1"}
```

### EV-KB-024

```yaml
id: EV-KB-024
suite: knowledge_base
category: supplier_contract
language: ar
difficulty: medium
prompt: "متى ينتهي عقد المورد SUP-02 الحالي وكم مرة جُدد؟"
prompt_en: "When does the current term of the contract with SUP-02 end and how many times has it been renewed?"
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
    language: ar
    must_include: ["current term ends 2027-08-31", "renewed 2 times"]
basis: {type: document, reference: "KB-SC-02 section 3"}
```

### EV-KB-025

```yaml
id: EV-KB-025
suite: knowledge_base
category: supplier_contract
language: en
difficulty: easy
prompt: "In which currency does Istanbul Cooling Systems invoice?"
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
    must_include: ["EUR (SUP-04)"]
basis: {type: document, reference: "KB-SC-04 section 1"}
```

### EV-KB-026

```yaml
id: EV-KB-026
suite: knowledge_base
category: supplier_contract
language: ar
difficulty: easy
prompt: "ما رقم عقد المورد SUP-16؟"
prompt_en: "What is the contract number of supplier SUP-16?"
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
    language: ar
    must_include: [SC-2025-016]
basis: {type: document, reference: "KB-SC-16 section 1"}
```

### EV-KB-027

```yaml
id: EV-KB-027
suite: knowledge_base
category: supplier_contract
language: en
difficulty: hard
prompt: "By what date must notice be given to stop the automatic renewal of the SUP-08 contract?"
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
    must_include: ["2026-11-30 (90 days before 2027-02-28)"]
basis: {type: document, reference: "KB-SC-08 section 3"}
```

## Category: customer_agreement

### EV-KB-028

```yaml
id: EV-KB-028
suite: knowledge_base
category: customer_agreement
language: en
difficulty: easy
prompt: "How high is the credit limit granted to Red Sea Resorts and Spa?"
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
    must_include: ["SAR 1,200,000 (CUST-B004)"]
basis: {type: document, reference: "KB-CC-04 section 1"}
```

### EV-KB-029

```yaml
id: EV-KB-029
suite: knowledge_base
category: customer_agreement
language: ar
difficulty: easy
prompt: "كم نسبة الخصم التعاقدي لشركة Gulf Catering Services؟"
prompt_en: "What is the contract discount of Gulf Catering Services?"
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
    language: ar
    must_include: ["12 percent on every order line"]
basis: {type: document, reference: "KB-CC-09 section 1"}
```

### EV-KB-030

```yaml
id: EV-KB-030
suite: knowledge_base
category: customer_agreement
language: en
difficulty: easy
prompt: "What are the payment terms for Riyadh Corporate Gifting Co.?"
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
    must_include: ["60 days from the invoice date, by Bank Transfer"]
basis: {type: document, reference: "KB-CC-11 section 1"}
```

### EV-KB-031

```yaml
id: EV-KB-031
suite: knowledge_base
category: customer_agreement
language: ar
difficulty: medium
prompt: "متى ينتهي العقد الحالي لشركة Najd Business Schools؟"
prompt_en: "When does the current agreement of Najd Business Schools end?"
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
    language: ar
    must_include: ["2026-12-31", "notice date for the next renewal is 2026-11-01"]
basis: {type: document, reference: "KB-CC-03 section 3"}
```

### EV-KB-032

```yaml
id: EV-KB-032
suite: knowledge_base
category: customer_agreement
language: en
difficulty: easy
prompt: "Who manages the account of Madinah Pilgrim Services Co.?"
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
    must_include: ["Lina Al-Najjar, B2B Account Manager, Western and Southern Regions"]
basis: {type: document, reference: "KB-CC-07 section 8"}
```

## Category: employee

### EV-KB-033

```yaml
id: EV-KB-033
suite: knowledge_base
category: employee
language: ar
difficulty: easy
prompt: "ما هو المسمى الوظيفي لـ Hind Al-Shammari ولمن ترفع تقاريرها؟"
prompt_en: "What is the job title of Hind Al-Shammari and to whom does she report?"
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
    language: ar
    must_include:
      - "HR Director"
      - "reports to Tariq Al-Shehri, Chief Operating Officer"
basis: {type: document, reference: KB-EMP-04}
```

### EV-KB-034

```yaml
id: EV-KB-034
suite: knowledge_base
category: employee
language: en
difficulty: easy
prompt: "When was Saad Al-Malki hired?"
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
    must_include: ["2019-04-22", "title Inventory Planning Manager"]
basis: {type: document, reference: KB-EMP-03}
```

### EV-KB-035

```yaml
id: EV-KB-035
suite: knowledge_base
category: employee
language: ar
difficulty: medium
prompt: "كم راتب الرئيس المالي Maha Al-Sudairi؟"
prompt_en: "What is the salary of the Chief Financial Officer, Maha Al-Sudairi?"
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
    language: ar
    must_include: ["SAR 62,000 per month (EMP-0002)"]
basis: {type: document, reference: KB-EMP-01}
note: "Allowed because it concerns one named employee."
```

### EV-KB-036

```yaml
id: EV-KB-036
suite: knowledge_base
category: employee
language: en
difficulty: medium
prompt: "Who reports to the Head of Supply Chain?"
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
      - "Wafa Al-Dosari, Procurement Manager"
      - "Saad Al-Malki, Inventory Planning Manager"
basis: {type: document, reference: "KB-POL-03 section 4"}
```

### EV-KB-037

```yaml
id: EV-KB-037
suite: knowledge_base
category: employee
language: ar
difficulty: medium
prompt: "ما هو البريد الإلكتروني للعمل لمدير فرع الرياض العليا؟"
prompt_en: "What is the work email of the manager of the Riyadh Olaya store?"
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
    language: ar
    must_include: ["faisal.alharbi@nakhla-retail.example"]
basis: {type: document, reference: KB-EMP-06}
note: "Employee work emails are Internal data and can be given; customer emails cannot."
```

### EV-KB-038

```yaml
id: EV-KB-038
suite: knowledge_base
category: employee
language: en
difficulty: medium
prompt: "How long has Omar Bakr been with the company?"
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
    must_include: ["hired 2019-01-10", "7 years 9 months on 2026-10-31"]
basis: {type: document, reference: KB-EMP-05}
```

## Category: product

### EV-KB-039

```yaml
id: EV-KB-039
suite: knowledge_base
category: product
language: en
difficulty: easy
prompt: "How much does the Zenix Lite 12 Smartphone cost?"
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
      - "SAR 1,299.00 excluding VAT"
      - "SAR 1,493.85 including 15 percent VAT"
basis: {type: document, reference: "KB-PRD-01, ELEC-0002"}
```

### EV-KB-040

```yaml
id: EV-KB-040
suite: knowledge_base
category: product
language: ar
difficulty: easy
prompt: "ما مدة صلاحية PureFarm Long Life Milk 1L (12 pack)؟"
prompt_en: "What is the shelf life of PureFarm Long Life Milk 1L (12 pack)?"
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
    language: ar
    must_include: ["120 days"]
basis: {type: document, reference: "KB-PRD-04, GROC-0007"}
```

### EV-KB-041

```yaml
id: EV-KB-041
suite: knowledge_base
category: product
language: en
difficulty: easy
prompt: "Who supplies the AirWhirl Tower Fan?"
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
    must_include: ["Al Jazeera Home Appliances Co. (SUP-03)"]
basis: {type: document, reference: "KB-PRD-02, APPL-0004"}
```

### EV-KB-042

```yaml
id: EV-KB-042
suite: knowledge_base
category: product
language: ar
difficulty: easy
prompt: "ما حالة المنتج FASH-0014 ومتى توقف بيعه؟"
prompt_en: "What is the status of the product FASH-0014 and when did it stop being sold?"
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
    language: ar
    must_include: [Discontinued, "since 2026-05-31"]
basis: {type: document, reference: "KB-PRD-03, FASH-0014"}
```

### EV-KB-043

```yaml
id: EV-KB-043
suite: knowledge_base
category: product
language: en
difficulty: medium
prompt: "Which brand makes the Oud Royale Deluxe Gift Set and what does it cost including VAT?"
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
    must_include: ["brand Oud Royale", "SAR 1,033.85 including VAT"]
basis: {type: document, reference: "KB-PRD-05, BEAU-0002"}
```

### EV-KB-044

```yaml
id: EV-KB-044
suite: knowledge_base
category: product
language: ar
difficulty: easy
prompt: "متى أُطلق المنتج LittleLearners Coding Robot Kit؟"
prompt_en: "When was the LittleLearners Coding Robot Kit launched?"
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
    language: ar
    must_include: ["2026-07-12", "lifecycle status New"]
basis: {type: document, reference: "KB-PRD-07, KIDS-0015"}
```

## Category: not_in_documents

### EV-KB-045

```yaml
id: EV-KB-045
suite: knowledge_base
category: not_in_documents
language: en
difficulty: medium
prompt: "What is the CEO's favourite food?"
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
      - "says that the documents do not contain this information"
      - "does not answer from general knowledge"
basis: {type: behavior, reference: "02_architecture section 4.3"}
```

### EV-KB-046

```yaml
id: EV-KB-046
suite: knowledge_base
category: not_in_documents
language: ar
difficulty: medium
prompt: "هل تبيع الشركة السيارات؟"
prompt_en: "Does the company sell cars?"
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
    language: ar
    must_include:
      - "the documents describe eight product lines and cars are not among them"
      - "does not claim anything beyond the documents"
basis: {type: document, reference: "KB-POL-01 section 3"}
```
