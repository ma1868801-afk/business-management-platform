"""Run the SQL validator over every real SQL example in rag_sources/ (the 51 tested patterns).
Every one of them must validate ok=True, per 05_security_and_guardrails.md section 6.6
("all 51 pass the emulation" after each raw-row example was given a LIMIT).
Run directly: python3 tests/test_sql_validator_corpus.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.guards.sql_validator import validate_sql  # noqa: E402

PAT = re.compile(r"```sql\n(.*?)```", re.S)


def extract():
    out = []
    for f in sorted((ROOT / "rag_sources").rglob("*.md")):
        text = f.read_text()
        for i, m in enumerate(PAT.finditer(text)):
            sql = m.group(1).strip()
            out.append((str(f.relative_to(ROOT)), i, sql))
    return out


def main():
    examples = extract()
    failures = []
    for path, i, sql in examples:
        r = validate_sql(sql, max_rows=500)
        if not r.ok:
            failures.append((path, i, sql, r.code, r.message, r.hint))
    print(f"{len(examples)} examples, {len(failures)} failed validation")
    for path, i, sql, code, message, hint in failures:
        print("=" * 80)
        print(path, "#", i, "->", code, message, "|", hint)
        print(sql)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
