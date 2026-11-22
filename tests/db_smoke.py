"""Dev-only integration smoke test: validate real SQL patterns with sql_validator, then
actually run them against the loaded Phase 2 test database via the `psql` CLI (since
`psycopg` cannot be installed in this sandbox -- see app/tools/postgres_tool.py). This is a
stand-in for exercising `postgres_tool` end-to-end; it is not what ships.

Usage: python3 tests/db_smoke.py
Expects the Phase 2 test cluster running at /tmp/pgsock:54329, database `bmp` (see
database/README.md).
"""
import json
import re
import subprocess
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.guards.sql_validator import validate_sql  # noqa: E402

PGARGS = ["psql", "-h", "/tmp/pgsock", "-p", "54329", "-U", "bmp_readonly", "-d", "bmp"]
PAT = re.compile(r"```sql\n(.*?)```", re.S)


def run_psql(sql: str) -> tuple[int, str, str]:
    env = {"PGPASSWORD": "ro_test_pw"}
    proc = subprocess.run(PGARGS + ["-At", "-c", sql], capture_output=True, text=True, env=env, timeout=15)
    return proc.returncode, proc.stdout, proc.stderr


def main():
    examples = []
    for f in sorted((ROOT / "rag_sources").rglob("*.md")):
        text = f.read_text()
        for i, m in enumerate(PAT.finditer(text)):
            examples.append((str(f.relative_to(ROOT)), i, m.group(1).strip()))

    ok, validated_but_failed, invalid = 0, 0, 0
    for path, i, sql in examples:
        max_rows = 50000 if "LIMIT 50000" in sql else 500
        v = validate_sql(sql, max_rows=max_rows)
        if not v.ok:
            print(f"VALIDATOR REJECTED {path}#{i}: {v.code} {v.message}")
            invalid += 1
            continue
        rc, out, err = run_psql(v.sql)
        if rc != 0:
            print(f"DB EXEC FAILED {path}#{i}: {err.strip()[:300]}")
            validated_but_failed += 1
            continue
        ok += 1
    print(f"\n{len(examples)} examples: {ok} validated+executed OK, {validated_but_failed} validated but DB-rejected, {invalid} validator-rejected")
    return 1 if (validated_but_failed or invalid) else 0


if __name__ == "__main__":
    raise SystemExit(main())
