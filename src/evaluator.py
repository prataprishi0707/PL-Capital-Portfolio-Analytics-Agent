
import json
import sqlite3
import pandas as pd
from pathlib import Path

from database import run_sql_query
from exposure_calculator import calculate_sector_exposure


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH_PATH = PROJECT_ROOT / "ground_truth_dataset.json"
DB_PATH = PROJECT_ROOT / "portfolio_database.db"


def load_ground_truth():

    with open(GROUND_TRUTH_PATH, "r") as file:
        dataset = json.load(file)

    return dataset["questions"]


def execute_ground_truth_sql(query):

    conn = sqlite3.connect(DB_PATH)

    try:
        result = pd.read_sql_query(query, conn)

        return {
            "success": True,
            "rows": result.to_dict(orient="records"),
            "row_count": len(result)
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }

    finally:
        conn.close()


def normalize_value(value):

    if value is None:
        return None

    if isinstance(value, (int, float)):
        return round(float(value), 4)

    return str(value).strip().lower()


# FIX: Compare column names and values,
# independent of dictionary column insertion order.
def normalize_rows(rows):

    normalized = []

    for row in rows:

        normalized_row = tuple(
            sorted(
                [
                    (
                        str(column).strip().lower(),
                        normalize_value(value)
                    )
                    for column, value in row.items()
                ],
                key=lambda item: item[0]
            )
        )

        normalized.append(normalized_row)

    return sorted(normalized, key=str)


def compare_results(actual, expected):

    if not actual.get("success") or not expected.get("success"):
        return False

    actual_rows = actual.get("rows", [])
    expected_rows = expected.get("rows", [])

    return normalize_rows(actual_rows) == normalize_rows(expected_rows)


def evaluate_exposure(question, actual_result=None):

    portfolio_name = (
        question["ground_truth"]["parameters"]["portfolio_name"]
    )

    expected = execute_ground_truth_sql("""
        SELECT
            sec.sector_name,
            ROUND(SUM(h.current_weight)*100, 2)
                AS exposure_percentage
        FROM holdings h
        JOIN securities s
            ON h.security_id = s.security_id
        JOIN sectors sec
            ON s.sector_id = sec.sector_id
        JOIN portfolios p
            ON h.portfolio_id = p.portfolio_id
        WHERE p.portfolio_name = '{}'
          AND s.asset_type = 'Stock'
        GROUP BY sec.sector_name
        ORDER BY sec.sector_name
    """.format(portfolio_name.replace("'", "''")))

    if actual_result is None:
        actual_result = calculate_sector_exposure(portfolio_name)

    expected_exposures = {
        row["sector_name"]: float(row["exposure_percentage"])
        for row in expected.get("rows", [])
    }

    actual_exposures = {
        row["sector_name"]: float(row["exposure_percentage"])
        for row in actual_result.get("sector_exposures", [])
    }

    passed = (
        actual_result.get("success", False)
        and expected.get("success", False)
        and actual_result.get("portfolio_name") == portfolio_name
        and set(actual_exposures) == set(expected_exposures)
        and all(
            abs(actual_exposures[key] - expected_exposures[key]) < 0.01
            for key in expected_exposures
        )
    )

    return {
        "success": actual_result.get("success", False),
        "passed": passed,
        "actual": actual_result,
        "expected": expected_exposures
    }


def evaluate_sql(question, client, model_name, schema_description):

    from sql_tool import generate_sql

    generated_sql = generate_sql(
        question["question"],
        client,
        model_name,
        schema_description
    )

    actual = run_sql_query(generated_sql)

    expected = execute_ground_truth_sql(
        question["ground_truth"]["sql_query"]
    )

    passed = compare_results(actual, expected)

    return {
        "success": actual.get("success", False),
        "passed": passed,
        "generated_sql": generated_sql,
        "actual": actual,
        "expected": expected
    }


def run_evaluation(client, model_name, schema_description):

    questions = load_ground_truth()

    results = []

    for question in questions:

        print(
            f"Evaluating Q{question['id']}: "
            f"{question['question']}"
        )

        try:

            if question["type"] == "text2sql":

                evaluation = evaluate_sql(
                    question,
                    client,
                    model_name,
                    schema_description
                )

                passed = evaluation["passed"]

            elif question["type"] == "exposure_calculator":

                evaluation = evaluate_exposure(question)

                # Exposure reference defines the tool and input,
                # not a fixed numerical result.
                passed = evaluation["passed"]

            else:

                evaluation = {
                    "success": False,
                    "error": "Unsupported question type."
                }

                passed = False

            results.append({
                "id": question["id"],
                "question": question["question"],
                "type": question["type"],
                "difficulty": question["difficulty"],
                "passed": passed,
                "evaluation": evaluation
            })

            print("Result:", "PASS" if passed else "FAIL")
            print("-" * 60)

        except Exception as e:

            results.append({
                "id": question["id"],
                "question": question["question"],
                "type": question["type"],
                "difficulty": question["difficulty"],
                "passed": False,
                "error": str(e)
            })

            print("ERROR:", str(e))
            print("-" * 60)

    return results



def evaluation_summary(results):

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    accuracy = round(
        (passed / total) * 100, 2
    ) if total else 0

    print("\n========== EVALUATION SUMMARY ==========")
    print("Total Questions:", total)
    print("Passed:", passed)
    print("Failed:", failed)
    print("Strict Accuracy:", str(accuracy) + "%")

    print("\n========== DIFFICULTY-WISE RESULTS ==========")

    for difficulty in ["easy", "medium", "hard"]:

        group = [
            r for r in results
            if r["difficulty"].lower() == difficulty
        ]

        if group:
            group_passed = sum(1 for r in group if r["passed"])
            group_accuracy = round(
                group_passed / len(group) * 100, 2
            )

            print(
                difficulty.upper(),
                f": {group_passed}/{len(group)} ({group_accuracy}%)"
            )

    print("\n========== TYPE-WISE RESULTS ==========")

    for question_type in ["text2sql", "exposure_calculator"]:

        group = [
            r for r in results
            if r["type"] == question_type
        ]

        if group:
            type_passed = sum(1 for r in group if r["passed"])
            type_accuracy = round(
                type_passed / len(group) * 100, 2
            )

            print(
                question_type.upper(),
                f": {type_passed}/{len(group)} ({type_accuracy}%)"
            )

    print("\n========== FAILED QUESTIONS ==========")

    failed_questions = [
        r for r in results if not r["passed"]
    ]

    if failed_questions:
        for question in failed_questions:
            print(f"Q{question['id']}: {question['question']}")
    else:
        print("No failed questions.")

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "strict_accuracy": accuracy
    }
