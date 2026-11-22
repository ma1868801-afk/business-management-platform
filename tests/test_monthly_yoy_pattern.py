from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.graph.data_analysis import (
    _format_monthly_yoy_answer,
    _monthly_yoy_pandas_code,
    _monthly_yoy_sql,
    _monthly_yoy_years,
)
from app.guards.pandas_validator import validate_pandas_code
from app.guards.sql_validator import validate_sql
from app.tools.pandas_tool import pandas_tool


QUESTION = (
    "Compare total net sales for every month in 2024 and 2025. Identify the top 3 "
    "months with the highest sales in each year, calculate the year-over-year "
    "growth for each month, and summarize the overall trend"
)


def test_monthly_yoy_query_selects_the_documented_year_pair() -> None:
    assert _monthly_yoy_years(QUESTION) == (2024, 2025)
    assert _monthly_yoy_years("What were total sales in 2024 and 2025?") is None
    assert _monthly_yoy_years("Show monthly sales trend in 2025") is None


def test_monthly_yoy_sql_passes_the_real_sql_validator() -> None:
    sql = _monthly_yoy_sql((2024, 2025))
    checked = validate_sql(sql, max_rows=500)
    assert checked.ok, (checked.code, checked.message)
    assert "FILTER (WHERE year = 2024)" in checked.sql
    assert "FILTER (WHERE year = 2025)" in checked.sql
    assert "LIMIT 1000" not in checked.sql
    assert "::int" not in checked.sql.lower()


def test_monthly_yoy_pandas_pattern_executes_in_the_isolated_worker() -> None:
    code = _monthly_yoy_pandas_code((2024, 2025))
    checked = validate_pandas_code(code)
    assert checked.ok, (checked.code, checked.message)

    rows = [
        {
            "month": month,
            "net_revenue_2024_sar": float(month * 1000),
            "net_revenue_2025_sar": float(month * (1100 if month % 2 else 900)),
        }
        for month in range(1, 13)
    ]
    result = pandas_tool(code, df=rows)
    assert "error" not in result, result
    assert len(result["result"]) == 12
    assert len(result["facts"]["top_2024"]) == 3
    assert len(result["facts"]["top_2025"]) == 3
    assert result["facts"]["months_increased"] == 6
    assert result["facts"]["months_decreased"] == 6
    answer = _format_monthly_yoy_answer(result, (2024, 2025))
    assert "Top 3 months in 2024" in answer
    assert "Top 3 months in 2025" in answer
    assert "Monthly year-over-year comparison" in answer
    assert "Overall net sales changed" in answer
