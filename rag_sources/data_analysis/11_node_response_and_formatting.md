# Data Analysis: Node Response and Formatting

- Document ID: DA-11
- Index: data_analysis
- Purpose: how the Data Analysis subgraph writes its final node response, so the aggregator can merge it and the output guard can verify every number.

## Node Response Structure

The subgraph returns exactly this structure. Values written as `<...>` below are placeholders that the node fills from the SQL result, `result` or `facts`; the examples never contain real figures.

| Field | Rule |
|---|---|
| `subgraph` | Always `data_analysis`. |
| `status` | `ok` when the question was fully answered; `partial` when part of it could not be answered; `failed` after the retry budget is spent. |
| `answer_en` | Two to five sentences in English with the key numbers and the period. No Markdown tables. No SQL. |
| `key_figures` | Up to 8 items `{label, value, unit}` with numeric values (not formatted strings). Units: SAR, percent, points, orders, units, customers, ratio. |
| `assumptions` | Short statements that change how a number is read: revenue definition, period, exclusions (such as `RYD-DC`), the status filter, sampling. |
| `method` | `tools_used` (postgres, pandas, hypothesis test), `bypassed` (for example `pandas`) and `queries` (number of SQL queries). |
| `sources` | Tables or views used, as `{type: table|view, name}`. |
| `warnings` | Limitations: partial year, small sample, truncation, undefined growth, estimated period. |
| `error` | `null` when the status is `ok`; otherwise a plain explanation. |

In the JSON examples the placeholders are quoted only so that the block stays valid JSON. Real `value` fields are numbers, never strings.

## Writing the Answer

1. Lead with the answer to the question in the first sentence, using the user's own terms (for example "net revenue" if they said "sales").
2. State the period and the revenue definition once: "Net revenue (Completed orders, excluding VAT), 1 January to 31 December 2025."
3. Give the comparison or ranking that was asked for, in the order requested. Keep rankings to the top items needed (top 3 or top 5 unless the user asked for all).
4. Add the one fact that explains the number when it is in the data (for example "the Distribution Center is excluded from the ranking").
5. Close with a caution only if it changes the reading. Do not add generic advice.
6. Every number in `answer_en` must appear in `key_figures`, `result` or `facts`. Do not calculate new numbers in the text.

## Number and Unit Style

- Money: "SAR 1,234,567.89" with two decimals for exact figures; "SAR 12.35 million" when rounding for readability. Keep one style within one answer.
- Percentages: at most one decimal in sentences (12.4 percent) and two decimals in `key_figures`. Write "percent" in sentences and use the number in `key_figures`.
- Percentage point differences are written "points".
- Dates: ISO format (2026-10-31) in `assumptions`; readable form ("31 October 2026") in sentences.
- Western digits (0-9) only. The aggregator translates to Arabic if needed and keeps numbers, SKU codes and branch codes unchanged.
- Product, branch and customer references use the canonical name and code once, for example "Riyadh Olaya Flagship (RYD-OLY)".

## When Pandas Was Bypassed

If the question needed only a list or a single aggregate, set `method.bypassed` to `["pandas"]` and describe the result directly. For a list, give at most 10 rows in the sentence form "A (value), B (value)"; mention the total number of rows if more exist.

## Partial and Failed Responses

- `partial`: answer the part that worked in `answer_en`, name the part that failed in `warnings` and set `error` to a plain explanation.
- `failed`: `answer_en` states that the question could not be answered and why in plain words (for example "the query exceeded the time limit"), without technical stack traces. `key_figures` is empty.
- Never fill a gap with an estimate and present it as measured. If an estimate is useful, label it as an estimate and name the method.

## Response Examples

### A single aggregate (Pandas bypassed)

```json
{
  "subgraph": "data_analysis",
  "status": "ok",
  "answer_en": "Net revenue for <period> was SAR <net_revenue> from <orders> orders.",
  "key_figures": [
    {"label": "Net revenue <period>", "value": "<net_revenue>", "unit": "SAR"},
    {"label": "Completed orders <period>", "value": "<orders>", "unit": "orders"}
  ],
  "assumptions": ["Net revenue is the sum of line totals of Completed orders and excludes VAT.", "Period: <start> to <end>."],
  "method": {"tools_used": ["postgres"], "bypassed": ["pandas"], "queries": 1},
  "sources": [{"type": "view", "name": "v_sales_detail"}],
  "warnings": [],
  "error": null
}
```

### A comparison with computation

```json
{
  "subgraph": "data_analysis",
  "status": "ok",
  "answer_en": "Net revenue grew by <growth_pct> percent from <year_a> to <year_b>, from SAR <value_a> to SAR <value_b>.",
  "key_figures": [
    {"label": "Net revenue <year_a>", "value": "<value_a>", "unit": "SAR"},
    {"label": "Net revenue <year_b>", "value": "<value_b>", "unit": "SAR"},
    {"label": "Growth", "value": "<growth_pct>", "unit": "percent"}
  ],
  "assumptions": ["Net revenue is the sum of line totals of Completed orders and excludes VAT."],
  "method": {"tools_used": ["postgres", "pandas"], "bypassed": [], "queries": 1},
  "sources": [{"type": "view", "name": "v_sales_detail"}],
  "warnings": [],
  "error": null
}
```

### A hypothesis test

```json
{
  "subgraph": "data_analysis",
  "status": "ok",
  "answer_en": "Average order value was SAR <mean_a> for <group_a> and SAR <mean_b> for <group_b>. Welch t-test: t = <t>, p <p_text>. The difference is <significant_or_not> at the 5 percent level (effect size d = <d>).",
  "key_figures": [
    {"label": "Mean order value <group_a>", "value": "<mean_a>", "unit": "SAR"},
    {"label": "Mean order value <group_b>", "value": "<mean_b>", "unit": "SAR"},
    {"label": "p-value", "value": "<p_value>", "unit": "ratio"},
    {"label": "Cohen's d", "value": "<d>", "unit": "ratio"}
  ],
  "assumptions": ["Orders are Completed orders of <period>.", "Two-sided test at the 5 percent level."],
  "method": {"tools_used": ["postgres", "pandas", "hypothesis_test"], "bypassed": [], "queries": 1},
  "sources": [{"type": "view", "name": "v_sales_detail"}],
  "warnings": ["Orders by the same customer are not fully independent."],
  "error": null
}
```

### A period with no data

```json
{
  "subgraph": "data_analysis",
  "status": "ok",
  "answer_en": "No sales data exists for <requested_period>; the data ends on 2026-10-31.",
  "key_figures": [],
  "assumptions": ["The dataset covers 2024-01-01 to 2026-10-31."],
  "method": {"tools_used": [], "bypassed": ["postgres", "pandas"], "queries": 0},
  "sources": [],
  "warnings": ["A forecast of unit demand can be requested from the Inventory subgraph."],
  "error": null
}
```

### A failed response

```json
{
  "subgraph": "data_analysis",
  "status": "failed",
  "answer_en": "The question could not be answered because the query did not finish within the time limit.",
  "key_figures": [],
  "assumptions": [],
  "method": {"tools_used": ["postgres"], "bypassed": [], "queries": 3},
  "sources": [],
  "warnings": [],
  "error": "Query timed out after the retry budget was used."
}
```

## Checklist Before Returning

1. The status filter and period are stated.
2. Every number in the text is in `key_figures`, `result` or `facts`.
3. The user's language of key terms is respected, and the answer is in English (the aggregator translates).
4. No SQL, code or table names appear in `answer_en`.
5. No email, phone or individual customer name appears anywhere.
6. Warnings list any partial period, small sample or truncation.
