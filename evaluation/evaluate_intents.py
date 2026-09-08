"""Batch evaluation for Dify intent-recognition outputs."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Keep direct execution (`python evaluation/evaluate_intents.py`) working.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.dify_output_parser import parse_dify_output


ENTITY_FIELDS = (
    "order_id",
    "ticket_no",
    "new_address",
    "complaint_content",
    "contact",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read non-empty JSONL records and fail with a useful line number."""

    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path}:{line_number} is not valid JSON: {exc.msg}"
                ) from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number} must be a JSON object")
            records.append(record)
    return records


def _entities_match(expected: Mapping[str, Any], actual: Any) -> bool:
    if not isinstance(actual, Mapping):
        return False
    return all(actual.get(field) == expected.get(field) for field in ENTITY_FIELDS)


def _slots_match(expected: Any, actual: Any) -> bool:
    if not isinstance(expected, list) or not isinstance(actual, list):
        return False
    return set(expected) == set(actual)


def _metric(correct: int, total: int) -> dict[str, Any]:
    return {
        "correct": correct,
        "total": total,
        "accuracy": round(correct / total, 4) if total else 0.0,
    }


def evaluate_cases(
    cases: Iterable[Mapping[str, Any]],
    predictions: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate parsed Dify outputs against expected JSONL case records."""

    records = list(cases)
    intent_correct = 0
    entity_correct = 0
    slots_correct = 0
    gate_correct = 0
    unsafe_tool_calls = 0
    missing_predictions = 0
    invalid_predictions = 0
    by_case: list[dict[str, Any]] = []

    for case in records:
        case_id = str(case["id"])
        raw_prediction = predictions.get(case_id)
        if raw_prediction is None:
            missing_predictions += 1
            actual = parse_dify_output(None)
        else:
            actual = parse_dify_output(raw_prediction)
            if actual.intent == "unknown" and case["expected_intent"] != "unknown":
                invalid_predictions += 1

        expected_entities = case.get("expected_entities", {})
        expected_slots = case.get("expected_missing_slots", [])
        expected_gate = case.get("should_call_tool", False)
        actual_entities = actual.entities.model_dump()

        intent_ok = actual.intent == case["expected_intent"]
        entities_ok = _entities_match(expected_entities, actual_entities)
        slots_ok = _slots_match(expected_slots, actual.missing_slots)
        gate_ok = actual.should_call_tool is expected_gate
        unsafe_call = actual.should_call_tool and not expected_gate

        intent_correct += intent_ok
        entity_correct += entities_ok
        slots_correct += slots_ok
        gate_correct += gate_ok
        unsafe_tool_calls += unsafe_call

        by_case.append(
            {
                "id": case_id,
                "intent_correct": intent_ok,
                "entity_correct": entities_ok,
                "missing_slots_correct": slots_ok,
                "tool_gate_correct": gate_ok,
                "unsafe_tool_call": unsafe_call,
                "actual": {
                    "intent": actual.intent,
                    "entities": actual_entities,
                    "missing_slots": actual.missing_slots,
                    "should_call_tool": actual.should_call_tool,
                },
            }
        )

    total = len(records)
    expected_tool_denominator = sum(
        not bool(case.get("should_call_tool", False)) for case in records
    )
    return {
        "total": total,
        "intent": _metric(intent_correct, total),
        "entities": _metric(entity_correct, total),
        "missing_slots": _metric(slots_correct, total),
        "tool_gate": _metric(gate_correct, total),
        "unsafe_tool_calls": unsafe_tool_calls,
        "unsafe_tool_call_rate": round(
            unsafe_tool_calls / expected_tool_denominator, 4
        )
        if expected_tool_denominator
        else 0.0,
        "missing_predictions": missing_predictions,
        "invalid_predictions": invalid_predictions,
        "cases": by_case,
    }


def _prediction_records(path: Path) -> dict[str, Any]:
    predictions: dict[str, Any] = {}
    for record in read_jsonl(path):
        if "id" not in record or "result_json" not in record:
            raise ValueError(
                f"{path} records must contain 'id' and 'result_json'"
            )
        case_id = str(record["id"])
        if case_id in predictions:
            raise ValueError(f"{path} contains duplicate prediction id: {case_id}")
        predictions[case_id] = record["result_json"]
    return predictions


def build_report(
    case_paths: Iterable[Path],
    predictions_path: Path,
) -> dict[str, Any]:
    """Build a report with separate summaries for each case set."""

    predictions = _prediction_records(predictions_path)
    sets = {}
    for case_path in case_paths:
        cases = read_jsonl(case_path)
        set_name = (
            "adversarial"
            if "adversarial" in case_path.stem
            else "basic"
        )
        sets[set_name] = evaluate_cases(cases, predictions)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "predictions_file": str(predictions_path),
        "sets": sets,
    }


def _print_summary(report: Mapping[str, Any]) -> None:
    print(f"predictions: {report['predictions_file']}")
    for set_name, summary in report["sets"].items():
        print(f"\n[{set_name}] total={summary['total']}")
        for metric_name in ("intent", "entities", "missing_slots", "tool_gate"):
            metric = summary[metric_name]
            print(
                f"{metric_name}_accuracy: "
                f"{metric['correct']}/{metric['total']} "
                f"({metric['accuracy']:.2%})"
            )
        print(
            "unsafe_tool_calls: "
            f"{summary['unsafe_tool_calls']} "
            f"({summary['unsafe_tool_call_rate']:.2%})"
        )
        print(f"missing_predictions: {summary['missing_predictions']}")
        print(f"invalid_predictions: {summary['invalid_predictions']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate Dify intent-recognition result_json JSONL outputs."
    )
    parser.add_argument(
        "--predictions",
        required=True,
        type=Path,
        help="JSONL with records such as {\"id\": \"intent-001\", \"result_json\": \"...\"}",
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=Path("evaluation/cases"),
        help="Directory containing intent_cases.jsonl and intent_adversarial_cases.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for a JSON regression report.",
    )
    args = parser.parse_args(argv)

    case_paths = [
        args.cases_dir / "intent_cases.jsonl",
        args.cases_dir / "intent_adversarial_cases.jsonl",
    ]
    try:
        report = build_report(case_paths, args.predictions)
    except (OSError, ValueError, KeyError) as exc:
        print(f"evaluation failed: {exc}", file=sys.stderr)
        return 2

    _print_summary(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nreport: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
