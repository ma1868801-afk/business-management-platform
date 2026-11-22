"""Negative cases the validator must reject, drawn from 05_security_and_guardrails.md
section 6.6 ("negative cases for each rule... were all rejected by the emulation") and
section 16's SQL red team list. Run directly: python3 tests/test_sql_validator_negative.py
"""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.guards.sql_validator import validate_sql  # noqa: E402

CASES = [
    ("SELECT * FROM customers", "V-06"),
    ("SELECT c.* FROM customers c", "V-06"),
    ("SELECT email FROM customers LIMIT 5", "V-07"),
    ("SELECT phone FROM customers LIMIT 5", "V-07"),
    ("SELECT customer_id FROM customers; DROP TABLE returns", "V-01"),
    ("UPDATE products SET list_price = 0", "V-02"),
    ("INSERT INTO products (sku) VALUES ('x')", "V-02"),
    ("DELETE FROM sales_orders", "V-02"),
    ("WITH x AS (DELETE FROM sales_orders RETURNING *) SELECT * FROM x", None),  # must still fail, any code
    ("DROP TABLE products", "V-03"),
    ("CREATE TABLE evil (x int)", "V-03"),
    ("GRANT SELECT ON products TO public", "V-03"),
    ("SET statement_timeout = 0", "V-03"),
    ("EXPLAIN SELECT * FROM products", "V-03"),
    ("SELECT pg_sleep(10)", "V-08"),
    ("SELECT pg_read_file('/etc/passwd')", "V-08"),
    ("SELECT lo_import('/etc/passwd')", "V-08"),
    ("SELECT * FROM rag.chunks LIMIT 5", None),  # schema-qualified FROM: parser-level reject
    ("SELECT now()", "V-11"),
    ("SELECT CURRENT_DATE", "V-11"),
    ("SELECT clock_timestamp()", "V-11"),
    ("SELECT random()", "V-11"),
    ("SELECT order_id FROM sales_orders ORDER BY order_id", "V-09"),  # raw rows, no LIMIT
    ("SELECT order_id FROM sales_orders ORDER BY order_id LIMIT 100000", "V-10"),
    ("SELECT full_name FROM customers LIMIT 10", "V-15"),
    ("SELECT dblink('x', 'select 1')", "V-08"),
    ("COPY products TO '/tmp/x.csv'", None),
    ("CALL some_procedure()", None),
    ("DO $$ BEGIN RAISE NOTICE 'hi'; END $$", None),
    ("SELECT * FROM products FOR UPDATE", "V-03"),  # V-03 is checked before V-06 (rule table order)
    ("SELECT product_id FROM products FOR UPDATE LIMIT 5", "V-03"),
    ("SELECT product_id FROM products FOR SHARE LIMIT 5", "V-03"),
    ("SELECT set_config('statement_timeout', '0', false)", "V-08"),
    ("SELECT current_setting('data_directory')", "V-08"),
]

POSITIVE = [
    "SELECT product_id FROM products LIMIT 10",
    "SELECT COUNT(*) FROM customers",
    "SELECT customer_code, full_name FROM customers WHERE customer_type = 'Business' LIMIT 10",
    "SELECT customer_code, full_name FROM customers WHERE customer_code LIKE 'CUST-B%' LIMIT 10",
]


def main():
    failed = 0
    for sql, expected_code in CASES:
        r = validate_sql(sql, max_rows=500)
        if r.ok:
            print(f"FAIL (should have been rejected): {sql!r}")
            failed += 1
            continue
        if expected_code is not None and r.code != expected_code:
            print(f"WRONG CODE for {sql!r}: got {r.code} ({r.message}), expected {expected_code}")
            failed += 1
    for sql in POSITIVE:
        r = validate_sql(sql, max_rows=500)
        if not r.ok:
            print(f"FAIL (should have been accepted): {sql!r} -> {r.code} {r.message}")
            failed += 1
    print(f"{len(CASES)} negative + {len(POSITIVE)} positive cases, {failed} unexpected results")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
