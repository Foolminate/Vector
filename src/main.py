import argparse
import asyncio
from datetime import datetime

# Local imports
from .database import DatabaseManager
from .config_loader import load_config
from .collector import SeekCollector
from .sorter import TriageSorter

def main():
    parser = argparse.ArgumentParser(description="Project Vector: Automated Job Discovery Engine")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Setup command
    subparsers.add_parser("setup", help="Initialize configuration and database")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape jobs from Seek.co.nz")
    scrape_parser.add_argument("--limit", type=int, help="Limit the number of jobs to scrape")
    
    # Triage command
    subparsers.add_parser("triage", help="Run AI triage on new jobs")
    
    # Review command
    subparsers.add_parser("review", help="Review edge-case roles")
    
    # Digest command
    subparsers.add_parser("digest", help="Generate daily Markdown digest")

    args = parser.parse_args()

    db = DatabaseManager()

    if args.command == "setup":
        print("Initializing Project Vector...")
        db.log_action("setup", "System initialization")
        config = load_config()
        if config:
            print("Configuration loaded successfully.")
        else:
            print("Warning: SEARCH_CONFIG.yaml not found.")
        print("Database initialized at vector.db")

    elif args.command == "scrape":
        print(f"Starting Seek scraper (limit={args.limit})...")
        config = load_config()
        collector = SeekCollector(db, config)
        asyncio.run(collector.scrape(limit=args.limit))
        db.log_action("scrape", f"Completed run (limit={args.limit})")

    elif args.command == "triage":
        print("Starting AI triage...")
        sorter = TriageSorter(db)
        sorter.triage_all_new()
        db.log_action("triage", "Completed triage run")

    elif args.command == "review":
        from .review_tui import ReviewApp
        app = ReviewApp(db)
        app.run()

    elif args.command == "digest":
        print("Starting evaluation and digest generation...")
        from .evaluator import JobEvaluator
        evaluator = JobEvaluator(db)
        evaluator.evaluate_all_new()
        report_path = evaluator.generate_digest()
        if report_path:
            print(f"Digest generated successfully: {report_path}")
        else:
            print("No jobs found to include in digest.")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
