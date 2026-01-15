#!/usr/bin/env python3
"""Generate synthetic traces by running the KB agent with questions from the question bank.

This script uses a pre-generated question bank (created by generate_question_bank.py)
and runs the questions through the KB agent to generate traces in LangSmith.

Usage:
    # First, generate a question bank
    python scripts/generate_question_bank.py --num-questions 50

    # Then generate traces using the bank
    python scripts/generate_traces.py --num-traces 10

    # Generate traces with specific ratio
    python scripts/generate_traces.py --num-traces 20 --in-scope-ratio 0.7

    # Use different question bank
    python scripts/generate_traces.py --question-bank data/my_bank.csv --num-traces 10
"""

import argparse
import asyncio
import csv
import random
import sys
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

from src.agent.docs_graph import docs_agent

# Load environment variables
load_dotenv()


def load_question_bank(bank_path: Path) -> List[Dict[str, str]]:
    """Load questions from the question bank CSV file."""
    if not bank_path.exists():
        raise FileNotFoundError(
            f"Question bank not found at {bank_path}\n"
            f"Generate one first with: python scripts/generate_question_bank.py"
        )

    questions = []
    with open(bank_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            questions.append({
                "id": row["id"],
                "question": row["question"],
                "in_scope": row["in_scope"] == "yes",
                "category": row["category"],
                "source": row["source"]
            })

    return questions


def select_questions(
    question_bank: List[Dict[str, str]],
    num_traces: int,
    in_scope_ratio: float = None
) -> List[Dict[str, str]]:
    """Select questions from the bank for trace generation.

    Args:
        question_bank: Full question bank
        num_traces: Number of questions to select
        in_scope_ratio: If specified, enforce this ratio of in-scope questions

    Returns:
        Selected questions
    """
    if num_traces > len(question_bank):
        print(f"⚠️  Warning: Requested {num_traces} traces but bank only has {len(question_bank)} questions")
        print(f"   Using all {len(question_bank)} questions from the bank")
        return question_bank

    if in_scope_ratio is None:
        # Random selection without ratio constraint
        return random.sample(question_bank, num_traces)

    # Select with ratio constraint
    in_scope_questions = [q for q in question_bank if q["in_scope"]]
    out_of_scope_questions = [q for q in question_bank if not q["in_scope"]]

    num_in_scope = int(num_traces * in_scope_ratio)
    num_out_of_scope = num_traces - num_in_scope

    # Check if we have enough questions
    if num_in_scope > len(in_scope_questions):
        print(f"⚠️  Warning: Need {num_in_scope} in-scope questions but bank only has {len(in_scope_questions)}")
        num_in_scope = len(in_scope_questions)
        num_out_of_scope = num_traces - num_in_scope

    if num_out_of_scope > len(out_of_scope_questions):
        print(f"⚠️  Warning: Need {num_out_of_scope} out-of-scope questions but bank only has {len(out_of_scope_questions)}")
        num_out_of_scope = len(out_of_scope_questions)
        num_in_scope = num_traces - num_out_of_scope

    # Sample from each pool
    selected = []
    if num_in_scope > 0:
        selected.extend(random.sample(in_scope_questions, num_in_scope))
    if num_out_of_scope > 0:
        selected.extend(random.sample(out_of_scope_questions, num_out_of_scope))

    # Shuffle to mix in-scope and out-of-scope
    random.shuffle(selected)

    return selected


async def run_agent_async(question_data: Dict) -> Dict:
    """Run the agent asynchronously with a question."""
    try:
        question = question_data["question"]
        input_data = {"messages": [{"role": "user", "content": question}]}
        result = await asyncio.to_thread(docs_agent.invoke, input_data)

        # Extract final answer
        messages = result.get("messages", [])
        final_message = None
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and hasattr(msg, "content"):
                if msg.content and not getattr(msg, "tool_calls", []):
                    final_message = msg.content
                    break

        return {
            **question_data,
            "answer": final_message or "No response",
            "success": True
        }
    except Exception as e:
        return {
            **question_data,
            "answer": None,
            "success": False,
            "error": str(e)
        }


async def generate_traces_async(questions: List[Dict[str, str]], max_concurrent: int = 3):
    """Generate traces by running questions through the agent.

    Args:
        questions: List of question dictionaries
        max_concurrent: Maximum number of concurrent agent invocations
    """
    print(f"\n🤖 Running {len(questions)} questions through the agent...")
    print(f"   Max concurrency: {max_concurrent}")
    print("-" * 80)
    sys.stdout.flush()

    results = []

    # Process in batches to control concurrency
    for i in range(0, len(questions), max_concurrent):
        batch = questions[i:i + max_concurrent]
        batch_num = (i // max_concurrent) + 1
        total_batches = (len(questions) + max_concurrent - 1) // max_concurrent

        print(f"\nBatch {batch_num}/{total_batches} ({len(batch)} questions)")
        sys.stdout.flush()

        # Run batch concurrently
        tasks = [run_agent_async(q) for q in batch]
        batch_results = await asyncio.gather(*tasks)

        # Print results
        for j, result in enumerate(batch_results):
            q_num = i + j + 1
            scope = "IN-SCOPE  " if result.get("in_scope") else "OUT-OF-SCOPE"
            status = "✓" if result["success"] else "✗"
            q_id = result.get("id", "unknown")

            print(f"  {status} [{q_num:2d}/{len(questions)}] [{q_id}] {scope}: {result['question'][:50]}...")
            if not result["success"]:
                print(f"      Error: {result.get('error', 'Unknown error')}")
            sys.stdout.flush()

        results.extend(batch_results)

    return results


def print_summary(results: List[Dict]):
    """Print summary statistics of the trace generation."""
    print("\n" + "=" * 80)
    print("TRACE GENERATION SUMMARY")
    print("=" * 80)

    total = len(results)
    successful = sum(1 for r in results if r["success"])
    failed = total - successful

    in_scope = sum(1 for r in results if r.get("in_scope", False))
    out_of_scope = total - in_scope

    print(f"Total traces: {total}")
    print(f"  Successful: {successful} ({successful/total*100:.1f}%)")
    if failed > 0:
        print(f"  Failed: {failed} ({failed/total*100:.1f}%)")
    print()
    print(f"In-scope questions: {in_scope} ({in_scope/total*100:.1f}%)")
    print(f"Out-of-scope questions: {out_of_scope} ({out_of_scope/total*100:.1f}%)")

    # Category breakdown
    categories = {}
    for r in results:
        cat = r.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    print("\nCategories:")
    for cat, count in sorted(categories.items()):
        print(f"  - {cat}: {count}")

    print()
    print("✅ Traces have been generated in LangSmith.")
    print("   View at: https://smith.langchain.com/")
    sys.stdout.flush()


async def main():
    parser = argparse.ArgumentParser(
        description="Generate traces using pre-generated question bank",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 10 traces from the default question bank
  python scripts/generate_traces.py --num-traces 10

  # Generate 20 traces with 70% in-scope questions
  python scripts/generate_traces.py --num-traces 20 --in-scope-ratio 0.7

  # Use custom question bank
  python scripts/generate_traces.py --question-bank data/my_bank.csv --num-traces 10

  # Higher concurrency for faster generation (use with caution)
  python scripts/generate_traces.py --num-traces 50 --max-concurrent 5

Note: Generate the question bank first with generate_question_bank.py
        """
    )

    parser.add_argument(
        "--num-traces",
        type=int,
        default=10,
        help="Number of traces to generate (default: 10)"
    )
    parser.add_argument(
        "--question-bank",
        type=str,
        default="data/question_bank.csv",
        help="Path to question bank CSV (default: data/question_bank.csv)"
    )
    parser.add_argument(
        "--in-scope-ratio",
        type=float,
        default=None,
        help="Ratio of in-scope questions (0.0 to 1.0, default: use bank's ratio)"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=3,
        help="Maximum concurrent agent invocations (default: 3)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (default: None)"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.num_traces < 1:
        parser.error("num-traces must be at least 1")
    if args.in_scope_ratio is not None and not 0.0 <= args.in_scope_ratio <= 1.0:
        parser.error("in-scope-ratio must be between 0.0 and 1.0")
    if args.max_concurrent < 1:
        parser.error("max-concurrent must be at least 1")

    # Set random seed if provided
    if args.seed is not None:
        random.seed(args.seed)
        print(f"🎲 Using random seed: {args.seed}")

    print("=" * 80)
    print("KB AGENT TRACE GENERATOR")
    print("=" * 80)
    sys.stdout.flush()

    # Load question bank
    bank_path = Path(args.question_bank)
    print(f"📚 Loading question bank from: {bank_path}")
    sys.stdout.flush()
    try:
        question_bank = load_question_bank(bank_path)
        print(f"   Loaded {len(question_bank)} questions")

        # Show bank composition
        in_scope_count = sum(1 for q in question_bank if q["in_scope"])
        out_of_scope_count = len(question_bank) - in_scope_count
        print(f"   Bank composition: {in_scope_count} in-scope, {out_of_scope_count} out-of-scope")
        sys.stdout.flush()

    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        sys.stdout.flush()
        return

    # Select questions
    print(f"\n🎯 Selecting {args.num_traces} questions...")
    if args.in_scope_ratio is not None:
        print(f"   Target ratio: {args.in_scope_ratio:.0%} in-scope")

    questions = select_questions(question_bank, args.num_traces, args.in_scope_ratio)

    actual_in_scope = sum(1 for q in questions if q["in_scope"])
    actual_out_of_scope = len(questions) - actual_in_scope
    print(f"   Selected: {actual_in_scope} in-scope, {actual_out_of_scope} out-of-scope")
    print(f"   Max concurrent: {args.max_concurrent}")
    sys.stdout.flush()

    # Run agent to generate traces
    results = await generate_traces_async(questions, args.max_concurrent)

    # Print summary
    print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
