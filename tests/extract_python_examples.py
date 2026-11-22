"""Pull every ```python fenced block out of rag_sources/, tagged with the nearest preceding
heading (so DA-PY-xx / INV-PY-xx ids can be matched against the sandbox-vs-trusted split in
05_security_and_guardrails.md section 7.3)."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAT = re.compile(r"```python\n(.*?)```", re.S)
HEADING = re.compile(r"^#{2,4}\s+(.*)$", re.M)


def extract():
    out = []
    for f in sorted((ROOT / "rag_sources").rglob("*.md")):
        text = f.read_text()
        headings = [(m.start(), m.group(1).strip()) for m in HEADING.finditer(text)]
        for m in PAT.finditer(text):
            code = m.group(1)
            # nearest heading before this code block
            heading = ""
            for pos, h in headings:
                if pos < m.start():
                    heading = h
                else:
                    break
            out.append((str(f.relative_to(ROOT)), heading, code))
    return out


if __name__ == "__main__":
    for path, heading, code in extract():
        print(f"-- {path} :: {heading}")
        print(code)
        print()
