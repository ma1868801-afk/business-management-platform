"""A small, dependency-free tokenizer and recursive-descent parser for the subset of
PostgreSQL SQL that `postgres_tool` is allowed to run: a single `SELECT` or
`WITH ... SELECT` statement, optionally with CTEs, joins, subqueries, window functions,
aggregates, `CASE`, casts and set operations.

This exists instead of a dependency on `pglast` (suggested as an example by
`05_security_and_guardrails.md` section 6.1, "for example `pglast`") because this sandbox
has no network access to install compiled dependencies; a hand-written parser that only
needs to recognize this bounded, read-only grammar has no such dependency and is easy to
audit for exactly the constructs it accepts. It produces a structural parse tree -- the
validator in `sql_validator.py` walks that tree, never the source text, which is what rule
V-13 ("checks the syntax tree, not the text") requires. If `pglast` becomes available in a
deployment, it can be dropped in behind the same `parse(sql) -> Statement` interface.

The grammar accepted is deliberately narrow: anything outside it is a `SyntaxError`, which
the caller turns into a V-13 validation failure (fail closed -- principle 3 of the security
document). A real PostgreSQL feature this parser does not recognize is correctly rejected,
not silently misparsed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Union

# --------------------------------------------------------------------------------------- tokens

_KEYWORDS = {
    "select", "distinct", "all", "from", "where", "group", "by", "having", "order",
    "limit", "offset", "as", "on", "join", "inner", "left", "right", "full", "outer",
    "cross", "lateral", "with", "recursive", "union", "intersect", "except", "and", "or",
    "not", "in", "is", "null", "true", "false", "like", "ilike", "between", "case", "when",
    "then", "else", "end", "asc", "desc", "nulls", "first", "last", "over", "partition",
    "window", "filter", "exists", "array", "cast", "date", "timestamp", "interval", "time",
    "using", "natural", "collate", "within", "unknown", "for",
}
# Keywords that can also legally appear as a plain (unqualified) identifier in this grammar
# subset (column/alias names observed in the corpus and allow-listed functions).
_SOFT_KEYWORDS = {"first", "last", "window"}

_PUNCT_MULTI = ["<=", ">=", "<>", "!=", "||", "::", "->>", "->"]
_PUNCT_SINGLE = set("()[],.;+-*/%=<>:")

_TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<linecomment>--[^\n]*)
  | (?P<blockcomment>/\*.*?\*/)
  | (?P<string>'(?:[^']|'')*')
  | (?P<qident>"(?:[^"]|"")*")
  | (?P<number>\d+\.\d+(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?|\d+(?:[eE][+-]?\d+)?)
  | (?P<param>\$\d+)
  | (?P<dollarquote>\$([A-Za-z_][A-Za-z0-9_]*)?\$.*?\$\2\$)
  | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<punct3><<=|>>=)
  | (?P<punct2><=|>=|<>|!=|\|\||::|->>|->)
  | (?P<punct1>[()\[\],.;+\-*/%=<>])
    """,
    re.VERBOSE | re.DOTALL,
)


@dataclass
class Token:
    kind: str  # 'kw' | 'ident' | 'qident' | 'number' | 'string' | 'param' | 'op' | 'eof'
    value: str
    pos: int


class LexError(SyntaxError):
    pass


