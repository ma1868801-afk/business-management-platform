from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.graph.data_analysis import (
    _default_answer_composer,
    _llm_answer_composer,
)


class FakeLLM:
    def __init__(self, data):
        self.data = data
        self.last_system = None
        self.last_user = None

    def complete_json(self, system, user, max_tokens=500):
        self.last_system = system
        self.last_user = user
        return SimpleNamespace(data=self.data)


def test_llm_answer_composer_success():
    result = {
        "columns": ["net_revenue_sar"],
        "rows": [["2483897.44"]],
    }

    llm = FakeLLM({
        "answer": "Total sales in January 2025 were SAR 2,483,897.44."
    })

    answer, used_llm = _llm_answer_composer(
        "What were the total sales in January 2025?",
        result,
        llm,
    )

    assert used_llm is True
    assert answer == "Total sales in January 2025 were SAR 2,483,897.44."
    assert "2483897.44" in llm.last_user
    assert "Do not invent" in llm.last_system


def test_llm_answer_composer_fallback():
    result = {
        "columns": ["net_revenue_sar"],
        "rows": [["2483897.44"]],
    }

    llm = FakeLLM(None)

    answer, used_llm = _llm_answer_composer(
        "What were the total sales?",
        result,
        llm,
    )

    assert used_llm is False
    assert answer == _default_answer_composer(
        "What were the total sales?",
        result,
    )
