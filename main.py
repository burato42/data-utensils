import argparse
import sys

from loguru import logger

from src import reader, cleaner, transformer, sink


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute SaaS subscription metrics from CSV files."
    )
    parser.add_argument("customers", help="Path to customers.csv")
    parser.add_argument("subscriptions", help="Path to subscriptions.csv")
    parser.add_argument("output", help="Path to write the JSON report")
    return parser.parse_args()


def main() -> None:
    logger.remove()
    logger.add(sys.stderr, format="{time:HH:mm:ss} | {level} | {message}", level="DEBUG")

    args = _parse_args()

    raw_customers = reader.read_customers(args.customers)
    raw_subscriptions = reader.read_subscriptions(args.subscriptions)

    clean_customers = cleaner.clean_customers(raw_customers)
    valid_ids = set(clean_customers["customer_id"])
    clean_subscriptions = cleaner.clean_subscriptions(raw_subscriptions, valid_ids)

    results = {
        "mrr": transformer.compute_mrr(clean_subscriptions),
        "churn": transformer.compute_churn(clean_subscriptions),
        "cohorts": transformer.compute_cohort_retention(clean_customers, clean_subscriptions),
    }

    sink.write_output(results, args.output)
    logger.info(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
