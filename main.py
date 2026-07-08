"""CLI entrypoint for the PC configuration agent."""

from __future__ import annotations

import argparse
import json

from src.agent.loop import PCConfigAgent
from src.evaluation.runner import run_evaluation, run_recent_runs_report


def main() -> None:
    parser = argparse.ArgumentParser(description="GenAI PC Configuration Agent")
    parser.add_argument("--message", type=str, help="User requirement message")
    parser.add_argument("--feedback", type=str, help="Optional user feedback to revise build")
    parser.add_argument("--evaluate", action="store_true", help="Run built-in evaluation scenarios")
    parser.add_argument(
        "--generate-report",
        action="store_true",
        help="Generate/update AGENT_RUN_REPORT.md from recent traces",
    )
    parser.add_argument(
        "--report-limit",
        type=int,
        default=5,
        help="Number of recent traces to include in the report (default: 5)",
    )
    args = parser.parse_args()

    if args.generate_report:
        if args.message:
            agent = PCConfigAgent()
            trace = agent.run(args.message, prior_feedback=args.feedback)
            
            if trace.final_build:
                print("\n" + "="*60)
                print("Build Result:")
                print("="*60)
                print(trace.final_build.model_dump_json(indent=2))
            else:
                print(json.dumps({"errors": trace.errors}, indent=2))
            
            print(f"\nTrace saved for session {trace.session_id}")
        
        print("\n" + "="*60)
        print("Updating AGENT_RUN_REPORT.md with recent runs...")
        print("="*60)
        run_recent_runs_report(limit=args.report_limit)
        return

    if args.evaluate:
        results = run_evaluation()
        print(json.dumps(results, indent=2))
        passed = sum(1 for item in results if item["passed"])
        print(f"\nEvaluation: {passed}/{len(results)} scenarios passed")
        return

    if not args.message:
        parser.error("--message is required unless --evaluate or --generate-report is used")

    agent = PCConfigAgent()
    trace = agent.run(args.message, prior_feedback=args.feedback)

    if trace.final_build:
        print(trace.final_build.model_dump_json(indent=2))
    else:
        print(json.dumps({"errors": trace.errors}, indent=2))

    print(f"\nTrace saved for session {trace.session_id}")


if __name__ == "__main__":
    main()
