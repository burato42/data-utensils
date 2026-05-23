# Assignment
## Context
You are building a small data analytics tool for a subscription SaaS product. The business wants a simple way to compute a few key metrics from exported CSV files.

You may use any Python libraries you like (e.g. pandas, pydantic, typer/click, pytest, etc.), as long as the setup remains simple (e.g. pip install -r requirements.txt).

## Input data
You can access two CSV files:

`customers.csv`
- customer_id (string)  
- signup_date (ISO date, e.g. 2024-01-15)  
- country (string, e.g. NL, DE, …)
`subscriptions.csv`
- customer_id (string)  
- start_date (ISO date)  
- end_date (ISO date or empty for active)  
- plan (string, e.g. basic, pro)  
- monthly_price (numeric)
Assume one active subscription per customer at a time, but customers may churn and later re-subscribe.

# Required output
Implement a small tool that, given the two CSV files, produces a JSON report with:

## Monthly MRR (Monthly Recurring Revenue) for each calendar month.
- For each month, sum monthly_price of all subscriptions that are active in that month.
- Monthly churned customers count
- A churn event is when a subscription has an end_date and the customer has no new subscription starting within 30 days after that end_date.
- Signup cohorts with 3-month retention
- Group customers by signup month.
- For each cohort, compute:
    - cohort_size
    - active_after_3_months: number of customers that still have any active subscription 3 months after their signup date.
    - retention_rate_3m= active_after_3_months / cohort_size.

## The tool should:

- Be runnable as a CLI, for example:
`python main.py customers.csv subscriptions.csv output.json`
- Validate inputs and fail with a clear message when required columns are missing or malformed.

- Log or otherwise surface data quality issues (e.g. unknown customer_id in subscriptions).

Non-functional requirements
- Structure and extensibility
- Organize your code so that adding a new metric (e.g. average revenue per user or LTV per cohort) can be done cleanly without turning main.py into a large script.
- Aim for reasonable separation of concerns (e.g. data loading, business logic, and CLI entry point).
Tests
- Include at least a few tests (e.g. pytest) that:
- Cover the churn logic and 3-month retention logic.
- Cover at least one edge case (e.g. subscription ending exactly on boundary dates, re-subscriptions within 30 days, etc.).
- Type hints and documentation
- Use type hints for your main functions.
- Add docstrings or comments where they clarify non-obvious logic.
- Short design note
- Include a short DESIGN.md (max 1 page) explaining:
    - How the code is structured.
    - How you modeled the business rules (MRR, churn, cohorts).
    - How you would add another metric in the future.
    - Any assumptions you made and known trade-offs.

## AI Chat Log
Include a note or file containing the relevant chat logs or prompts from ChatGPT, Codex or any other AI tools used during the assignment.