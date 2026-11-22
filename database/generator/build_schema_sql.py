"""Build database/sql/01_schema.sql, 03_indexes.sql and 04_roles.sql from docs/03_database_design.md.

The data dictionary, views, index list and role script in doc 03 are the contract; this script copies them
and adds CHECK constraints for enumerated values and sign rules. Run: python3 build_schema_sql.py
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = (ROOT / "docs" / "03_database_design.md").read_text()
OUT = ROOT / "database" / "sql"

ORDER = ["branches", "product_categories", "suppliers", "products", "customers", "promotions", "calendar",
         "monthly_sales_targets", "sales_orders", "sales_order_items", "sales_returns", "inventory_levels",
         "inventory_snapshots", "purchase_orders", "purchase_order_items", "stock_adjustments"]

CHECKS = {
    "branches": ["region IN ('Central','Western','Eastern','Southern')",
                 "branch_type IN ('Flagship Store','Standard Store','Express Store','Distribution Center')",
                 "area_sqm > 0 AND staff_count > 0"],
    "suppliers": ["lead_time_days BETWEEN 1 AND 60", "min_order_qty > 0", "payment_terms_days >= 0",
                  "on_time_delivery_pct BETWEEN 0 AND 100", "quality_rating BETWEEN 1.0 AND 5.0",
                  "billing_currency IN ('SAR','USD','EUR','AED')", "contract_end_date > contract_start_date"],
    "products": ["unit_price > unit_cost AND unit_cost > 0",
                 "unit_of_measure IN ('Each','Pack','Box','Kg','Set')",
                 "lifecycle_status IN ('New','Active','Declining','Discontinued')",
                 "(lifecycle_status = 'Discontinued') = (discontinued_date IS NOT NULL)"],
    "customers": ["customer_type IN ('Individual','Business')",
                  "customer_segment IN ('Premium','Core','Occasional')",
                  "loyalty_tier IN ('None','Silver','Gold','Platinum')",
                  "acquisition_channel IN ('Walk-in','Website','Mobile App','Social Media','Referral','B2B Sales')",
                  "gender IS NULL OR gender IN ('Male','Female')",
                  "age_group IS NULL OR age_group IN ('18-24','25-34','35-44','45-54','55+')",
                  "loyalty_points >= 0"],
    "promotions": ["promotion_type IN ('Percentage Off','Bundle Deal','Seasonal Sale','Loyalty Bonus','Clearance')",
                   "channel_scope IN ('All','In-Store','Online')", "discount_pct > 0 AND discount_pct <= 50",
                   "end_date >= start_date"],
    "calendar": ["day_of_week BETWEEN 0 AND 6", "quarter BETWEEN 1 AND 4", "month BETWEEN 1 AND 12",
                 "climate_season IN ('Winter','Spring','Summer','Autumn')"],
    "monthly_sales_targets": ["target_revenue > 0", "EXTRACT(DAY FROM target_month) = 1"],
    "sales_orders": ["channel IN ('In-Store','Online','Mobile App','B2B')",
                     "status IN ('Completed','Cancelled','Returned','Processing')",
                     "payment_method IN ('Mada','Credit Card','Apple Pay','STC Pay','Cash','Cash on Delivery','Buy Now Pay Later','Bank Transfer')",
                     "order_hour BETWEEN 0 AND 23", "items_count >= 1", "currency = 'SAR'",
                     "subtotal_amount >= 0 AND vat_amount >= 0 AND shipping_fee >= 0 AND total_amount >= 0"],
    "sales_order_items": ["quantity >= 1", "unit_price > 0 AND unit_cost > 0", "discount_pct BETWEEN 0 AND 50",
                          "line_total >= 0 AND line_cost >= 0"],
    "sales_returns": ["quantity_returned >= 1", "refund_amount >= 0",
                      "return_reason IN ('Defective','Wrong Item','Changed Mind','Late Delivery','Not as Described','Damaged in Transit')"],
    "inventory_levels": ["quantity_on_hand >= 0 AND quantity_reserved >= 0", "reorder_point >= safety_stock"],
    "inventory_snapshots": ["quantity_on_hand >= 0", "stockout_days BETWEEN 0 AND 7"],
    "purchase_orders": ["status IN ('Received','Partially Received','In Transit','Open','Cancelled')",
                        "currency = 'SAR'", "total_amount >= 0"],
    "purchase_order_items": ["quantity_ordered > 0", "quantity_received BETWEEN 0 AND quantity_ordered", "unit_cost > 0"],
    "stock_adjustments": ["reason IN ('Damage','Expiry','Shrinkage','Count Correction','Display Sample')"],
}

dd = SRC.split("## 4. Data Dictionary")[1].split("## 5. Views")[0]
tables = {}
for sec in re.split(r"\n### `", dd)[1:]:
    name = sec.split("`", 1)[0]
    pk = re.search(r"\*\*Primary key:\*\* `([^`]+)`", sec).group(1)
    fks = []
    m = re.search(r"\*\*Foreign keys:\*\* (.+)", sec)
    if m:
        for fk in re.findall(r"`([^`]+)`", m.group(1)):
            fks.append(re.match(r"(\w+) -> (\w+)\.(\w+)", fk).groups())
    cols = [(r[0], r[1].strip(), r[2] == "no")
            for r in re.findall(r"^\| `(\w+)` \| ([^|]+) \| (no|yes) \|", sec, flags=re.M)]
    tables[name] = dict(pk=pk, fks=fks, cols=cols)
assert set(tables) == set(ORDER)

ddl = []
for t in ORDER:
    d = tables[t]
    lines = []
    for c, typ, notnull in d["cols"]:
        if t == "inventory_levels" and c == "quantity_available":
            lines.append("  quantity_available INTEGER GENERATED ALWAYS AS (quantity_on_hand - quantity_reserved) STORED")
        else:
            lines.append(f"  {c} {typ}{' NOT NULL' if notnull else ''}")
    lines.append(f"  CONSTRAINT pk_{t} PRIMARY KEY ({d['pk']})")
    for col, rt, rc in d["fks"]:
        lines.append(f"  CONSTRAINT fk_{t}_{col} FOREIGN KEY ({col}) REFERENCES {rt}({rc})")
    for i, ck in enumerate(CHECKS.get(t, []), start=1):
        lines.append(f"  CONSTRAINT ck_{t}_{i} CHECK ({ck})")
    ddl.append(f"CREATE TABLE {t} (\n" + ",\n".join(lines) + "\n);")

blocks = re.findall(r"```sql\n(.*?)```", SRC, flags=re.S)
views = [b.strip() for b in blocks if b.startswith("CREATE VIEW")]
idx = [b for b in blocks if b.startswith("CREATE UNIQUE INDEX") or b.startswith("CREATE INDEX")][0].strip()
role = [b for b in blocks if b.startswith("CREATE ROLE")][0].strip()
assert len(views) == 3

header = """-- Business Management Platform, Phase 2: schema (tables, constraints, views).
-- Generated by database/generator/build_schema_sql.py from docs/03_database_design.md. Do not edit by hand.
-- Target: PostgreSQL 16. Run on an empty database as a role that may create schemas and tables.
"""
ext = """
-- pgvector is needed from Phase 3 (schema rag). The load does not depend on it, so a missing extension is only a notice.
DO $$
BEGIN
  CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'pgvector is not available on this server (%). Install it before Phase 3.', SQLERRM;
END $$;

CREATE SCHEMA IF NOT EXISTS rag;

"""
(OUT / "01_schema.sql").write_text(header + ext + "\n\n".join(ddl) + "\n\n" + "\n\n".join(views) + "\n")
(OUT / "03_indexes.sql").write_text("-- Recommended indexes (docs/03_database_design.md section 6). Created after the data load for speed.\n"
                                    + idx + "\nANALYZE;\n")
(OUT / "04_roles.sql").write_text("-- Read-only role and grants (docs/03_database_design.md section 7).\n"
                                  "-- Usage: psql -v readonly_password='<password>' -f 04_roles.sql\n" + role + "\n")
print("tables", len(ddl), "views", len(views))
