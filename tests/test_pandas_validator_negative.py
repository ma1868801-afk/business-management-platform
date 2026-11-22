"""Escape attempts the Pandas validator must reject, per 05_security_and_guardrails.md
section 7.4 ("14 negative cases... an import, open, to_csv, a dunder attribute, str.format
traversal, read_csv, query, eval, while, getattr, np.load, pd.io traversal, a function
definition, an unbound os") and section 16's 30-escape-attempt test plan.
Run directly: python3 tests/test_pandas_validator_negative.py
"""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.guards.pandas_validator import validate_pandas_code  # noqa: E402

CASES = [
    ("import os\nresult = os.listdir('.')", "P-03"),
    ("result = open('/etc/passwd').read()", "P-04"),
    ("df.to_csv('/tmp/x.csv')\nresult = 1", "P-06"),
    ("result = df.__class__", "P-05"),
    ("result = ''.format(df)", None),  # format on a str literal, not df -- still blocked by P-06
    ("result = '{0.__class__}'.format(df)", "P-05"),
    ("result = pd.read_csv('/etc/passwd')", "P-06"),
    ("result = df.query('a == 1')", "P-06"),
    ("result = df.eval('a + 1')", "P-06"),
    ("i = 0\nwhile i < 10:\n    i += 1\nresult = i", "P-03"),
    ("result = getattr(df, 'to_csv')", "P-04"),
    ("result = np.load('/etc/passwd')", "P-06"),
    ("result = pd.io.common.get_handle('/etc/passwd', 'r')", "P-07"),
    ("def f():\n    return 1\nresult = f()", "P-03"),
    ("result = os.environ['GROQ_API_KEY']", "P-04"),
    ("result = df.to_pickle('/tmp/x.pkl')", "P-06"),
    ("result = ().__class__.__bases__[0]", "P-05"),
    ("result = df[\"a\"].__getattribute__('to_csv')", "P-05"),
    ("import sys\nresult = sys.modules", "P-03"),
    ("result = exec('import os')", "P-04"),
    ("result = __import__('os')", "P-05"),
    ("class Foo:\n    pass\nresult = 1", "P-03"),
    ("try:\n    result = 1\nexcept Exception:\n    result = 2", "P-03"),
    ("with open('/tmp/x') as f:\n    result = 1", "P-03"),
    ("global x\nx = 1\nresult = x", "P-03"),
    ("result = (yield 1)", "P-03"),
    ("result := 5", "P-01"),  # walrus at statement level is also just a syntax error here
    ("result = df.to_json()", "P-06"),
    ("result = df.plot()", "P-06"),
    ("result = np.fromfile('/etc/passwd')", "P-06"),
]

POSITIVE = [
    "result = df['units_sold'].sum()",
    "x = df.groupby('category')['revenue'].sum()\nresult = x.to_dict()",
    "facts = {'n': len(df)}\nresult = df.head(5).to_dict('records')",
    "result = [i for i in range(10) if i % 2 == 0]",
    "f = lambda x: x * 2\nresult = [f(i) for i in range(5)]",
]


def main():
    failed = 0
    for code, expected_code in CASES:
        r = validate_pandas_code(code)
        if r.ok:
            print(f"FAIL (should have been rejected): {code!r}")
            failed += 1
            continue
        if expected_code is not None and r.code != expected_code:
            print(f"WRONG CODE for {code!r}: got {r.code} ({r.message}), expected {expected_code}")
            failed += 1
    for code in POSITIVE:
        r = validate_pandas_code(code)
        if not r.ok:
            print(f"FAIL (should have been accepted): {code!r} -> {r.code} {r.message}")
            failed += 1
    print(f"{len(CASES)} negative + {len(POSITIVE)} positive cases, {failed} unexpected results")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
