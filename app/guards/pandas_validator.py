"""Pandas guard: `pandas_tool`'s static validator, enforcing P-01..P-08 of
`05_security_and_guardrails.md` section 7.1 on the code's AST (Python's own `ast` module --
no external dependency needed here). Runtime failures (P-09 timeout, P-10 runtime error,
P-11 unserializable result) are raised by the sandbox runner in `pandas_tool.py`, not here.

This is the first of two layers (section 7.3): "the validator reduces risk; the process
boundary provides the protection." A gap in this validator is expected to be caught by the
isolated-subprocess runner (scrubbed environment, resource limits, no network/files), never
relied on alone.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Optional

MAX_CHARS = 6000
MAX_LINES = 120

BOUND_NAMES = frozenset({"df", "dfs", "pd", "np", "stats", "math"})

ALLOWED_BUILTINS = frozenset({
    "abs", "all", "any", "bool", "dict", "enumerate", "float", "int", "len", "list", "max",
    "min", "range", "reversed", "round", "set", "sorted", "str", "sum", "tuple", "zip",
})

_BLOCKED_METHOD_NAMES = frozenset({
    "to_csv", "to_excel", "to_pickle", "to_sql", "to_parquet", "to_feather", "to_hdf",
    "to_stata", "to_clipboard", "to_json", "to_html", "to_latex", "to_markdown", "to_xml",
    "to_orc", "eval", "query", "format", "format_map", "style", "plot", "hist", "boxplot",
    "savefig", "tofile", "fromfile", "memmap", "system", "popen",
})
_BLOCKED_NAME_PREFIXES = ("read_", "load", "save")

ALLOWED_PD_ATTRS = frozenset({
    "DataFrame", "Series", "Timestamp", "Timedelta", "DateOffset", "to_datetime", "to_numeric",
    "to_timedelta", "concat", "merge", "cut", "qcut", "crosstab", "pivot_table", "date_range",
    "period_range", "Grouper", "isna", "notna", "get_dummies", "NA", "NaT", "Categorical",
    "Index", "MultiIndex", "unique", "factorize",
})
ALLOWED_NP_ATTRS = frozenset({
    "array", "arange", "linspace", "where", "select", "nan", "inf", "pi", "isnan", "isfinite",
    "isin", "nan_to_num", "abs", "sqrt", "log", "log1p", "exp", "expm1", "power", "round",
    "floor", "ceil", "clip", "maximum", "minimum", "sum", "mean", "median", "std", "var", "min",
    "max", "argmax", "argmin", "argsort", "sort", "unique", "cumsum", "cumprod", "prod", "diff",
    "percentile", "quantile", "corrcoef", "cov", "polyfit", "polyval", "flatnonzero", "nonzero",
    "zeros", "ones", "full", "float64", "int64", "concatenate", "average", "sign", "tile",
    "repeat", "searchsorted", "bincount", "histogram", "digitize", "any", "all",
})
ALLOWED_STATS_ATTRS = frozenset({
    "ttest_ind", "ttest_rel", "ttest_1samp", "mannwhitneyu", "wilcoxon", "f_oneway", "kruskal",
    "chi2_contingency", "chisquare", "fisher_exact", "spearmanr", "pearsonr", "kendalltau",
    "shapiro", "levene", "norm", "t", "chi2", "f", "binom", "binomtest", "poisson", "linregress",
    "zscore", "sem", "iqr", "skew", "kurtosis",
})
_MODULE_ATTR_ALLOWLIST = {"pd": ALLOWED_PD_ATTRS, "np": ALLOWED_NP_ATTRS, "stats": ALLOWED_STATS_ATTRS}
# math: "any public name" is allowed (the module has no file or network access) -- enforced
# simply as "does not start with underscore", same as every other attribute access (P-05).

_ALLOWED_STMT_NODES = (
    ast.Module, ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Expr, ast.If, ast.For, ast.Pass,
    ast.Break, ast.Continue,
)
_ALLOWED_EXPR_NODES = (
    ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare, ast.IfExp, ast.Call, ast.keyword,
    ast.Attribute, ast.Subscript, ast.Slice, ast.Starred, ast.Name, ast.Constant, ast.JoinedStr,
    ast.FormattedValue, ast.List, ast.Tuple, ast.Dict, ast.Set, ast.ListComp, ast.SetComp,
    ast.DictComp, ast.GeneratorExp, ast.Lambda, ast.comprehension, ast.arguments, ast.arg,
    ast.Load, ast.Store, ast.Del,
)
_ALLOWED_OP_NODES = (
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.FloorDiv, ast.MatMult, ast.USub,
    ast.UAdd, ast.Not, ast.Invert, ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt, ast.Gt, ast.LtE,
    ast.GtE, ast.Is, ast.IsNot, ast.In, ast.NotIn,
)
_ALLOWED_NODES = _ALLOWED_STMT_NODES + _ALLOWED_EXPR_NODES + _ALLOWED_OP_NODES


@dataclass
class PandasValidationResult:
    ok: bool
    code: Optional[str] = None
    message: Optional[str] = None
    hint: Optional[str] = None


def _fail(code: str, message: str, hint: str) -> PandasValidationResult:
    return PandasValidationResult(ok=False, code=code, message=message, hint=hint)


def _attr_chain(node: ast.AST) -> Optional[list[str]]:
    """For `a.b.c`, returns ['a', 'b', 'c'] if the base is a plain Name, else None."""
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        parts.reverse()
        return parts
    return None


def validate_pandas_code(code: str) -> PandasValidationResult:
    if len(code) > MAX_CHARS or code.count("\n") + 1 > MAX_LINES:
        return _fail("P-02", f"{len(code)} characters / {code.count(chr(10)) + 1} lines (limits {MAX_CHARS}/{MAX_LINES})", "Shorten the code.")

    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        return _fail("P-01", str(e), "Fix the syntax.")

    # P-03: only allowed syntax nodes anywhere in the tree.
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return _fail("P-03", f"disallowed construct: {type(node).__name__}", "Remove the construct; only simple expressions, assignments, if/for and comprehensions are allowed.")

    # P-05: no name/attribute starts with underscore; no string constant contains '__'.
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            return _fail("P-05", f"name '{node.id}' starts with an underscore", "Remove the underscore-prefixed name.")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            return _fail("P-05", f"attribute '.{node.attr}' starts with an underscore", "Remove the underscore-prefixed attribute.")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "__" in node.value:
            return _fail("P-05", "a string constant contains a double underscore", "Remove the double underscore from the string.")

    # P-06: no blocklisted method/function name anywhere (as a call target or bare attribute).
    for node in ast.walk(tree):
        name = None
        if isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.Name):
            name = node.id
        if name is None:
            continue
        low = name.lower()
        if low in _BLOCKED_METHOD_NAMES or low.startswith(_BLOCKED_NAME_PREFIXES):
            return _fail("P-06", f"blocked name '{name}'", "Use a different approach; file, network and evaluator operations are not allowed.")

    # P-07: attribute access on pd / np / stats must be on their allow-list (math: public names only).
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            chain = _attr_chain(node)
            if chain and len(chain) >= 2 and chain[0] in _MODULE_ATTR_ALLOWLIST:
                allowed = _MODULE_ATTR_ALLOWLIST[chain[0]]
                if chain[1] not in allowed:
                    return _fail("P-07", f"'{chain[0]}.{chain[1]}' is not on the allow-list", "Use an allowed function of this module.")

    # P-04: every loaded Name must be bound (df/dfs/pd/np/stats/math), assigned earlier, a
    # comprehension/lambda variable, or an allowed built-in.
    err = _check_bound_names(tree)
    if err is not None:
        return err

    # P-08: the code assigns `result` at the top level (anywhere in the module body --
    # there are no function scopes in this grammar subset to distinguish "top level" from
    # nested if/for blocks).
    if not _assigns_result(tree):
        return _fail("P-08", "the code never assigns a top-level name called 'result'", "Assign the final answer to a variable named `result`.")

    return PandasValidationResult(ok=True)


def _assigns_result(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name) and t.id == "result":
                    return True
    return False


def _check_bound_names(tree: ast.Module) -> Optional[PandasValidationResult]:
    """A simple, order-independent reaching-names check: because there is no function scope
    (P-03 forbids `def`), every name assigned anywhere in the module, plus every comprehension
    and lambda parameter, plus the fixed bound names and built-ins, is accepted. This is
    intentionally permissive about *order* (a name used before its only assignment is not
    flagged) because soundness here is a defense-in-depth nicety, not the security boundary --
    the boundary is process isolation (section 7.2); P-04's job is to catch exfiltration via
    unbound names like `__builtins__` or an unexpected global, not to be a full interpreter.
    """
    assigned: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                _collect_target_names(t, assigned)
        elif isinstance(node, ast.For):
            _collect_target_names(node.target, assigned)
        elif isinstance(node, ast.comprehension):
            _collect_target_names(node.target, assigned)
        elif isinstance(node, (ast.Lambda,)):
            for a in node.args.args:
                assigned.add(a.arg)

    allowed = assigned | BOUND_NAMES | ALLOWED_BUILTINS
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in allowed:
                return _fail("P-04", f"name '{node.id}' is not bound, assigned, or an allowed built-in", "Use only df, dfs, pd, np, stats, math, names you assigned, or an allowed built-in.")
    return None


def _collect_target_names(target: ast.AST, out: set[str]) -> None:
    if isinstance(target, ast.Name):
        out.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for el in target.elts:
            _collect_target_names(el, out)
    elif isinstance(target, ast.Starred):
        _collect_target_names(target.value, out)
    # ast.Attribute / ast.Subscript targets (e.g. df['x'] = ...) bind no new bare name.
