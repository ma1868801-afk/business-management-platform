"""Parse every real SQL example in rag_sources/ and report failures. Run directly:
    python3 tests/test_sql_parser_corpus.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.guards.sql_parser import parse, ParseError, LexError  # noqa: E402

PAT = re.compile(r"```sql\n(.*?)```", re.S)


def extract():
    out = []
    for f in sorted((ROOT / "rag_sources").rglob("*.md")):
        text = f.read_text()
        for i, m in enumerate(PAT.finditer(text)):
            sql = m.group(1).strip()
            # Strip a trailing semicolon the way the real tool would (single statement, no ;).
            sql = sql.rstrip().rstrip(";")
            out.append((str(f.relative_to(ROOT)), i, sql))
    return out


def main():
    examples = extract()
    failures = []
    for path, i, sql in examples:
        try:
            parse(sql)
        except (ParseError, LexError) as e:
            failures.append((path, i, sql, str(e)))
    print(f"{len(examples)} examples, {len(failures)} failed to parse")
    for path, i, sql, err in failures:
        print("=" * 80)
        print(path, "#", i, " -> ", err)
        print(sql)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
