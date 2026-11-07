
import os
import json
import argparse

from google import genai

from agent import ask_portfolio_agent
from evaluator import (
    load_ground_truth,
    execute_ground_truth_sql,
    evaluate_exposure,
    compare_results,
    evaluation_summary
)
from main import get_schema_description


def is_api_error(error):

    error_message = str(error).upper()

    api_indicators = [
        "RESOURCE_EXHAUSTED",
        "UNAVAILABLE",
        "INTERNAL",
        "DEADLINE_EXCEEDED",
        "API KEY",
        "API_ERROR",
        "429",
        "500",
        "502",
        "503",
        "504"
    ]

    return any(
        indicator in error_message
        for indicator in api_indicators
    )


def main():

    parser = argparse.ArgumentParser(
        description="PL Capital Agent Ground Truth Evaluator"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Evaluate only the first N questions"
    )

    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")

    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not set.")
        return

    client = genai.Client(api_key=api_key)

    model_name = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.8-flash"
    )

    schema_description = get_schema_description()

    questions = load_ground_truth()

    if args.limit is not None:
        questions = questions[:args.limit]

    results = []

    print("\nPL CAPITAL - AGENT EVALUATION")
    print("=" * 55)
    print("Model:", model_name)
    print("Questions:", len(questions))

    for question in questions:

        qid = question["id"]
        qtext = question["question"]

        expected_tool = (
            "run_sql_query"
            if question["type"] == "text2sql"
            else "calculate_sector_exposure"
        )

        print(f"\nQ{qid}: {qtext}")

        try:

            agent_result = ask_portfolio_agent(
                qtext,
                client,
                model_name,
                schema_description,
                return_details=True
            )

            answer = agent_result.get("answer", "")
            tool_calls = agent_result.get("tool_calls", [])

            # Strict tool selection:
            # Exactly one call, and it must be the expected tool.
            tool_selection_passed = (
                len(tool_calls) == 1
                and tool_calls[0].get("name") == expected_tool
            )

            selected_call = (
                tool_calls[0]
                if tool_selection_passed
                else None
            )

            if selected_call is None:

                passed = False

                evaluation = {
                    "error": "Incorrect tool selection.",
                    "expected_tool": expected_tool,
                    "actual_tool_calls": tool_calls
                }

            elif question["type"] == "text2sql":

                actual = selected_call.get("result", {})

                generated_sql = selected_call.get(
                    "generated_sql"
                )

                expected = execute_ground_truth_sql(
                    question["ground_truth"]["sql_query"]
                )

                passed = compare_results(actual, expected)

                evaluation = {
                    "generated_sql": generated_sql,
                    "actual": actual,
                    "expected": expected
                }

            elif question["type"] == "exposure_calculator":

                actual = selected_call.get("result", {})

                evaluation = evaluate_exposure(
                    question,
                    actual_result=actual
                )

                passed = evaluation["passed"]

            else:

                passed = False

                evaluation = {
                    "error": "Unsupported question type."
                }

            status = "PASS" if passed else "FAIL"

            results.append({
                "id": qid,
                "question": qtext,
                "type": question["type"],
                "difficulty": question["difficulty"],
                "status": status,
                "passed": passed,
                "tool_selection_passed": tool_selection_passed,
                "answer": answer,
                "tool_calls": tool_calls,
                "evaluation": evaluation
            })

            print(
                "Tool Selection:",
                "PASS" if tool_selection_passed else "FAIL"
            )

            print("Result Evaluation:", status)

        except Exception as error:

            status = (
                "API_ERROR"
                if is_api_error(error)
                else "ERROR"
            )

            results.append({
                "id": qid,
                "question": qtext,
                "type": question["type"],
                "difficulty": question["difficulty"],
                "status": status,
                "passed": False,
                "tool_selection_passed": False,
                "error": str(error)
            })

            print("Status:", status)
            print("Details:", str(error))

        print("-" * 55)

    # Separate successfully evaluated questions from errors.
    evaluated_results = [
        result for result in results
        if result["status"] in ["PASS", "FAIL"]
    ]

    api_errors = [
        result for result in results
        if result["status"] == "API_ERROR"
    ]

    execution_errors = [
        result for result in results
        if result["status"] == "ERROR"
    ]

    # Generate functional evaluation summary.
    summary = evaluation_summary(evaluated_results)

    total_attempted = len(results)
    total_evaluated = len(evaluated_results)

    tool_correct = sum(
        1 for result in evaluated_results
        if result.get("tool_selection_passed", False)
    )

    tool_accuracy = (
        round(tool_correct / total_evaluated * 100, 2)
        if total_evaluated else None
    )

    summary["total_attempted"] = total_attempted
    summary["api_errors"] = len(api_errors)
    summary["execution_errors"] = len(execution_errors)
    summary["tool_selection_accuracy"] = tool_accuracy

    print("\n========== EXECUTION STATUS ==========")
    print("Questions Attempted:", total_attempted)
    print("Questions Evaluated:", total_evaluated)
    print("API Errors:", len(api_errors))
    print("Execution Errors:", len(execution_errors))

    print("\n========== TOOL SELECTION SUMMARY ==========")

    print(
        "Tool Selection Accuracy:",
        f"{tool_accuracy}%" if tool_accuracy is not None else "N/A"
    )

    # Save complete results, including API errors.
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "evaluation_results.json"
    )

    with open(output_path, "w") as file:

        json.dump(
            {
                "summary": summary,
                "results": results
            },
            file,
            indent=4,
            default=str
        )

    print("\nDetailed results saved to:", output_path)


if __name__ == "__main__":
    main()
