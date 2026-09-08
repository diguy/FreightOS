from __future__ import annotations

import json

from scripts.run_formal_intent_regression import (
    _extract_intent_result,
    _validate_database_fixtures,
    run_regression,
)


class FakeDifyClient:
    def __init__(self, settings=None, failures=None):
        self.calls = []
        self.failures = failures or {}

    def chat(self, *, query, user, conversation_id=None, inputs=None):
        self.calls.append((query, user))
        case_id = user.rsplit("-", 1)[-1]
        if case_id in self.failures:
            from app.agent.dify_client import DifyClientError

            raise DifyClientError(self.failures[case_id])
        return {"answer": json.dumps({
            "intent": "unknown",
            "confidence": 0.0,
            "entities": {
                "order_id": None,
                "ticket_no": None,
                "new_address": None,
                "complaint_content": None,
                "contact": None,
            },
            "missing_slots": [],
            "action": "clarify",
            "should_call_tool": False,
        })}


def test_formal_regression_writes_timestamped_prediction_and_report(
    tmp_path, monkeypatch
):
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    case = {
        "id": "case-1",
        "query": "你好",
        "expected_intent": "unknown",
        "expected_entities": {
            "order_id": None,
            "ticket_no": None,
            "new_address": None,
            "complaint_content": None,
            "contact": None,
        },
        "expected_missing_slots": [],
        "should_call_tool": False,
    }
    for name, case_id in (
        ("intent_cases.jsonl", "case-basic"),
        ("intent_adversarial_cases.jsonl", "case-adversarial"),
    ):
        case["id"] = case_id
        (cases_dir / name).write_text(
            json.dumps(case, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    fake = FakeDifyClient()
    monkeypatch.setattr(
        "scripts.run_formal_intent_regression.HttpDifyClient",
        lambda settings: fake,
    )
    monkeypatch.setenv("DIFY_API_KEY", "test-key")

    predictions, report = run_regression(
        cases_dir=cases_dir,
        output_dir=tmp_path / "results",
        user="test-user",
        delay_seconds=0,
    )

    assert predictions.name.startswith("formal-50-dify_outputs-")
    assert report.name.startswith("formal-50-intent-regression-")
    assert len(predictions.read_text(encoding="utf-8").splitlines()) == 2
    assert json.loads(report.read_text(encoding="utf-8"))["sets"]["basic"][
        "intent"
    ]["accuracy"] == 1.0


def test_formal_regression_continues_after_dify_case_failure(
    tmp_path, monkeypatch
):
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    payload = {
        "expected_intent": "unknown",
        "expected_entities": {
            "order_id": None,
            "ticket_no": None,
            "new_address": None,
            "complaint_content": None,
            "contact": None,
        },
        "expected_missing_slots": [],
        "should_call_tool": False,
    }
    for filename, case_id in (
        ("intent_cases.jsonl", "case-1"),
        ("intent_adversarial_cases.jsonl", "case-2"),
    ):
        (cases_dir / filename).write_text(
            json.dumps({"id": case_id, "query": "你好", **payload}) + "\n",
            encoding="utf-8",
        )

    fake = FakeDifyClient(failures={"1": "temporary timeout"})
    monkeypatch.setattr(
        "scripts.run_formal_intent_regression.HttpDifyClient",
        lambda settings: fake,
    )
    monkeypatch.setenv("DIFY_API_KEY", "test-key")

    predictions, report = run_regression(
        cases_dir=cases_dir,
        output_dir=tmp_path / "results",
        user="test-user",
        delay_seconds=0,
    )

    records = [
        json.loads(line)
        for line in predictions.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 2
    assert records[0]["result_json"] is None
    assert records[0]["error"] == "temporary timeout"
    assert json.loads(records[1]["result_json"])["intent"] == "unknown"
    report_data = json.loads(report.read_text(encoding="utf-8"))
    assert report_data["execution_failures"] == [
        {"id": "case-1", "error": "temporary timeout"}
    ]
    assert len(fake.calls) == 2


def test_ticket_fixture_validation_rejects_missing_mysql_ticket(monkeypatch):
    class Cursor:
        def execute(self, query, params):
            self.params = params

        def fetchall(self):
            return []

        def close(self):
            pass

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr(
        "scripts.run_formal_intent_regression.get_mysql_connection",
        lambda: Connection(),
    )

    cases = [
        {
            "id": "ticket-case",
            "expected_intent": "ticket_status",
            "expected_entities": {"ticket_no": "T-MISSING"},
        }
    ]

    try:
        _validate_database_fixtures(cases, user_id="demo-user-001")
    except RuntimeError as error:
        assert "T-MISSING" in str(error)
    else:
        raise AssertionError("missing ticket fixture should fail preflight")


def test_extract_intent_result_from_backend_wrapped_answer():
    response = {
        "answer": json.dumps(
            {
                "success": True,
                "data": {
                    "intent_result": {
                        "intent": "ticket_status",
                        "confidence": 0.95,
                    }
                },
            }
        )
    }

    assert _extract_intent_result(response) == {
        "intent": "ticket_status",
        "confidence": 0.95,
    }
