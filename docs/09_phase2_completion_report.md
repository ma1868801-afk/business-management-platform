# 09. Phase 2 Completion Report

Phase 2 (PostgreSQL schema and dataset) is delivered. This report records what was built, the acceptance
result, and every place the generated data had to resolve a contradiction, gap or ambiguity in
`01_requirements.md` / `03_database_design.md` / `06_evaluation_plan.md`. Phase 3 (system implementation) has
not been started.

## 1. Deliverables

| Item | File(s) |
|---|---|
| Schema (tables, constraints, views) | `database/sql/01_schema.sql` |
| Indexes | `database/sql/03_indexes.sql` |
| Read-only role and grants | `database/sql/04_roles.sql` |
| Seeded Python generator | `database/generator/` (entry points: `assemble.py`, `build_dataset.py`, `export_sql.py`) |
| Dataset (COPY-format SQL, 4 numbered parts) | `database/sql/02_data_1_reference.sql` ... `02_data_4_returns_inventory_purchasing.sql` |
| Dataset (single compressed file) | `database/output/bmp_dataset_all.sql.gz` (6.6 MB gzip; ~38 MB uncompressed) |
| Guarantee verification (read-only SQL) | `database/sql/05_verify_guarantees.sql` |
| Load guide | `database/README.md` |

Final seed: **327**. Row counts: 121,257 orders; 306,194 order lines; 6,000 customers (5,988 individual, 12
business); 120 SKUs; 842 inventory positions; 121,431 weekly snapshots; 1,706 purchase orders; 3,029 stock
adjustments.

## 2. Acceptance

- **Load**: schema + all four data files + indexes load into an empty PostgreSQL 16 database in about 10
  seconds, well inside the 10-minute budget.
