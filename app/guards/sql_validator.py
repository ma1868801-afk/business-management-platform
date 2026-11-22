"""SQL guard: `postgres_tool`'s validator, enforcing V-01..V-15 of
`05_security_and_guardrails.md` section 6.1 on the parse tree produced by `sql_parser.py`
(never on the raw text -- rule V-13).

Checks run in the documented order; the first failure returns immediately with its code, a
message, and a short hint the generating model can act on when it regenerates (section 6.1:
"a hint that the model can use to regenerate, at most 2 times"). On success, `validate_sql`
returns the comment-stripped, single-statement SQL text that `postgres_tool` should actually
execute (rule: "comments are removed before parsing and before execution").

Deviation from the architecture document, recorded here rather than silently patched in:
`DA-SQL-09` (`rag_sources/data_analysis/03_sql_patterns_sales.md#9`) uses
`EXTRACT(YEAR FROM o.order_date)`, but the function allow-list in
`05_security_and_guardrails.md` section 6.2 lists `date_part` and does not list `extract`,
even though they are equivalent in PostgreSQL and the architecture document's own tested
pattern needs it. `extract` is added to `_ALLOWED_FUNCTIONS` below so that an approved,
already-delivered Phase 1 pattern is not rejected by this validator; this is noted the same
way Phase 2's spec deviations were (`09_phase2_completion_report.md`).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.guards import sql_parser as sp

# --------------------------------------------------------------------------- allow-lists (6.2)

ALLOWED_RELATIONS = frozenset({
    "branches", "product_categories", "suppliers", "products", "promotions", "calendar",
    "monthly_sales_targets", "customers", "sales_orders", "sales_order_items", "sales_returns",
    "inventory_levels", "inventory_snapshots", "purchase_orders", "purchase_order_items",
    "stock_adjustments", "v_sales_detail", "v_inventory_status", "v_weekly_product_demand",
})

_AGGREGATE_FUNCTIONS = frozenset({
    "sum", "count", "avg", "min", "max", "stddev", "stddev_samp", "variance", "var_samp",
    "corr", "percentile_cont", "percentile_disc", "string_agg", "array_agg", "bool_and", "bool_or",
})
_SCALAR_FUNCTIONS = frozenset({
    "round", "coalesce", "nullif", "greatest", "least", "abs", "ceil", "floor", "power", "sqrt",
    "ln", "log", "exp", "mod", "date_trunc", "extract", "date_part", "to_char", "make_date",
    "lower", "upper", "length", "substr", "substring", "concat", "replace", "trim", "split_part",
})
_WINDOW_FUNCTIONS = frozenset({"row_number", "rank", "dense_rank", "lag", "lead", "first_value", "last_value", "ntile"})
_SET_RETURNING_FUNCTIONS = frozenset({"generate_series"})
ALLOWED_FUNCTIONS = _AGGREGATE_FUNCTIONS | _SCALAR_FUNCTIONS | _WINDOW_FUNCTIONS | _SET_RETURNING_FUNCTIONS

_CLOCK_OR_RANDOM_FUNCTIONS = frozenset({"now", "clock_timestamp", "transaction_timestamp", "random"})
_CLOCK_BARE_WORDS = frozenset({"current_date", "current_time", "current_timestamp", "localtime", "localtimestamp"})

_ALLOWED_CAST_TYPES = frozenset({"numeric", "text", "date", "timestamp", "boolean"})

_BLOCKED_COLUMNS = frozenset({"email", "phone"})

# First-token classification: a statement whose first significant word is one of these can
# never be a SELECT/WITH query, so the grammar rejects it; these sets only pick a more useful
# V-code and hint than a generic syntax error (fail-closed holds either way -- parsing fails).
_V03_FIRST_WORDS = frozenset({
    "set", "reset", "explain", "copy", "call", "do", "grant", "revoke", "create", "alter",
    "drop", "truncate", "comment", "security", "vacuum", "analyze", "refresh", "lock", "listen",
    "notify", "prepare", "execute", "deallocate", "checkpoint", "discard", "cluster", "reindex",
    "begin", "commit", "rollback", "savepoint",
})


@dataclass
class ValidationResult:
    ok: bool
    sql: str = ""  # the cleaned, single-statement SQL to execute (only when ok)
    code: Optional[str] = None
    message: Optional[str] = None
    hint: Optional[str] = None

    def to_error(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "hint": self.hint}}


def _fail(code: str, message: str, hint: str) -> ValidationResult:
    return ValidationResult(ok=False, code=code, message=message, hint=hint)


# --------------------------------------------------------------------------- comment / statement splitting

def strip_comments(sql: str) -> str:
    """Remove -- line comments and /* */ block comments, respecting string literals."""
    out = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c == "'":
            j = i + 1
            while j < n:
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            out.append(sql[i:j])
            i = j
            continue
        if c == "-" and i + 1 < n and sql[i + 1] == "-":
            j = sql.find("\n", i)
            i = n if j == -1 else j
            continue
        if c == "/" and i + 1 < n and sql[i + 1] == "*":
            j = sql.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def split_single_statement(sql: str) -> tuple[str, str]:
    """Quote-aware split on the first top-level ';'. Returns (statement, trailing-after-it)."""
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c == "'":
            i += 1
            while i < n:
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if c == ";":
            return sql[:i], sql[i + 1:]
        i += 1
    return sql, ""


# --------------------------------------------------------------------------- AST walking

class _Analysis:
    def __init__(self):
        self.table_refs: list[str] = []          # base relation names actually checked against the allow-list
        self.function_calls: list[str] = []
        self.clock_bare_words: list[str] = []
        self.star_violations: list[str] = []      # 'bare *' or 'alias.*'
        self.column_refs: list[list[str]] = []     # every ColumnRef.parts seen anywhere
        self.cast_types: list[str] = []
        self.select_list_exprs: list[sp.Expr] = []  # of the outermost query, for V-09
        self.outermost_group_by: list[sp.Expr] = []
        self.has_for_update: bool = False
        self.schema_qualified_violation: bool = False


def _walk_expr(e: sp.Expr, a: _Analysis, known_ctes: set[str]) -> None:
    if e is None:
        return
    if isinstance(e, sp.ColumnRef):
        a.column_refs.append(e.parts)
        if len(e.parts) == 1 and e.parts[0].lower() in _CLOCK_BARE_WORDS:
            a.clock_bare_words.append(e.parts[0].lower())
        if len(e.parts) >= 3:
            a.schema_qualified_violation = True
    elif isinstance(e, sp.Star):
        a.star_violations.append(e.qualifier or "*")
    elif isinstance(e, sp.Literal):
        pass
    elif isinstance(e, sp.FuncCall):
        a.function_calls.append(e.name.lower())
        for arg in e.args:
            _walk_expr(arg, a, known_ctes)
        if e.filter_where is not None:
            _walk_expr(e.filter_where, a, known_ctes)
        if e.over is not None:
            for p in e.over.partition_by:
                _walk_expr(p, a, known_ctes)
            for o in e.over.order_by:
                _walk_expr(o.expr, a, known_ctes)
    elif isinstance(e, sp.Cast):
        a.cast_types.append(e.type_name.lower())
        _walk_expr(e.expr, a, known_ctes)
    elif isinstance(e, sp.CaseExpr):
        if e.operand is not None:
            _walk_expr(e.operand, a, known_ctes)
        for cond, res in e.whens:
            _walk_expr(cond, a, known_ctes)
            _walk_expr(res, a, known_ctes)
        if e.else_ is not None:
            _walk_expr(e.else_, a, known_ctes)
    elif isinstance(e, sp.ArrayLit):
        for el in e.elements:
            _walk_expr(el, a, known_ctes)
    elif isinstance(e, sp.UnaryOp):
        _walk_expr(e.expr, a, known_ctes)
    elif isinstance(e, sp.BinaryOp):
        _walk_expr(e.left, a, known_ctes)
        _walk_expr(e.right, a, known_ctes)
    elif isinstance(e, sp.Between):
        _walk_expr(e.expr, a, known_ctes)
        _walk_expr(e.low, a, known_ctes)
        _walk_expr(e.high, a, known_ctes)
    elif isinstance(e, sp.InList):
        _walk_expr(e.expr, a, known_ctes)
        for it in e.items:
            _walk_expr(it, a, known_ctes)
    elif isinstance(e, sp.InSubquery):
        _walk_expr(e.expr, a, known_ctes)
        _walk_statement(e.subquery, a, known_ctes)
    elif isinstance(e, sp.ExistsExpr):
        _walk_statement(e.subquery, a, known_ctes)
    elif isinstance(e, sp.IsNull):
        _walk_expr(e.expr, a, known_ctes)
    elif isinstance(e, sp.ScalarSubquery):
        _walk_statement(e.subquery, a, known_ctes)
    else:  # pragma: no cover - exhaustive by construction
        raise TypeError(f"unhandled expression node {type(e)!r}")


def _walk_from(node: Optional["sp.FromClauseNode"], a: _Analysis, known_ctes: set[str]) -> None:
    if node is None:
        return
    if isinstance(node, sp.Join):
        _walk_from(node.left, a, known_ctes)
        _walk_from(node.right, a, known_ctes)
        _walk_expr(node.on, a, known_ctes)
        return
    if isinstance(node, sp.TableRef):
        name = node.name.lower()
        if name not in known_ctes:
            a.table_refs.append(name)
        return
    if isinstance(node, sp.FuncTableRef):
        a.function_calls.append(node.call.name.lower())
        for arg in node.call.args:
            _walk_expr(arg, a, known_ctes)
        return
    if isinstance(node, sp.SubqueryRef):
        _walk_statement(node.subquery, a, known_ctes)
        return
    raise TypeError(f"unhandled FROM node {type(node)!r}")  # pragma: no cover


def _walk_select_core(core: sp.SelectCore, a: _Analysis, known_ctes: set[str], outermost: bool) -> None:
    if core.for_update:
        a.has_for_update = True
    for item in core.select_items:
        _walk_expr(item.expr, a, known_ctes)
        if outermost:
            a.select_list_exprs.append(item.expr)
    _walk_from(core.from_clause, a, known_ctes)
    _walk_expr(core.where, a, known_ctes)
    for g in core.group_by:
        _walk_expr(g, a, known_ctes)
        if outermost:
            a.outermost_group_by.append(g)
    _walk_expr(core.having, a, known_ctes)


def _walk_body(body: sp.SelectOrSetOp, a: _Analysis, known_ctes: set[str], outermost: bool) -> None:
    if isinstance(body, sp.SelectCore):
        _walk_select_core(body, a, known_ctes, outermost)
    elif isinstance(body, sp.SetOpSelect):
        _walk_body(body.left, a, known_ctes, outermost=False)
        _walk_select_core(body.right, a, known_ctes, outermost)
    else:  # pragma: no cover
        raise TypeError(f"unhandled statement body {type(body)!r}")


def _walk_statement(stmt: sp.Statement, a: _Analysis, known_ctes: set[str], outermost: bool = False) -> None:
    local_ctes = set(known_ctes)
    for cte in stmt.ctes:
        _walk_statement(cte.statement, a, local_ctes, outermost=False)
        local_ctes.add(cte.name.lower())
    _walk_body(stmt.body, a, local_ctes, outermost)
    for o in stmt.order_by:
        _walk_expr(o.expr, a, local_ctes)
    _walk_expr(stmt.limit, a, local_ctes)
    _walk_expr(stmt.offset, a, local_ctes)


def analyze(stmt: sp.Statement) -> _Analysis:
    a = _Analysis()
    _walk_statement(stmt, a, set(), outermost=True)
    return a


def _contains_bare_aggregate(e: sp.Expr) -> bool:
    """Whether a non-windowed aggregate call occurs anywhere in `e`, without descending into
    a subquery (an aggregate inside a correlated or scalar subquery does not collapse *this*
    query's rows)."""
    if e is None:
        return False
    if isinstance(e, sp.FuncCall):
        if e.name.lower() in _AGGREGATE_FUNCTIONS and e.over is None:
            return True
        return any(_contains_bare_aggregate(arg) for arg in e.args) or _contains_bare_aggregate(e.filter_where)
    if isinstance(e, sp.Cast):
        return _contains_bare_aggregate(e.expr)
    if isinstance(e, sp.CaseExpr):
        return (
            _contains_bare_aggregate(e.operand)
            or any(_contains_bare_aggregate(c) or _contains_bare_aggregate(r) for c, r in e.whens)
            or _contains_bare_aggregate(e.else_)
        )
    if isinstance(e, sp.ArrayLit):
        return any(_contains_bare_aggregate(el) for el in e.elements)
    if isinstance(e, sp.UnaryOp):
        return _contains_bare_aggregate(e.expr)
    if isinstance(e, sp.BinaryOp):
        return _contains_bare_aggregate(e.left) or _contains_bare_aggregate(e.right)
    if isinstance(e, sp.Between):
        return _contains_bare_aggregate(e.expr) or _contains_bare_aggregate(e.low) or _contains_bare_aggregate(e.high)
    if isinstance(e, sp.InList):
        return _contains_bare_aggregate(e.expr) or any(_contains_bare_aggregate(it) for it in e.items)
    if isinstance(e, sp.IsNull):
        return _contains_bare_aggregate(e.expr)
    return False  # ColumnRef, Star, Literal, subqueries (InSubquery/ExistsExpr/ScalarSubquery)


def _core_is_raw(exprs: list[sp.Expr], group_by: list[sp.Expr]) -> bool:
    """True when the outermost query returns individual rows rather than collapsed groups."""
    if group_by:
        return False
    return not any(_contains_bare_aggregate(e) for e in exprs)


def _is_aggregate_literal_value(lit: sp.Literal) -> Optional[int]:
    if lit.kind == "number":
        try:
            return int(lit.value)
        except ValueError:
            return None
    return None


def _has_full_name_output(a: _Analysis) -> bool:
    for parts in [list(e.parts) for e in a.select_list_exprs if isinstance(e, sp.ColumnRef)]:
        if parts[-1].lower() == "full_name":
            return True
    return False


def _has_business_predicate(expr: Optional[sp.Expr]) -> bool:
    found = False

    def visit(e: sp.Expr) -> None:
        nonlocal found
        if e is None or found:
            return
        if isinstance(e, sp.BinaryOp):
            if e.op == "=" and isinstance(e.left, sp.ColumnRef) and e.left.parts[-1].lower() == "customer_type":
                if isinstance(e.right, sp.Literal) and e.right.kind == "string" and e.right.value == "Business":
                    found = True
                    return
            if e.op == "like" and isinstance(e.left, sp.ColumnRef) and e.left.parts[-1].lower() == "customer_code":
                if isinstance(e.right, sp.Literal) and e.right.kind == "string" and e.right.value.upper().startswith("CUST-B"):
                    found = True
                    return
            visit(e.left)
            visit(e.right)
        elif isinstance(e, sp.UnaryOp):
            visit(e.expr)
        elif isinstance(e, sp.Between):
            visit(e.expr)
        elif isinstance(e, sp.InList):
            visit(e.expr)
        elif isinstance(e, sp.CaseExpr):
            for cond, res in e.whens:
                visit(cond)
                visit(res)
        # IN ('Business', ...) style membership on customer_type is also accepted.
        if isinstance(e, sp.InList) and isinstance(e.expr, sp.ColumnRef) and e.expr.parts[-1].lower() == "customer_type":
            for it in e.items:
                if isinstance(it, sp.Literal) and it.kind == "string" and it.value == "Business":
                    found = True

    visit(expr)
    return found


def _classify_parse_error(stmt_text: str, err: Exception) -> tuple[str, str]:
    msg = str(err)
    if "(V-05)" in msg:
        return "V-05", "Use unqualified names; `rag`, `pg_catalog` and `information_schema` are not accessible."
    stripped = stmt_text.strip()
    first_word = stripped.split(None, 1)[0].lower() if stripped else ""
    first_word = first_word.rstrip("(")
    if first_word in _V03_FIRST_WORDS:
        return "V-03", "Remove the construct."
    if first_word and first_word not in ("select", "with"):
        return "V-02", "Only read queries are allowed."
    return "V-13", "Fix the syntax."


def validate_sql(sql: str, max_rows: int, max_chars: int = 8000, max_relations: int = 12) -> ValidationResult:
    """Run V-01..V-15 in order. `max_rows` is the LIMIT ceiling for this call (up to 50,000
    when `postgres_tool` is feeding a Pandas extraction, per 02_architecture.md section 6.1
    and 05_security_and_guardrails.md section 14)."""
    cleaned = strip_comments(sql)
    stmt_text, trailing = split_single_statement(cleaned)
    if trailing.strip():
        return _fail("V-01", "more than one statement", "Send one statement without a semicolon in the middle.")
    stmt_text = stmt_text.strip()
    if not stmt_text:
        return _fail("V-13", "empty statement", "Fix the syntax.")

    # V-12 (length clause)
    if len(stmt_text) > max_chars:
        return _fail("V-12", f"statement is {len(stmt_text)} characters (limit {max_chars})", "Simplify the query or split it.")

    # V-13 (parses)
    try:
        stmt = sp.parse(stmt_text)
    except (sp.ParseError, sp.LexError) as e:
        code, hint = _classify_parse_error(stmt_text, e)
        return _fail(code, str(e), hint)

    # V-02 (SELECT or WITH ... SELECT) -- guaranteed by the grammar once parse() succeeds,
    # verified defensively.
    if not isinstance(stmt.body, (sp.SelectCore, sp.SetOpSelect)):
        return _fail("V-02", "statement body is not a SELECT", "Only read queries are allowed.")

    a = analyze(stmt)

    # V-03 (no data-changing construct, no FOR UPDATE/SHARE, no WITH RECURSIVE)
    if stmt.recursive:
        return _fail("V-03", "WITH RECURSIVE is not allowed", "Remove the construct.")
    if a.has_for_update:
        return _fail("V-03", "FOR UPDATE/SHARE is not allowed", "Remove the construct.")

    # V-12 (relation-count clause)
    distinct_relations = sorted(set(a.table_refs))
    if len(distinct_relations) > max_relations:
        return _fail(
            "V-12", f"references {len(distinct_relations)} relations (limit {max_relations})",
            "Simplify the query or split it.",
        )

    # V-04 (relation allow-list) / V-05 (no schema-qualified name)
    if a.schema_qualified_violation:
        return _fail("V-05", "schema-qualified column reference", "Use unqualified names; `rag`, `pg_catalog` and `information_schema` are not accessible.")
    for rel in distinct_relations:
        if rel not in ALLOWED_RELATIONS:
            return _fail("V-04", f"relation '{rel}' is not on the allow-list", "Use only the listed tables and views.")

    # V-06 (no SELECT * / table.*; COUNT(*) is allowed, represented separately)
    if a.star_violations:
        return _fail("V-06", f"unqualified star in select list: {a.star_violations[0]}", "List the columns.")

    # V-07 (no customers.email / customers.phone anywhere)
    for parts in a.column_refs:
        if parts[-1].lower() in _BLOCKED_COLUMNS:
            return _fail("V-07", f"blocked column '{parts[-1]}'", "Contact details are restricted.")

    # V-15 (full_name output requires a Business-customer predicate)
    where_expr = stmt.body.where if isinstance(stmt.body, sp.SelectCore) else None
    if _has_full_name_output(a) and not _has_business_predicate(where_expr):
        return _fail(
            "V-15", "full_name is selected without a Business-customer predicate",
            "Individuals are identified by customer_code.",
        )

    # V-08 (function allow-list; cast types) / V-11 (no system clock or random function)
    for fn in a.function_calls:
        if fn in _CLOCK_OR_RANDOM_FUNCTIONS:
            return _fail("V-11", f"'{fn}()' reads the system clock or is non-deterministic", "Use the reference date as a literal: `DATE '2026-10-31'`.")
        if fn not in ALLOWED_FUNCTIONS:
            return _fail("V-08", f"function '{fn}' is not on the allow-list", "Use an allowed function.")
    if a.clock_bare_words:
        return _fail("V-11", f"'{a.clock_bare_words[0]}' reads the system clock", "Use the reference date as a literal: `DATE '2026-10-31'`.")
    for t in a.cast_types:
        base = t.split("[")[0].split("(")[0].strip()
        if base not in _ALLOWED_CAST_TYPES:
            return _fail("V-08", f"cast to '{t}' is not allowed", "Use an allowed function.")

    # V-09 / V-10 (LIMIT required on a raw-row outermost query, and bounded)
    is_raw = _core_is_raw(a.select_list_exprs, a.outermost_group_by)
    if is_raw:
        if stmt.limit is None:
            return _fail("V-09", "outermost query returns raw rows without LIMIT", "Add `LIMIT`.")
        if not isinstance(stmt.limit, sp.Literal):
            return _fail("V-10", "LIMIT must be a literal number", "Lower the limit or aggregate.")
        n = _is_aggregate_literal_value(stmt.limit)
        if n is None or n < 0:
            return _fail("V-10", "LIMIT must be a non-negative integer literal", "Lower the limit or aggregate.")
        if n > max_rows:
            return _fail("V-10", f"LIMIT {n} exceeds the cap of {max_rows}", "Lower the limit or aggregate.")

    return ValidationResult(ok=True, sql=stmt_text)
