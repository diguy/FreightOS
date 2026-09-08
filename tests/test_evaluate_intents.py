import json

from evaluation.evaluate_intents import build_report, evaluate_cases, main


def _result(
    *,
    intent="tracking_query",
    confidence=0.98,
    entities=None,
    missing_slots=None,
    action="query",
    should_call_tool=True,
):
    return json.dumps(
        {
            "intent": intent,
            "confidence": confidence,
            "entities": entities
            or {
                "order_id": "ORD1001",
                "ticket_no": None,
                "new_address": None,
                "complaint_content": None,
                "contact": None,
            },
            "missing_slots": missing_slots or [],
            "action": action,
            "should_call_tool": should_call_tool,
        },
        ensure_ascii=False,
    )


def test_evaluate_cases_reports_all_metrics_and_unsafe_calls():
    cases = [
        {
            "id": "ok",
            "expected_intent": "tracking_query",
            "expected_entities": {
                "order_id": "ORD1001",
                "ticket_no": None,
                "new_address": None,
                "complaint_content": None,
                "contact": None,
            },
            "expected_missing_slots": [],
            "should_call_tool": True,
        },
        {
            "id": "blocked",
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
        },
    ]
    predictions = {
        "ok": _result(),
        "blocked": _result(
            intent="unknown",
            confidence=0.99,
            entities={
                "order_id": None,
                "ticket_no": None,
                "new_address": None,
                "complaint_content": None,
                "contact": None,
            },
            action="clarify",
            should_call_tool=True,
        ),
    }

    report = evaluate_cases(cases, predictions)

    assert report["intent"]["accuracy"] == 1.0
    assert report["entities"]["accuracy"] == 1.0
    assert report["missing_slots"]["accuracy"] == 1.0
    assert report["tool_gate"]["accuracy"] == 1.0
    assert report["unsafe_tool_calls"] == 0
    assert report["unsafe_tool_call_rate"] == 0.0


def test_evaluate_cases_missing_prediction_is_safe_unknown():
    cases = [
        {
            "id": "missing",
            "expected_intent": "tracking_query",
            "expected_entities": {
                "order_id": "ORD1001",
                "ticket_no": None,
                "new_address": None,
                "complaint_content": None,
                "contact": None,
            },
            "expected_missing_slots": [],
            "should_call_tool": True,
        }
    ]

    report = evaluate_cases(cases, {})

    assert report["missing_predictions"] == 1
    assert report["intent"]["accuracy"] == 0.0
    assert report["unsafe_tool_calls"] == 0


def test_build_report_separates_basic_and_adversarial(tmp_path):
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    basic = cases_dir / "intent_cases.jsonl"
    adversarial = cases_dir / "intent_adversarial_cases.jsonl"
    prediction_file = tmp_path / "predictions.jsonl"

    base_case = {
        "id": "basic-1",
        "expected_intent": "tracking_query",
        "expected_entities": {
            "order_id": "ORD1001",
            "ticket_no": None,
            "new_address": None,
            "complaint_content": None,
            "contact": None,
        },
        "expected_missing_slots": [],
        "should_call_tool": True,
    }
    adversarial_case = {
        **base_case,
        "id": "adv-1",
        "expected_intent": "unknown",
        "should_call_tool": False,
    }
    basic.write_text(json.dumps(base_case) + "\n", encoding="utf-8")
    adversarial.write_text(json.dumps(adversarial_case) + "\n", encoding="utf-8")
    prediction_file.write_text(
        json.dumps({"id": "basic-1", "result_json": _result()}) + "\n"
        + json.dumps(
            {
                "id": "adv-1",
                "result_json": _result(
                    intent="unknown",
                    confidence=0.0,
                    entities={
                        "order_id": None,
                        "ticket_no": None,
                        "new_address": None,
                        "complaint_content": None,
                        "contact": None,
                    },
                    action="clarify",
                    should_call_tool=False,
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_report([basic, adversarial], prediction_file)

    assert set(report["sets"]) == {"basic", "adversarial"}
    assert report["sets"]["basic"]["intent"]["accuracy"] == 1.0
    assert report["sets"]["adversarial"]["intent"]["accuracy"] == 1.0


def test_cli_writes_regression_report(tmp_path, capsys):
    prediction_file = tmp_path / "predictions.jsonl"
    report_file = tmp_path / "results" / "baseline.json"
    prediction_file.write_text(
        json.dumps(
            {
                "id": "intent-001",
                "result_json": _result(),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--predictions",
            str(prediction_file),
            "--cases-dir",
            "evaluation/cases",
            "--output",
            str(report_file),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "[basic]" in output
    assert "[adversarial]" in output
    assert report_file.exists()
