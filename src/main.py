
import os
import argparse
import sqlite3

from google import genai
from agent import ask_portfolio_agent


def get_schema_description():

    db_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "portfolio_database.db"
    )

    conn = sqlite3.connect(
        f"file:{db_path}?mode=ro",
        uri=True
    )

    try:
        cursor = conn.cursor()

        tables = cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

        schema = []

        for (table_name,) in tables:

            columns = cursor.execute(
                f"PRAGMA table_info('{table_name}')"
            ).fetchall()

            column_names = [
                column[1] for column in columns
            ]

            schema.append(
                f"Table: {table_name}\n"
                f"Columns: {', '.join(column_names)}"
            )

        return "\n\n".join(schema)

    finally:
        conn.close()


def main():

    parser = argparse.ArgumentParser(
        description="PL Capital AI Portfolio Analytics Agent"
    )

    parser.add_argument(
        "--question",
        type=str,
        help="Ask a portfolio-related question"
    )

    args = parser.parse_args()

    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not set.")
        return

    try:
        client = genai.Client(api_key=api_key)

        # Override via GEMINI_MODEL env var.
        # Default: gemini-2.5-flash — verified present in google-genai SDK 1.64.0 source.
        # Fallback options (older but stable): gemini-1.5-flash, gemini-2.0-flash-lite.
        model_name = os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash"
        )

        schema_description = get_schema_description()

    except Exception as error:
        print("Initialization Error:", error)
        return

    print("\nPL Capital Portfolio Analytics Agent")
    print("------------------------------------")

    if args.question:
        questions = [args.question]

    else:
        print("Type 'exit' to quit.\n")
        questions = None

    def process_question(question):

        print("\nProcessing your question...")

        answer = ask_portfolio_agent(
            question,
            client,
            model_name,
            schema_description
        )

        print("\nAgent:")
        print(answer)
        print("-" * 50)

    if questions:

        for question in questions:

            try:
                process_question(question)

            except Exception as error:
                print("Error:", error)

    else:

        while True:

            question = input("\nYou: ").strip()

            if question.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            if not question:
                continue

            try:
                process_question(question)

            except Exception as error:
                print("Error:", error)


if __name__ == "__main__":
    main()
