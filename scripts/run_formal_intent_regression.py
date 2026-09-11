"""Run the formal intent regression set against the currently configured Dify app."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.dify_client import DifyClientError, DifySettings, HttpDifyClient
from app.mysql_database import get_mysql_connection
from scripts.evaluation.evaluate_intents import build_report


def _read_cases(path: Path) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number} is invalid JSON") from error
            if not isinstance(record, dict) or "id" not in record or "query" not in record:
                raise ValueError(f"{path}:{line_number} must contain id and query")
            cases.append(record)
    return cases


def _all_cases(cases_dir: Path) -> list[dict[str, object]]:
    return _read_cases(cases_dir / "intent_cases.jsonl") + _read_cases(
        cases_dir / "intent_adversarial_cases.jsonl"
    )


def _validate_database_fixtures(
    cases: list[dict[str, object]],
    *,
    user_id: str,
) -> None:
    """Fail before Dify execution when live fixtures drift from MySQL."""

    expected_ticket_numbers = {
        str(case["expected_entities"]["ticket_no"]).strip().upper()
        for case in cases
        if case.get("expected_intent") == "ticket_status"
        and isinstance(case.get("expected_entities"), dict)
        and case["expected_entities"].get("ticket_no")
    }
    expected_order_numbers = {
        str(case["expected_entities"]["order_id"]).strip().upper()
        for case in cases
        if case.get("expected_entities", {}).get("order_id")
    }
    if not expected_ticket_numbers and not expected_order_numbers:
        return

    connection = get_mysql_connection()
    try:
        cursor = connection.cursor()
        actual_ticket_numbers: set[str] = set()
        if expected_ticket_numbers:
            placeholders = ", ".join(["%s"] * len(expected_ticket_numbers))
            cursor.execute(
                f"""
                SELECT ticket_no
                FROM tickets
                WHERE user_id = %s
                  AND ticket_no IN ({placeholders})
                """,
                (user_id, *sorted(expected_ticket_numbers)),
            )
            actual_ticket_numbers = {
                str(row["ticket_no"]).strip().upper()
                for row in cursor.fetchall()
            }

        actual_order_numbers: set[str] = set()
        if expected_order_numbers:
            placeholders = ", ".join(["%s"] * len(expected_order_numbers))
            cursor.execute(
                f"""
                SELECT order_no
                FROM orders
                WHERE user_id = %s
                  AND order_no IN ({placeholders})
                """,
                (user_id, *sorted(expected_order_numbers)),
            )
            actual_order_numbers = {
                str(row["order_no"]).strip().upper()
                for row in cursor.fetchall()
            }
        cursor.close()
    finally:
        connection.close()

    missing_tickets = sorted(expected_ticket_numbers - actual_ticket_numbers)
    missing_orders = sorted(expected_order_numbers - actual_order_numbers)
    if missing_tickets or missing_orders:
        details = []
        if missing_tickets:
            details.append(f"tickets={', '.join(missing_tickets)}")
        if missing_orders:
            details.append(f"orders={', '.join(missing_orders)}")
        raise RuntimeError(
            "regression fixtures are missing from MySQL "
            f"for user {user_id}: {'; '.join(details)}"
        )


def _extract_intent_result(response: dict[str, object]) -> object:
    """Extract the intent payload from the backend-wrapped Dify answer."""

    answer = response.get("answer")
    if isinstance(answer, str):
        try:
            answer_payload = json.loads(answer)
        except json.JSONDecodeError:
            return answer
    else:
        answer_payload = answer

    if isinstance(answer_payload, dict):
        data = answer_payload.get("data")
        if isinstance(data, dict) and "intent_result" in data:
            return data["intent_result"]
        if "intent_result" in answer_payload:
            return answer_payload["intent_result"]
    return answer


def run_regression(
    *,
    cases_dir: Path,
    output_dir: Path,
    user: str,
    delay_seconds: float,
) -> tuple[Path, Path]:
    settings = DifySettings.from_env()
    if not settings.api_key:
        raise ValueError("DIFY_API_KEY is not configured")

    cases = _all_cases(cases_dir)
    backend_user_id = os.getenv("DIFY_AGENT_USER_ID", "demo-user-001")
    _validate_database_fixtures(cases, user_id=backend_user_id)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    predictions_path = output_dir / f"formal-50-dify_outputs-{timestamp}.jsonl"
    report_path = output_dir / f"formal-50-intent-regression-{timestamp}.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    client = HttpDifyClient(settings)
    execution_failures: list[dict[str, str]] = []
    with predictions_path.open("w", encoding="utf-8") as output:
        for index, case in enumerate(cases, start=1):
            case_id = str(case["id"])
            query = str(case["query"])
            try:
                response = client.chat(
                    query=query,
                    user=f"{user}-{case_id}",
                )
            except DifyClientError as error:
                message = str(error)
                execution_failures.append({"id": case_id, "error": message})
                output.write(
                    json.dumps(
                        {"id": case_id, "result_json": None, "error": message},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                output.flush()
                print(f"[{index}/{len(cases)}] {case_id} FAILED: {message}", flush=True)
                if delay_seconds:
                    time.sleep(delay_seconds)
                continue

            result_json = _extract_intent_result(response)
            output.write(
                json.dumps(
                    {"id": case_id, "result_json": result_json},
                    ensure_ascii=False,
                )
                + "\n"
            )
            output.flush()
            print(f"[{index}/{len(cases)}] {case_id}", flush=True)
            if delay_seconds:
                time.sleep(delay_seconds)

    report = build_report(
        [
            cases_dir / "intent_cases.jsonl",
            cases_dir / "intent_adversarial_cases.jsonl",
        ],
        predictions_path,
    )
    report["execution_failures"] = execution_failures
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return predictions_path, report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-dir", type=Path, default=Path("scripts/evaluation/cases"))
    parser.add_argument("--output-dir", type=Path, default=Path("scripts/evaluation/results"))
    parser.add_argument("--user", default="formal-intent-regression-20260907")
    parser.add_argument("--delay-seconds", type=float, default=0.0)
    args = parser.parse_args(argv)

    try:
        predictions_path, report_path = run_regression(
            cases_dir=args.cases_dir,
            output_dir=args.output_dir,
            user=args.user,
            delay_seconds=args.delay_seconds,
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"formal regression failed: {error}", file=sys.stderr)
        return 1

    print(f"predictions: {predictions_path}")
    print(f"report: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    failures = report.get("execution_failures", [])
    if failures:
        print(f"execution_failures: {len(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