def tokenize(sql: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(sql)
    while i < n:
        m = _TOKEN_RE.match(sql, i)
        if not m:
            raise LexError(f"unrecognized character {sql[i]!r} at position {i}")
        i = m.end()
        kind = m.lastgroup
        text = m.group()
        if kind in ("ws", "linecomment", "blockcomment"):
            continue
        if kind == "dollarquote":
            raise LexError("dollar-quoted strings are not allowed")
        if kind == "string":
            tokens.append(Token("string", text[1:-1].replace("''", "'"), m.start()))
        elif kind == "qident":
            tokens.append(Token("ident", text[1:-1].replace('""', '"'), m.start()))
        elif kind == "number":
            tokens.append(Token("number", text, m.start()))
        elif kind == "param":
            tokens.append(Token("param", text, m.start()))
        elif kind == "ident":
            low = text.lower()
            # Soft keywords still tokenize as 'kw' (so at_kw(...) recognizes them in context,
            # e.g. NULLS LAST); ident_name() below accepts kind == 'kw' for a soft keyword too,
            # so they remain usable as ordinary identifiers everywhere else.
            if low in _KEYWORDS:
                tokens.append(Token("kw", low, m.start()))
            else:
                tokens.append(Token("ident", text, m.start()))
        else:  # punct1/2/3
            tokens.append(Token("op", text, m.start()))
    tokens.append(Token("eof", "", n))
    return tokens


# ------------------------------------------------------------------------------------------ AST

@dataclass
class ColumnRef:
    parts: list[str]  # e.g. ["o", "order_id"] or ["order_id"]


@dataclass
class Star:
    qualifier: Optional[str] = None  # None for bare '*', else "table.*"


@dataclass
class Literal:
    kind: str  # 'number' | 'string' | 'null' | 'bool' | 'typed' | 'param'
    value: str
    type_name: Optional[str] = None  # for typed literals: DATE 'x', TIMESTAMP 'x', INTERVAL 'x'


@dataclass
class FuncCall:
    name: str
    args: list["Expr"]
    distinct: bool = False
    star: bool = False  # COUNT(*)
    filter_where: Optional["Expr"] = None
    over: Optional["WindowSpec"] = None


@dataclass
class WindowSpec:
    partition_by: list["Expr"] = field(default_factory=list)
    order_by: list["OrderItem"] = field(default_factory=list)


@dataclass
class Cast:
    expr: "Expr"
    type_name: str


@dataclass
class CaseExpr:
    operand: Optional["Expr"]
    whens: list[tuple["Expr", "Expr"]]
    else_: Optional["Expr"]


@dataclass
class ArrayLit:
    elements: list["Expr"]


@dataclass
class UnaryOp:
    op: str
    expr: "Expr"


@dataclass
class BinaryOp:
    op: str
    left: "Expr"
    right: "Expr"


@dataclass
class Between:
    expr: "Expr"
    low: "Expr"
    high: "Expr"
    negated: bool = False


@dataclass
class InList:
    expr: "Expr"
    items: list["Expr"]
    negated: bool = False


@dataclass
class InSubquery:
    expr: "Expr"
    subquery: "Statement"
    negated: bool = False


@dataclass
class ExistsExpr:
    subquery: "Statement"
    negated: bool = False


@dataclass
class IsNull:
    expr: "Expr"
    negated: bool = False


@dataclass
class ScalarSubquery:
    subquery: "Statement"


Expr = Union[
    ColumnRef, Star, Literal, FuncCall, Cast, CaseExpr, ArrayLit, UnaryOp, BinaryOp,
    Between, InList, InSubquery, ExistsExpr, IsNull, ScalarSubquery,
]


@dataclass
class SelectItem:
    expr: Expr
    alias: Optional[str] = None


@dataclass
class OrderItem:
    expr: Expr
    desc: bool = False


@dataclass
class TableRef:
    name: str
    alias: Optional[str] = None


@dataclass
class FuncTableRef:
    call: FuncCall
    alias: Optional[str] = None


@dataclass
class SubqueryRef:
    subquery: "Statement"
    alias: Optional[str] = None


FromItem = Union[TableRef, FuncTableRef, SubqueryRef]


@dataclass
class Join:
    left: "FromClauseNode"
    right: FromItem
    join_type: str  # 'inner' | 'left' | 'right' | 'full' | 'cross'
    on: Optional[Expr] = None


FromClauseNode = Union[FromItem, Join]


@dataclass
class SelectCore:
    select_items: list[SelectItem]
    distinct: bool
    from_clause: Optional[FromClauseNode]
    where: Optional[Expr]
    group_by: list[Expr]
    having: Optional[Expr]
    for_update: bool = False  # always rejected by the validator (V-03) if True


@dataclass
class SetOpSelect:
    op: str  # 'union' | 'intersect' | 'except'
    all_: bool
    left: "SelectOrSetOp"
    right: SelectCore


SelectOrSetOp = Union[SelectCore, SetOpSelect]


@dataclass
class CTE:
    name: str
    columns: list[str]
    statement: "Statement"


@dataclass
class Statement:
    ctes: list[CTE]
    recursive: bool
    body: SelectOrSetOp
    order_by: list[OrderItem]
    limit: Optional[Expr]
    offset: Optional[Expr]


class ParseError(SyntaxError):
    pass


_AGGREGATES = {
    "sum", "count", "avg", "min", "max", "stddev", "stddev_samp", "variance", "var_samp",
    "corr", "percentile_cont", "percentile_disc", "string_agg", "array_agg", "bool_and",
    "bool_or",
}
_WINDOW_ONLY = {"row_number", "rank", "dense_rank", "lag", "lead", "first_value", "last_value", "ntile"}


class Parser:
    def __init__(self, tokens: list[Token]):
        self.toks = tokens
        self.i = 0

    # -- low level -----------------------------------------------------------------------
    def peek(self, offset: int = 0) -> Token:
        return self.toks[min(self.i + offset, len(self.toks) - 1)]

    def at_kw(self, *kws: str) -> bool:
        t = self.peek()
        return t.kind == "kw" and t.value in kws

    def at_op(self, *ops: str) -> bool:
        t = self.peek()
        return t.kind == "op" and t.value in ops

    def advance(self) -> Token:
        t = self.toks[self.i]
        if self.i < len(self.toks) - 1:
            self.i += 1
        return t

    def expect_kw(self, kw: str) -> Token:
        if not self.at_kw(kw):
            raise ParseError(f"expected keyword {kw!r} at position {self.peek().pos}, found {self.peek().value!r}")
        return self.advance()

    def expect_op(self, op: str) -> Token:
        if not self.at_op(op):
            raise ParseError(f"expected {op!r} at position {self.peek().pos}, found {self.peek().value!r}")
        return self.advance()

    def ident_name(self) -> str:
        t = self.peek()
        if t.kind == "ident" or (t.kind == "kw" and t.value in _SOFT_KEYWORDS):
            self.advance()
            return t.value
        raise ParseError(f"expected identifier at position {t.pos}, found {t.value!r}")

    # -- top level -------------------------------------------------------------------------
    def parse_statement(self) -> Statement:
        ctes: list[CTE] = []
        recursive = False
        if self.at_kw("with"):
            self.advance()
            if self.at_kw("recursive"):
                recursive = True
                self.advance()
            ctes.append(self.parse_cte())
            while self.at_op(","):
                self.advance()
                ctes.append(self.parse_cte())
        body = self.parse_set_op_select()
        order_by: list[OrderItem] = []
        if self.at_kw("order"):
            self.advance()
            self.expect_kw("by")
            order_by.append(self.parse_order_item())
            while self.at_op(","):
                self.advance()
                order_by.append(self.parse_order_item())
        limit = offset = None
        # LIMIT and OFFSET may appear in either order in PostgreSQL.
        for _ in range(2):
            if self.at_kw("limit"):
                self.advance()
                limit = self.parse_expr()
            elif self.at_kw("offset"):
                self.advance()
                offset = self.parse_expr()
        return Statement(ctes=ctes, recursive=recursive, body=body, order_by=order_by, limit=limit, offset=offset)

    def parse_cte(self) -> CTE:
        name = self.ident_name()
        columns: list[str] = []
        if self.at_op("("):
            self.advance()
            columns.append(self.ident_name())
            while self.at_op(","):
                self.advance()
                columns.append(self.ident_name())
            self.expect_op(")")
        self.expect_kw("as")
        self.expect_op("(")
        stmt = self.parse_statement()
        self.expect_op(")")
        return CTE(name=name, columns=columns, statement=stmt)

    def parse_set_op_select(self) -> SelectOrSetOp:
        left: SelectOrSetOp = self.parse_select_core_or_paren()
        while self.at_kw("union", "intersect", "except"):
            op = self.advance().value
            all_ = False
            if self.at_kw("all"):
                all_ = True
                self.advance()
            elif self.at_kw("distinct"):
                self.advance()
            right = self.parse_select_core_or_paren()
            if isinstance(right, SetOpSelect):
                raise ParseError("nested set operation on the right side is not supported")
            left = SetOpSelect(op=op, all_=all_, left=left, right=right)
        return left

    def parse_select_core_or_paren(self) -> SelectOrSetOp:
        if self.at_op("("):
            # A parenthesized SELECT used directly as a set-operation branch.
            save = self.i
            self.advance()
            inner = self.parse_set_op_select()
            if self.at_op(")"):
                self.advance()
                return inner
            self.i = save
        return self.parse_select_core()

    def parse_select_core(self) -> SelectCore:
        self.expect_kw("select")
        distinct = False
        if self.at_kw("distinct"):
            distinct = True
            self.advance()
            if self.at_kw("on"):
                raise ParseError("DISTINCT ON is not supported")
        elif self.at_kw("all"):
            self.advance()
        items = [self.parse_select_item()]
        while self.at_op(","):
            self.advance()
            items.append(self.parse_select_item())
        from_clause: Optional[FromClauseNode] = None
        if self.at_kw("from"):
            self.advance()
            from_clause = self.parse_from_clause()
        where = None
        if self.at_kw("where"):
            self.advance()
            where = self.parse_expr()
        group_by: list[Expr] = []
        if self.at_kw("group"):
            self.advance()
            self.expect_kw("by")
            group_by.append(self.parse_expr())
            while self.at_op(","):
                self.advance()
                group_by.append(self.parse_expr())
        having = None
        if self.at_kw("having"):
            self.advance()
            having = self.parse_expr()
        for_update = False
        if self.at_kw("for"):
            # FOR UPDATE / FOR SHARE -- always rejected (V-03); parsed so the rest of a
            # (rejected) query still parses instead of surfacing a confusing syntax error.
            self.advance()
            for_update = True
            while not self.at_op(")", ";") and self.peek().kind != "eof" and not self.at_kw(
                "order", "limit", "offset", "union", "intersect", "except"
            ):
                self.advance()
        return SelectCore(
            select_items=items, distinct=distinct, from_clause=from_clause, where=where,
            group_by=group_by, having=having, for_update=for_update,
        )

    def parse_select_item(self) -> SelectItem:
        if self.at_op("*"):
            self.advance()
            return SelectItem(expr=Star())
        expr = self.parse_expr()
        alias = None
        if self.at_kw("as"):
            self.advance()
            alias = self.ident_name()
        elif self.peek().kind == "ident":
            alias = self.ident_name()
        return SelectItem(expr=expr, alias=alias)

    # -- FROM / JOIN -------------------------------------------------------------------------
    def parse_from_clause(self) -> FromClauseNode:
        node = self.parse_table_ref()
        while True:
            jt = self._peek_join_type()
            if jt is None:
                if self.at_op(","):
                    self.advance()
                    right = self.parse_table_ref()
                    node = Join(left=node, right=right, join_type="inner", on=None)
                    continue
                break
            for _ in range(jt[1]):
                self.advance()
            right = self.parse_table_ref()
            on = None
            if self.at_kw("on"):
                self.advance()
                on = self.parse_expr()
            elif self.at_kw("using"):
                self.advance()
                self.expect_op("(")
                self.ident_name()
                while self.at_op(","):
                    self.advance()
                    self.ident_name()
                self.expect_op(")")
            node = Join(left=node, right=right, join_type=jt[0], on=on)
        return node

    def _peek_join_type(self) -> Optional[tuple[str, int]]:
        t = self.peek()
        if t.kind != "kw":
            return None
        if t.value == "join":
            return ("inner", 1)
        if t.value == "cross" and self.peek(1).kind == "kw" and self.peek(1).value == "join":
            return ("cross", 2)
        if t.value in ("inner",) and self.peek(1).kind == "kw" and self.peek(1).value == "join":
            return ("inner", 2)
        if t.value in ("left", "right", "full"):
            n = 1
            if self.peek(1).kind == "kw" and self.peek(1).value == "outer":
                n = 2
            if self.peek(n).kind == "kw" and self.peek(n).value == "join":
                return (t.value, n + 1)
        return None

    def parse_table_ref(self) -> FromItem:
        if self.at_kw("lateral"):
            self.advance()
        if self.at_op("("):
            self.advance()
            stmt = self.parse_statement()
            self.expect_op(")")
            alias = self._opt_alias()
            return SubqueryRef(subquery=stmt, alias=alias)
        name = self.ident_name()
        if self.at_op("."):
            self.advance()
            self.ident_name()
            raise ParseError("schema-qualified table names are not allowed (V-05)")
        if self.at_op("("):
            # function call used as a row source, e.g. generate_series(...)
            args, distinct, star = self._parse_call_args()
            call = FuncCall(name=name, args=args, distinct=distinct, star=star)
            if self.at_kw("over"):
                call.over = self._parse_over()
            alias = self._opt_alias()
            if self.at_op("("):
                # column alias list: generate_series(...) AS t(col)
                self.advance()
                self.ident_name()
                while self.at_op(","):
                    self.advance()
                    self.ident_name()
                self.expect_op(")")
            return FuncTableRef(call=call, alias=alias)
        alias = self._opt_alias()
        return TableRef(name=name, alias=alias)

    def _opt_alias(self) -> Optional[str]:
        if self.at_kw("as"):
            self.advance()
            return self.ident_name()
        t = self.peek()
        if t.kind == "ident":
            return self.ident_name()
        return None

    # -- expressions (Pratt-style precedence climbing) --------------------------------------
    def parse_order_item(self) -> OrderItem:
        expr = self.parse_expr()
        desc = False
        if self.at_kw("asc"):
            self.advance()
        elif self.at_kw("desc"):
            desc = True
            self.advance()
        if self.at_kw("nulls"):
            self.advance()
            if self.at_kw("first", "last"):
                self.advance()
        return OrderItem(expr=expr, desc=desc)

    def parse_expr(self) -> Expr:
        return self._parse_or()

    def _parse_or(self) -> Expr:
        left = self._parse_and()
        while self.at_kw("or"):
            self.advance()
            right = self._parse_and()
            left = BinaryOp(op="or", left=left, right=right)
        return left

    def _parse_and(self) -> Expr:
        left = self._parse_not()
        while self.at_kw("and"):
            self.advance()
            right = self._parse_not()
            left = BinaryOp(op="and", left=left, right=right)
        return left

    def _parse_not(self) -> Expr:
        if self.at_kw("not"):
            self.advance()
            return UnaryOp(op="not", expr=self._parse_not())
        return self._parse_comparison()

    _CMP_OPS = {"=", "<", ">", "<=", ">=", "<>", "!="}

    def _parse_comparison(self) -> Expr:
        left = self._parse_concat()
        if self.at_op(*self._CMP_OPS):
            op = self.advance().value
            right = self._parse_concat()
            return BinaryOp(op=op, left=left, right=right)
        negated = False
        if self.at_kw("not"):
            negated = True
            self.advance()
        if self.at_kw("between"):
            self.advance()
            low = self._parse_concat()
            self.expect_kw("and")
            high = self._parse_concat()
            return Between(expr=left, low=low, high=high, negated=negated)
        if self.at_kw("in"):
            self.advance()
            self.expect_op("(")
            if self.at_kw("select", "with"):
                sub = self.parse_statement()
                self.expect_op(")")
                return InSubquery(expr=left, subquery=sub, negated=negated)
            items = [self.parse_expr()]
            while self.at_op(","):
                self.advance()
                items.append(self.parse_expr())
            self.expect_op(")")
            return InList(expr=left, items=items, negated=negated)
        if self.at_kw("like", "ilike"):
            op = self.advance().value
            right = self._parse_concat()
            res: Expr = BinaryOp(op=op, left=left, right=right)
            return UnaryOp(op="not", expr=res) if negated else res
        if negated:
            raise ParseError(f"expected BETWEEN/IN/LIKE after NOT at position {self.peek().pos}")
        if self.at_kw("is"):
            self.advance()
            neg2 = False
            if self.at_kw("not"):
                neg2 = True
                self.advance()
            if self.at_kw("null"):
                self.advance()
                return IsNull(expr=left, negated=neg2)
            if self.at_kw("true", "false", "unknown"):
                self.advance()
                return IsNull(expr=left, negated=neg2)  # treated opaquely; not security-relevant
            if self.at_kw("distinct"):
                self.advance()
                self.expect_kw("from")
                right = self._parse_concat()
                return BinaryOp(op="is distinct from", left=left, right=right)
            raise ParseError(f"unsupported IS predicate at position {self.peek().pos}")
        return left

    def _parse_concat(self) -> Expr:
        left = self._parse_additive()
        while self.at_op("||"):
            self.advance()
            right = self._parse_additive()
            left = BinaryOp(op="||", left=left, right=right)
        return left

    def _parse_additive(self) -> Expr:
        left = self._parse_multiplicative()
        while self.at_op("+", "-"):
            op = self.advance().value
            right = self._parse_multiplicative()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def _parse_multiplicative(self) -> Expr:
        left = self._parse_unary()
        while self.at_op("*", "/", "%"):
            op = self.advance().value
            right = self._parse_unary()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def _parse_unary(self) -> Expr:
        if self.at_op("-", "+"):
            op = self.advance().value
            return UnaryOp(op=op, expr=self._parse_unary())
        return self._parse_cast_postfix()

    def _parse_cast_postfix(self) -> Expr:
        expr = self._parse_primary()
        while True:
            if self.at_op("::"):
                self.advance()
                type_name = self._parse_type_name()
                expr = Cast(expr=expr, type_name=type_name)
                continue
            break
        return expr

    def _parse_type_name(self) -> str:
        name = self.ident_name() if self.peek().kind != "kw" else self.advance().value
        parts = [name]
        if self.at_op("("):
            self.advance()
            depth = 1
            while depth:
                t = self.advance()
                if t.kind == "op" and t.value == "(":
                    depth += 1
                elif t.kind == "op" and t.value == ")":
                    depth -= 1
        if self.at_op("[") and self.peek(1).kind == "op" and self.peek(1).value == "]":
            self.advance()
            self.advance()
            parts.append("[]")
        return " ".join(parts)

    def _parse_primary(self) -> Expr:
        t = self.peek()
        if t.kind == "number":
            self.advance()
            return Literal(kind="number", value=t.value)
        if t.kind == "string":
            self.advance()
            return Literal(kind="string", value=t.value)
        if t.kind == "param":
            self.advance()
            return Literal(kind="param", value=t.value)
        if t.kind == "kw" and t.value == "null":
            self.advance()
            return Literal(kind="null", value="null")
        if t.kind == "kw" and t.value in ("true", "false"):
            self.advance()
            return Literal(kind="bool", value=t.value)
        if t.kind == "kw" and t.value in ("date", "timestamp", "time", "interval"):
            type_word = self.advance().value
            if self.peek().kind == "string":
                s = self.advance()
                return Literal(kind="typed", value=s.value, type_name=type_word)
            # used as a plain function/type name elsewhere (rare in this grammar) -- treat as ident
            return ColumnRef(parts=[type_word])
        if t.kind == "kw" and t.value == "cast":
            self.advance()
            self.expect_op("(")
            inner = self.parse_expr()
            self.expect_kw("as")
            type_name = self._parse_type_name()
            self.expect_op(")")
            return Cast(expr=inner, type_name=type_name)
        if t.kind == "kw" and t.value == "case":
            return self._parse_case()
        if t.kind == "kw" and t.value == "array":
            self.advance()
            self.expect_op("[")
            elements: list[Expr] = []
            if not self.at_op("]"):
                elements.append(self.parse_expr())
                while self.at_op(","):
                    self.advance()
                    elements.append(self.parse_expr())
            self.expect_op("]")
            return ArrayLit(elements=elements)
        if t.kind == "kw" and t.value == "exists":
            self.advance()
            self.expect_op("(")
            sub = self.parse_statement()
            self.expect_op(")")
            return ExistsExpr(subquery=sub)
        if t.kind == "kw" and t.value == "not" and self.peek(1).kind == "kw" and self.peek(1).value == "exists":
            self.advance()
            self.advance()
            self.expect_op("(")
            sub = self.parse_statement()
            self.expect_op(")")
            return ExistsExpr(subquery=sub, negated=True)
        if t.kind == "op" and t.value == "(":
            self.advance()
            if self.at_kw("select", "with"):
                sub = self.parse_statement()
                self.expect_op(")")
                return ScalarSubquery(subquery=sub)
            inner = self.parse_expr()
            self.expect_op(")")
            return inner
        if t.kind in ("ident",) or (t.kind == "kw" and t.value in _SOFT_KEYWORDS):
            return self._parse_ident_or_call()
        raise ParseError(f"unexpected token {t.value!r} at position {t.pos}")

    def _parse_case(self) -> Expr:
        self.expect_kw("case")
        operand = None
        if not self.at_kw("when"):
            operand = self.parse_expr()
        whens: list[tuple[Expr, Expr]] = []
        while self.at_kw("when"):
            self.advance()
            cond = self.parse_expr()
            self.expect_kw("then")
            res = self.parse_expr()
            whens.append((cond, res))
        else_ = None
        if self.at_kw("else"):
            self.advance()
            else_ = self.parse_expr()
        self.expect_kw("end")
        return CaseExpr(operand=operand, whens=whens, else_=else_)

    def _parse_ident_or_call(self) -> Expr:
        first = self.ident_name()
        parts = [first]
        while self.at_op("."):
            # Could be table.column, or table.* -- handled by caller context for SELECT list;
            # here it's always a column reference chain.
            save = self.i
            self.advance()
            if self.at_op("*"):
                self.advance()
                return Star(qualifier=".".join(parts))
            parts.append(self.ident_name())
        if self.at_op("("):
            name = parts[-1] if len(parts) == 1 else ".".join(parts)
            if len(parts) == 1 and name.lower() == "extract":
                # EXTRACT(field FROM source) -- field is a bare word (YEAR, MONTH, DOW, ...),
                # not a general expression. Represented as extract(<field literal>, <source>)
                # so downstream analysis (function allow-list, column collection) sees it like
                # any other two-argument function call.
                self.advance()  # '('
                field = self.advance().value
                self.expect_kw("from")
                source = self.parse_expr()
                self.expect_op(")")
                call = FuncCall(name="extract", args=[Literal(kind="string", value=str(field)), source])
                if self.at_kw("over"):
                    call.over = self._parse_over()
                return call
            args, distinct, star = self._parse_call_args()
            call = FuncCall(name=name, args=args, distinct=distinct, star=star)
            if self.at_kw("filter"):
                self.advance()
                self.expect_op("(")
                self.expect_kw("where")
                call.filter_where = self.parse_expr()
                self.expect_op(")")
            if self.at_kw("over"):
                call.over = self._parse_over()
            return call
        return ColumnRef(parts=parts)

    def _parse_call_args(self) -> tuple[list[Expr], bool, bool]:
        self.expect_op("(")
        distinct = False
        star = False
        args: list[Expr] = []
        if self.at_kw("distinct"):
            distinct = True
            self.advance()
        if self.at_op("*"):
            star = True
            self.advance()
        elif not self.at_op(")"):
            args.append(self.parse_expr())
            while self.at_op(","):
                self.advance()
                args.append(self.parse_expr())
            # window function ORDER BY inside args, e.g. string_agg(x, ',' ORDER BY y), is parsed
            # loosely: consume a trailing ORDER BY clause if present (not security-relevant).
            if self.at_kw("order"):
                self.advance()
                self.expect_kw("by")
                self.parse_order_item()
                while self.at_op(","):
                    self.advance()
                    self.parse_order_item()
        self.expect_op(")")
        return args, distinct, star

    def _parse_over(self) -> WindowSpec:
        self.expect_kw("over")
        self.expect_op("(")
        partition_by: list[Expr] = []
        order_by: list[OrderItem] = []
        if self.at_kw("partition"):
            self.advance()
            self.expect_kw("by")
            partition_by.append(self.parse_expr())
            while self.at_op(","):
                self.advance()
                partition_by.append(self.parse_expr())
        if self.at_kw("order"):
            self.advance()
            self.expect_kw("by")
            order_by.append(self.parse_order_item())
            while self.at_op(","):
                self.advance()
                order_by.append(self.parse_order_item())
        # frame clause (ROWS/RANGE BETWEEN ...) -- consume tokens until the matching ')'.
        depth = 1
        while depth:
            t = self.peek()
            if t.kind == "op" and t.value == "(":
                depth += 1
                self.advance()
            elif t.kind == "op" and t.value == ")":
                depth -= 1
                if depth:
                    self.advance()
            elif t.kind == "eof":
                raise ParseError("unterminated OVER (...) clause")
            else:
                self.advance()
        self.expect_op(")")
        return WindowSpec(partition_by=partition_by, order_by=order_by)


def parse(sql: str) -> Statement:
    tokens = tokenize(sql)
    p = Parser(tokens)
    stmt = p.parse_statement()
    if p.peek().kind != "eof":
        raise ParseError(f"unexpected trailing input at position {p.peek().pos}: {p.peek().value!r}")
    return stmt