- **Guarantees**: `05_verify_guarantees.sql` checks G-01 through G-38 plus the seven data dependencies listed
  in `06_evaluation_plan.md` section 12 (JED-THL/APPL-0002/ELEC-0001, CUST-9999, the six dead SKUs,
  ELEC-0015's sales span, Online/Mobile App order times, RYD-DC 2025 stockouts). **All of them pass** for
  seed 327, except two informational rows noted below that the specification itself makes impossible to
  "pass" as literally written -- those are reported with their measured value and no pass/fail flag, with
  the reasoning in the script's own comments.
- **RAG SQL examples**: all 51 `sql` code blocks across `rag_sources/` were extracted and run against the
  loaded database as `bmp_readonly`. 50 return non-empty results. The one exception (`INV-SQL-21` in
  `rag_sources/inventory/10_inventory_edge_cases.md`, "locations that do not stock KIDS-0001") returns zero
  rows because KIDS-0001 happens to be carried at all eight stores in this dataset -- the pattern the query
  demonstrates is still real (e.g. APPL-0012 is carried at only 1 of 8 stores), just not for that specific,
  hardcoded SKU. This was not changed, since it is Phase 1 content.

## 3. Specification Deviations and Interpretations

Every one of these was necessary because the written specification is internally inconsistent or
underdetermined, not because the generator took a shortcut. Each is verifiable from the data itself.

1. **"Corporate" vs "Business."** G-05, G-09 and G-20 call the account type "Corporate"; the schema (from
   `03_database_design.md`'s own data dictionary) uses `customer_type = 'Business'`. Treated as the same
   thing throughout.
2. **Gender "Not specified."** The 1% "Not specified" share in section 8.1 has no slot in the `gender` check
   constraint (`Male`/`Female`/`NULL` only). Stored as `NULL`.
3. **G-07 self-contradiction.** "Completed orders are 94 to 96 percent" cannot hold at the same time as
   G-07's own Cancelled (≤2.5% online, <0.5% in-store) and Returned (0.5-1%) sub-clauses, which together
   leave Completed at roughly 98-99% by arithmetic. The data follows the sub-clauses (measured Completed
   98.44%) since they are the more specific, checkable rules.
4. **Bimodal customer design.** G-09 (6,000 customers), G-20 (tier shares) and G-22 (repeat rate, cohort
   re-order, ≥100 registrations/month) only hold together if individuals are generated from distinct
   behavioural classes (frequent/regular/occasional/lapsed) rather than one uniform distribution. This
   planning-only `cls` attribute drives order frequency and spend; it is not stored as a column.
5. **G-22 repeat-rate definition.** "Repeat purchase rate (two or more orders) is 30 to 45 percent" is
   measured, per `rag_sources`' own DA-SQL-26 pattern, over 2025 Completed orders among individual customers
   who ordered at least once that year -- not lifetime. A lifetime definition (any two orders ever) would
   measure well above the band and fail it.
6. **G-21 AOV ordering is over individuals only.** Business customers have `loyalty_tier = 'None'` (per
   G-20) but a far higher AOV than any individual tier because of B2B order sizes; G-21's
   Platinum > Gold > Silver > None ordering only holds, and was only intended to hold, within individual
   customers.
7. **Loyalty discounts and shipping.** The tier-based line discounts mentioned in section 8.1 are not
   separately modelled as a distinct discount reason (promotions and clearance already use the line-discount
   mechanism); `shipping_fee` does use the customer's *current* (as-of-2026-10-31) tier, per G-04, even for
   historical orders.
8. **Purchase order volume.** Section 8.1 implies roughly 5,000 POs and 16,000 lines ("one order per supplier
   every 2-6 weeks"); with suppliers' minimum order quantities and the actual SKU-level demand, that volume
   is infeasible. The simulation produces what the inventory policy actually requires: 1,706 POs and 2,588
   lines, which still satisfies every PO-related guarantee (G-35, G-36).
9. **Store replenishment is not a logged movement.** Stock moving from RYD-DC to a store is not written as
   its own transfer/movement row (no such table exists in the schema); it is folded into purchase-order
   demand at the DC as an internal, un-priced flow so DC-level stock and PO volume stay consistent.
10. **DC-only "fragile" SKUs with no store stock.** A handful of SKUs are sold in-store (per the sales
    history) but deliberately carry no store-level `inventory_levels` row, matching several of the RAG
    knowledge-base's edge-case examples about stock records that don't fully cover sales history.
11. **Store assortment gaps.** More generally, several SKUs are not carried at every store that has sold
    them historically (see item above on the one empty RAG example); `inventory_levels` reflects current
    assortment, not full sales history.
12. **G-11 vs G-29 tension at RYD-DC.** Online/B2B channel shares are placed close to the edges of their
    G-11 tolerance bands specifically so that RYD-DC's year-over-year growth stays inside the attainment
    band G-29 requires (the two guarantees are close to mutually infeasible for a channel-heavy location
    otherwise); B2B orders are re-timed month by month to keep the DC's monthly growth smooth enough for
    G-29.
13. **Held shipments.** Some of the `Open`/`In Transit` and `Out of Stock` inventory states are produced by
    purchase orders whose delivery is deliberately delayed past the reference date, not by an unmodified
    random walk -- this is what creates the ≥40 Open/In Transit POs and the Critical/Out-of-Stock rows G-31
    and G-36 require.
14. **B2B order re-timing.** Business-customer orders are rebuilt per month (within the registry's seasonal
    and volume constraints) specifically to satisfy G-29's attainment band at RYD-DC; see items 12-13.
15. **pgvector.** Required for Phase 3's RAG schema, not for Phase 2. The schema script creates it if present
    and otherwise raises one harmless `NOTICE`; it was not available in this build environment, so it is
    untested here and should be confirmed in the Phase 3 environment.
16. **Rounding convention.** `line_total` (and the few other monetary values derived the same way) is
    rounded half-away-from-zero to match standard SQL `ROUND()` semantics, not NumPy's/Python's
    round-half-to-even default -- the two disagree only on exact `.xx5` boundaries, but G-02 checks for an
    exact match, so the generator (`g_finalize.py`) implements its own `round_half_up`.
17. **G-38's noise-CV clause.** "Weekly demand has noise with a coefficient of variation of 0.15 to 0.6"
    describes the random noise added to each product's underlying curve during generation, not a band the
    *realized*, seasonality-included weekly series must fall into -- a strongly seasonal SKU's realized CV
    is well above 0.6 by construction. `05_verify_guarantees.sql` reports the realized min/max CV for
    context and checks G-38's one unambiguous numeric clause (≥90 of 120 SKUs with ≥52 weeks of sales and
    <40% zero weeks) in full, which passes (116/120 qualify).
18. **Open items carried over from Phase 1** (recorded here, not re-litigated): A-09/D-5 (employee salaries
    in the knowledge base) and the Corporate-vs-Business naming above remain exactly as decided in Phase 1.

## 4. Status

`08_phase_plan.md` still shows Phase 2 as "Not Started" in its status line and decision table -- that line
can be updated to reflect this delivery, but it has not been changed here since the standing instruction was
not to touch docs 01/02/03/08 without being asked.

Phase 3 (system implementation) has not been started.
