"""Run the Pandas validator over the 20 sandbox-eligible Python examples (DA-PY-01..15,
INV-PY-01..03, INV-PY-07, INV-PY-08). INV-PY-04..06 are the regression tool's trusted
scikit-learn implementations (05_security_and_guardrails.md section 7.3) and never run
through this validator or the sandbox, so they are excluded here.
Run directly: python3 tests/test_pandas_validator_corpus.py
"""
import re
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.extract_python_examples import extract  # noqa: E402
from app.guards.pandas_validator import validate_pandas_code  # noqa: E402

TRUSTED_NOT_SANDBOXED = re.compile(r"INV-PY-0[456]:")


def main():
    examples = extract()
    failures = []
    skipped = 0
    for path, heading, code in examples:
        if TRUSTED_NOT_SANDBOXED.match(heading):
            skipped += 1
            continue
        r = validate_pandas_code(code)
        if not r.ok:
            failures.append((path, heading, code, r.code, r.message, r.hint))
    print(f"{len(examples)} examples ({skipped} trusted/not sandboxed), {len(failures)} failed validation")
    for path, heading, code, c, m, h in failures:
        print("=" * 80)
        print(path, "::", heading, "->", c, m, "|", h)
        print(code)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
