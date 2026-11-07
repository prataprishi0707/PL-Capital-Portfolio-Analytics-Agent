# AI Engineering Take-Home: Portfolio Analytics Agent

## Overview

Build a simple AI agent that can answer questions about portfolio data. The agent should be able to understand natural language questions and either query a database or calculate basic portfolio metrics.

## What You'll Build

1. **SQL Query Tool**: Convert questions like "How many portfolios do we have?" into SQL queries.
2. **Exposure Calculator Tool**: Given a portfolio, calculate sector exposures. You will need to combine weights of each holding in a portfolio with the respective sector of that security, so that given a portfolio your calculator can output percentage exposures to each sector. Ignore bond holdings for this calculation, only consider the equities in the portfolio.
3. **Portfolio Agent**: A command-line agent that can choose one of the above tools to answer a user query.
4. **Agent Evaluator**: A command-line script that uses the given ground truth dataset, runs each question through the agent, and confirms whether the generated response matches the expected true answer.

## Provided Materials
✅ **Sample data** - CSV files with portfolio related information under `data/`  
✅ **Database schema** - See `database_schema.sql`  
✅ **Suggested libraries** - see `requirements.txt`   
✅ **Ground Truth Dataset** - see `ground_truth_dataset.json` 

## Getting Started

### Step 1: Environment Setup
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Get API key from Google AI Studio (https://ai.google.dev/gemini-api/docs)

# 3. Create a script to load your in-memory DB with the provided schema & data
```

### Step 2: Understand the Data
- Explore the CSV files in the `data/` folder
- Look at `database_schema.sql` to understand table relationships
- Run a few test queries on the database
- Understand the evaluation Q&A in the `ground_truth_dataset.json` file

### Step 3: Build Your Agent

**Start Simple:**
```python
# Basic structure - build on this
class PortfolioAgent:
    def __init__(self):
        self.db_connection = sqlite3.connect('portfolio_database.db')
    
    def answer_question(self, question):
        # Your logic here
        pass
```

**Key Implementation Tips:**
- Start with hardcoded SQL for a few questions to test your setup
- Add Gemini API integration once basic structure works
- Focus on getting a few questions working well before expanding
- Test frequently with the evaluation questions

### Step 4: Evaluation
Create a simple script to test your agent against the ground truth questions.

## Technical Hints

### Database Connection
```python
import sqlite3
db_path = 'portfolio_database.db'
conn = sqlite3.connect(db_path)
```

### Gemini API Usage
```python
import google.generativeai as genai
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')
```

## Common Pitfalls to Avoid

1. **Don't overthink the architecture** - Start simple and add complexity gradually
2. **Test early and often** - Verify each piece works before moving on
3. **Focus on accuracy first** - Get basic functionality working before optimizing
4. **Handle errors gracefully** - Add try/catch blocks around database operations
5. **Read the data first** - Understand the portfolio data structure before coding

## Optional Enhancements 

- Use parameterized queries to prevent SQL injection (SQL Safety)
- Validate queries before execution (SQL Safety)
- Handle database errors gracefully (SQL Safety)
- Add logging to track what your agent is doing
- Add basic input validation and error messages
- Implement caching for repeated queries
- Provide a graphical interface via Streamlit
- Leverage RAG or GraphRAG to find the right metadata related to the user question to be used in the context.
- Convert the agent to a production ready REST API
- Support concurrent query handling from multiple users
- Improve evaluation to favor queries that are more performant (e.g. ones that have lower logical i/o)
- Handle and evaluate hybrid questions that require both tools to be used together

## Deliverables

1. **Working agent** that can answer questions via command line
2. **Evaluation script** that tests against the ground truth questions
3. **Brief documentation** explaining how to run your solution (can include design diagrams)
4. **Clean code** with basic error handling


Don't worry about perfect accuracy - focus on building something that works and shows good engineering practices!

## 10. Evaluation and Testing

The project includes:
- A ground-truth question dataset.
- An evaluation module.
- A command-line evaluation runner.
- An automated backend regression test suite.
- SQL read-only validation and safety checks.
- Dashboard syntax and runtime checks.

### Verified Development Checks

| Check | Result |
|---|---|
| SQL Query Tool smoke test | Passed |
| Exposure Calculator smoke test | Passed |
| Portfolio Health smoke test | Passed |
| Portfolio Comparison smoke test | Passed |
| Risk Analyzer smoke test | Passed |
| Automated backend regression tests | 18/18 passed |
| SQL write-operation rejection tests | Passed |
| Multiple-statement rejection test | Passed |
| Database integrity after SQL safety tests | Passed |
| Agent tool registration | Five tools registered |
| Dashboard Python syntax | 5/5 files passed |
| Streamlit health endpoint | HTTP 200 |
| Dashboard browser review | All five pages checked |

### SQL Safety Verification

The SQL execution layer was tested against:
- INSERT, UPDATE and DELETE statements.
- DROP TABLE, ALTER TABLE and CREATE TABLE statements.
- Write-style PRAGMA operations.
- Multiple SQL statements in a single request.
- Invalid table references.

All tested write attempts and multiple-statement requests were rejected.

A subsequent database integrity check confirmed:
- 13 portfolio records remained.
- All nine original database tables remained present.
- PRAGMA user_version remained unchanged at 0.

### Evaluation Status

The following development and testing checks have been completed:

- Automated backend regression tests: **18/18 passed**.
- Result comparison unit tests: **5/5 passed**.
- Exposure ground-truth tests: **2/2 passed**.
- Offline tool-selection logic tests: **5/5 passed**.
- API-error classification tests: **6/6 passed**.
- One successful end-to-end Gemini SQL tool execution, correctly returning **13 portfolios**.

**Live evaluation limitation:**

The complete 10-question ground-truth evaluation has not yet been verified. Subsequent Gemini API requests encountered HTTP 503 service-unavailability errors before tool selection. Therefore, no overall live agent accuracy percentage is claimed. Live exposure-tool selection also remains unverified.

API availability limitations do not invalidate the independently tested database tools, SQL safety checks, or offline evaluation logic.

