"""Pull every ```sql fenced block out of rag_sources/ for use as a validator test corpus."""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAT = re.compile(r"```sql\n(.*?)```", re.S)


def extract():
    out = []
    for f in sorted((ROOT / "rag_sources").rglob("*.md")):
        text = f.read_text()
        for i, m in enumerate(PAT.finditer(text)):
            sql = m.group(1).strip()
            out.append((str(f.relative_to(ROOT)), i, sql))
    return out


if __name__ == "__main__":
    examples = extract()
    print(f"{len(examples)} SQL blocks found", file=sys.stderr)
    for path, i, sql in examples:
        print(f"-- {path}#{i}")
        print(sql)
        print()
