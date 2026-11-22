from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.graph.data_analysis import _default_sql_generator as da_sql_generator
from app.graph.inventory import _default_sql_generator as inventory_sql_generator
from app.llm.client import GroqClient, LLMResult, SQLFormatError, extract_plain_sql


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("SELECT sku FROM products LIMIT 10", "SELECT sku FROM products LIMIT 10"),
        ("WITH x AS (SELECT 1) SELECT * FROM x", "WITH x AS (SELECT 1) SELECT * FROM x"),
        ("```sql\nSELECT 1\n```", "SELECT 1"),
        ("```postgresql\nWITH x AS (SELECT 1) SELECT * FROM x;\n```", "WITH x AS (SELECT 1) SELECT * FROM x;"),
    ],
)
def test_extract_plain_sql_accepts_select_cte_and_single_fence(raw, expected):
    assert extract_plain_sql(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        '{"sql": "SELECT * FROM products"}',
        "Here is the SQL:\nSELECT * FROM products",
        "DROP TABLE products",
        "[SELECT 1]",
    ],
)
def test_extract_plain_sql_rejects_json_prose_and_non_select(raw):
    with pytest.raises(SQLFormatError):
        extract_plain_sql(raw)


def test_complete_sql_uses_plain_text_and_returns_clean_sql(monkeypatch):
    client = GroqClient(api_key="", model="test")
    calls = {}

    def fake_complete_text(system, user, **kwargs):
        calls["system"] = system
        calls["kwargs"] = kwargs
        return LLMResult(data=None, raw_text="```sql\nSELECT 1\n```", elapsed_ms=4)

    monkeypatch.setattr(client, "complete_text", fake_complete_text)
    result = client.complete_sql("Write SQL", "Count products")
    assert result.raw_text == "SELECT 1"
    assert result.error is None
    assert "JSON" not in calls["system"]


def test_complete_sql_keeps_invalid_response_for_validator_retry(monkeypatch):
    client = GroqClient(api_key="", model="test")
    monkeypatch.setattr(
        client,
        "complete_text",
        lambda *args, **kwargs: LLMResult(data=None, raw_text='{"sql":"SELECT 1"}', elapsed_ms=1),
    )
    result = client.complete_sql("Write SQL", "Count products")
    assert result.raw_text == '{"sql":"SELECT 1"}'
    assert result.error and result.error.startswith("invalid_sql_format:")


@pytest.mark.parametrize("factory", [da_sql_generator, inventory_sql_generator])
def test_default_sql_generators_use_plain_sql_contract(factory, monkeypatch):
    class FakeLLM:
        def __init__(self):
            self.called = False

        def complete_sql(self, system, user, **kwargs):
            self.called = True
            assert "ONLY" in system
            assert "Respond as JSON" not in system
            return LLMResult(data=None, raw_text="SELECT 1 LIMIT 1", elapsed_ms=1)

    fake = FakeLLM()
    generated = factory(fake)("count", [{"text": "schema"}], None)
    assert fake.called
    assert generated == "SELECT 1 LIMIT 1"
