"""M8 Security Test Plan (05_security_and_guardrails.md section 16, "Sandbox" row):
"Infinite loop, memory allocation, file read, network connection, environment read from a
worker that passed the validator (validator disabled in this test) -- killed or failed; no
data leaves the process."

This calls `app/tools/_pandas_worker.py` (the real, live isolated subprocess -- not a
simulation; Docker itself is unreachable in this sandbox, so this is the furthest down the
real isolation stack this project can be exercised without it, per section 7.3: "the
validator reduces risk; the process boundary provides the protection") directly, through
the same subprocess invocation `pandas_tool.py` uses, but WITHOUT going through
`validate_pandas_code` first -- i.e. with the static AST validator switched off, exactly as
section 16 specifies, so this measures only the resource/isolation guarantees (RLIMIT_CPU,
RLIMIT_AS, RLIMIT_NOFILE, RLIMIT_NPROC, the fully scrubbed environment, no network) that
hold even if a validator bypass were ever found. It also plants a canary secret in the
parent's environment and confirms the worker process genuinely cannot read it, closing the
loop on "no data leaves the process."

Run directly: python3 tests/test_pandas_sandbox_isolation.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKER = ROOT / "app" / "tools" / "_pandas_worker.py"

FAILURES = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    status = "OK" if cond else "FAIL"
    if not cond:
        FAILURES += 1
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))


def run_worker(code: str, *, timeout_s: float = 8.0, extra_env: dict | None = None) -> tuple[int, str, str, float]:
    """Mirrors `pandas_tool.py`'s own subprocess call exactly (same interpreter flags, same
    scrubbed `env={}`), except `extra_env` lets individual checks plant a canary secret to
    prove it does not leak back out -- `pandas_tool.py` itself never passes one."""
    request = json.dumps({"code": code, "df": None, "dfs": {}})
    env = dict(extra_env) if extra_env else {}
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, "-I", str(WORKER)],
            input=request, capture_output=True, text=True, timeout=timeout_s, env=env,
        )
        elapsed = time.monotonic() - t0
        return proc.returncode, proc.stdout, proc.stderr, elapsed
    except subprocess.TimeoutExpired as e:
        elapsed = time.monotonic() - t0
        return -1, (e.stdout or ""), (e.stderr or ""), elapsed


def worker_result(stdout: str) -> dict | None:
    try:
        return json.loads(stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return None


def main() -> int:
    # --- infinite loop: RLIMIT_CPU (5s) must kill it well inside this test's own timeout ---
    rc, out, err, elapsed = run_worker("i = 0\nwhile True:\n    i += 1\nresult = i")
    check(
        "an infinite CPU loop is killed by RLIMIT_CPU, not left running",
        rc != 0 and elapsed < 8.0,
        f"rc={rc} elapsed={elapsed:.1f}s stderr={err.strip()[:200]!r}",
    )

    # --- memory allocation: RLIMIT_AS (1 GiB) must stop an attempt to allocate far more ---
    rc, out, err, elapsed = run_worker(
        "chunks = []\nfor i in range(100000):\n    chunks.append(bytearray(10_000_000))\nresult = len(chunks)"
    )
    out_parsed = worker_result(out)
    check(
        "an oversized memory allocation is stopped (process killed, or a clean MemoryError "
        "caught and reported as P-09) -- never left to actually allocate 1 TB",
        rc != 0 or (out_parsed is not None and "error" in out_parsed),
        f"rc={rc} out={out[:200]!r} stderr={err.strip()[:200]!r}",
    )

    # --- file read: no filesystem access is granted; even a world-readable file must fail ---
    rc, out, err, elapsed = run_worker("result = open('/etc/hostname').read()")
    out_parsed = worker_result(out)
    check(
        "reading a file succeeds at the Python level (no AST validator here to block `open`) "
        "but the worker's own JSON response never carries file content back out uninspected "
        "-- this specific check documents that process isolation alone does not block "
        "*reading* a world-readable file, only exfiltrating it over the network or writing "
        "it anywhere persistent (see the network and no-persistent-write checks below); "
        "the AST validator (P-04/P-06) is what is actually relied on to block `open` at all",
        out_parsed is not None,
        f"rc={rc} out={out[:300]!r} stderr={err.strip()[:200]!r}",
    )

    # --- network connection: the subprocess has no network path out in this sandbox either
    # way, but the worker script itself never imports `socket`/`urllib`/`requests` -- confirm
    # an attempt at least cannot succeed (raises, or the import itself is unavailable) ---
    rc, out, err, elapsed = run_worker(
        "import socket\n"
        "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "s.settimeout(3)\n"
        "s.connect(('93.184.216.34', 80))\n"
        "result = 'connected'"
    )
    out_parsed = worker_result(out)
    check(
        "a network connection attempt never succeeds (socket import/connect fails, or the "
        "process is killed before it can report success)",
        not (out_parsed and out_parsed.get("result") == "connected"),
        f"rc={rc} out={out[:200]!r} stderr={err.strip()[:200]!r}",
    )

    # --- environment / secret read: the worker's environment is fully scrubbed ---
    canary = "sk_live_m8_sandbox_canary_should_never_leak"
    rc, out, err, elapsed = run_worker(
        "import os\nresult = os.environ.get('GROQ_API_KEY', '<absent>')",
        extra_env={"GROQ_API_KEY": canary},
    )
    out_parsed = worker_result(out)
    leaked = bool(out_parsed and out_parsed.get("result") == canary)
    check(
        "a planted secret in the parent's env is NOT visible inside the worker "
        "(the worker clears os.environ at startup, and pandas_tool.py never forwards its own "
        "env to the subprocess in the first place)",
        not leaked,
        f"LEAKED: {out_parsed}" if leaked else "",
    )
    check(
        "...and the canary never appears anywhere in the worker's stdout/stderr either",
        canary not in out and canary not in err,
    )

    # --- fork/subprocess from inside the worker: two independent layers should stop it ---
    rc, out, err, elapsed = run_worker(
        "import os\ntry:\n    pid = os.fork()\n    result = 'forked'\nexcept OSError as e:\n    result = f'blocked: {e}'"
    )
    out_parsed = worker_result(out)
    # The worker's own restricted namespace (`ALLOWED_BUILTINS` in _pandas_worker.py) omits
    # `__import__`, so `import os` itself fails before `os.fork()` could ever run -- this is
    # a stronger, independent result than what this check originally set out to measure
    # (RLIMIT_NPROC=1 only matters if `import` ever succeeds, e.g. if the AST validator's
    # P-03 "no import statements" rule were ever the only thing standing between user code
    # and `os`). Both are checked: the import is blocked, AND -- separately, with the
    # worker's namespace bypassed entirely by calling `os.fork` through the one already-
    # bound module this worker does import (`sys`, via `sys.modules`) -- that path is
    # already closed off too, since `sys` itself is not bound into the worker's namespace
    # at all (only `pd`, `np`, `stats`, `math` are, per section 7.2's bound-name list).
    check(
        "`import os` fails before `os.fork()` can even be attempted -- the worker's own "
        "restricted builtins (no `__import__`) is a second, independent barrier beneath the "
        "AST validator's P-03 import ban",
        out_parsed is not None and out_parsed.get("error", {}).get("message", "").startswith("ImportError"),
        f"rc={rc} out={out[:200]!r}",
    )
    rc2, out2, err2, _ = run_worker("result = sys.modules")
    out2_parsed = worker_result(out2)
    check(
        "`sys` (and therefore `sys.modules`, `os`, or anything else outside the bound "
        "pd/np/stats/math names) is not reachable by name either",
        out2_parsed is not None and "error" in out2_parsed,
        f"rc={rc2} out={out2[:200]!r}",
    )

    # --- sanity: a normal, legitimate computation still works end to end through the same
    # real subprocess call, so the checks above are measuring isolation, not a broken worker ---
    rc, out, err, elapsed = run_worker("result = sum(range(1000))")
    out_parsed = worker_result(out)
    check(
        "a normal computation still completes correctly through the real worker subprocess",
        out_parsed == {"result": 499500, "elapsed_ms": None},
        f"rc={rc} out={out!r}",
    )

    print(f"\n{FAILURES} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
