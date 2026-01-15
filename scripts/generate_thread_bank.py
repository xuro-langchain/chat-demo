#!/usr/bin/env python3
"""Generate a bank of thread personas for multi-turn conversation testing.

This script creates a thread bank with personas that guide simulated users
through realistic multi-turn conversations with the KB agent.

Usage:
    # Generate default thread bank (20 threads)
    python scripts/generate_thread_bank.py

    # Generate custom size bank
    python scripts/generate_thread_bank.py --num-threads 30
"""

import argparse
import csv
import random
import sys
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langsmith import tracing_context
from src.agent.config import DEFAULT_MODEL

# Load environment variables
load_dotenv()

# Initialize LLM for persona generation
persona_generator = init_chat_model(DEFAULT_MODEL.id, temperature=0.8)


# In-scope thread scenarios (based on KB topics)
IN_SCOPE_SCENARIOS = [
    {
        "category": "account_closure",
        "initial_intent": "wants to close their credit card account",
        "follow_up_topics": [
            "whether they need to pay off balance first",
            "if there are any closure fees",
            "how long the process takes",
            "what happens to rewards points",
            "confirmation that account is closed"
        ]
    },
    {
        "category": "balance_transfer",
        "initial_intent": "wants to transfer balance from another card",
        "follow_up_topics": [
            "what the balance transfer fee is",
            "if there's a promotional APR",
            "how long the transfer takes",
            "what the credit limit on transfers is",
            "how to initiate the transfer"
        ]
    },
    {
        "category": "disputed_charge",
        "initial_intent": "found an unauthorized charge on their statement",
        "follow_up_topics": [
            "how to dispute the charge",
            "if they'll get money back immediately",
            "how long the dispute process takes",
            "whether they need to freeze their card",
            "what documentation they need"
        ]
    },
    {
        "category": "lost_stolen_card",
        "initial_intent": "lost their credit card or had it stolen",
        "follow_up_topics": [
            "how to report the card as lost/stolen",
            "if they're liable for fraudulent charges",
            "how quickly they can get a replacement",
            "whether they need to update autopay accounts",
            "how to track the replacement card"
        ]
    },
    {
        "category": "payment_methods",
        "initial_intent": "wants to pay their credit card bill",
        "follow_up_topics": [
            "what payment methods are accepted",
            "how long payments take to process",
            "if they can set up autopay",
            "what happens if they miss the due date",
            "how to change payment due date"
        ]
    },
    {
        "category": "credit_limit",
        "initial_intent": "wants to increase their credit limit",
        "follow_up_topics": [
            "how to request a credit limit increase",
            "what factors affect approval",
            "if it requires a hard credit pull",
            "how long it takes to process",
            "whether increases are automatic over time"
        ]
    },
    {
        "category": "rewards_redemption",
        "initial_intent": "wants to redeem their rewards points",
        "follow_up_topics": [
            "how to check rewards balance",
            "what redemption options are available",
            "if points expire",
            "minimum redemption amounts",
            "how to maximize point value"
        ]
    },
    {
        "category": "late_payment",
        "initial_intent": "missed their payment due date",
        "follow_up_topics": [
            "what late fees they'll be charged",
            "if they can get fees waived",
            "how it affects their credit score",
            "how to avoid late payments in future",
            "whether they can still make a payment"
        ]
    },
    {
        "category": "card_activation",
        "initial_intent": "received new card and needs to activate it",
        "follow_up_topics": [
            "how to activate the card",
            "what to do if activation isn't working",
            "whether old card still works during activation",
            "if PIN needs to be set",
            "when they can start using the card"
        ]
    },
    {
        "category": "statement_access",
        "initial_intent": "can't find or access their statement",
        "follow_up_topics": [
            "how to access statements online",
            "how to get paper statements",
            "what to do if statement is missing",
            "how far back statements are available",
            "how to download statements for records"
        ]
    },
]


# Out-of-scope thread scenarios (not in KB)
OUT_OF_SCOPE_SCENARIOS = [
    {
        "category": "cryptocurrency",
        "initial_intent": "wants to use credit card to buy cryptocurrency",
        "follow_up_topics": [
            "if they can stake crypto using the card",
            "what fees apply to crypto transactions",
            "if crypto purchases earn rewards",
            "whether there are spending limits",
            "how to report crypto for taxes"
        ]
    },
    {
        "category": "investment_account",
        "initial_intent": "wants to open a brokerage investment account",
        "follow_up_topics": [
            "what investment products are offered",
            "what the account minimums are",
            "whether they offer robo-advisor services",
            "what trading fees apply",
            "how to transfer existing investments"
        ]
    },
    {
        "category": "mortgage",
        "initial_intent": "interested in applying for a home mortgage",
        "follow_up_topics": [
            "what mortgage rates are available",
            "what down payment is required",
            "what the pre-approval process is",
            "what closing costs to expect",
            "how long approval takes"
        ]
    },
    {
        "category": "business_banking",
        "initial_intent": "wants to open a business checking account",
        "follow_up_topics": [
            "what documents are needed",
            "what fees apply to business accounts",
            "whether they can integrate with QuickBooks",
            "if they offer merchant services",
            "what the account minimum is"
        ]
    },
    {
        "category": "savings_account",
        "initial_intent": "wants to open a high-yield savings account",
        "follow_up_topics": [
            "what the current interest rate is",
            "what the minimum balance requirement is",
            "how many withdrawals are allowed per month",
            "whether the rate is variable",
            "how interest is compounded"
        ]
    },
    {
        "category": "wire_transfer",
        "initial_intent": "needs to send a wire transfer internationally",
        "follow_up_topics": [
            "what fees apply to international wires",
            "how long the transfer takes",
            "what information they need from recipient",
            "if there are daily limits",
            "whether they can cancel after sending"
        ]
    },
    {
        "category": "student_loans",
        "initial_intent": "wants to refinance their student loans",
        "follow_up_topics": [
            "what interest rates are available",
            "if they can refinance federal loans",
            "what the eligibility requirements are",
            "what repayment terms are offered",
            "how refinancing affects loan forgiveness"
        ]
    },
    {
        "category": "auto_loan",
        "initial_intent": "wants to get pre-approved for a car loan",
        "follow_up_topics": [
            "what the current APR is",
            "what the maximum loan term is",
            "if they finance used cars",
            "what the pre-approval process involves",
            "whether there are early payoff penalties"
        ]
    },
    {
        "category": "mobile_app",
        "initial_intent": "having trouble with the mobile banking app",
        "follow_up_topics": [
            "how to reset their app password",
            "what features are available in the app",
            "if they can deposit checks through the app",
            "how to enable biometric login",
            "whether the app works internationally"
        ]
    },
    {
        "category": "debit_card",
        "initial_intent": "wants to activate a new debit card",
        "follow_up_topics": [
            "how to activate the debit card",
            "what the daily withdrawal limit is",
            "whether it works internationally",
            "how to report lost debit card",
            "what ATM fees apply"
        ]
    },
]


def generate_persona(scenario: Dict, in_scope: bool) -> str:
    """Generate a detailed persona for a thread scenario."""
    prompt = f"""Generate a detailed persona for a simulated customer who will have a multi-turn conversation with a credit card support agent.

Scenario: Customer {scenario['initial_intent']}

Requirements:
- Create a realistic customer profile (name, situation, tone)
- Include specific details that make follow-up questions natural
- Mention 2-3 specific follow-up concerns they should ask about from these topics: {', '.join(scenario['follow_up_topics'])}
- Make the persona conversational and realistic (not overly formal)
- Keep it 3-4 sentences

{"IMPORTANT: This is an IN-SCOPE scenario - the agent's KB should be able to help with this. The persona should expect helpful answers." if in_scope else "IMPORTANT: This is an OUT-OF-SCOPE scenario - the agent's KB does NOT cover this topic. The persona should be understanding if the agent can't help."}

Example persona format:
"Sarah is a busy professional who recently noticed an unauthorized $250 charge from an online retailer she's never used. She's concerned about identity theft and wants to act quickly. She needs to understand the dispute process, whether she's liable for the charge, and how long it will take to get her money back. She's moderately tech-savvy and prefers clear, step-by-step instructions."

Generate ONE persona (do not include the label, just the persona text):"""

    # Trace persona generation to separate project
    with tracing_context(project_name="synthetic-generation"):
        response = persona_generator.invoke([{"role": "user", "content": prompt}])
    return response.content.strip()


def generate_thread_bank(num_threads: int = 20, in_scope_ratio: float = 0.6) -> List[Dict[str, str]]:
    """Generate a bank of thread scenarios with personas.

    Args:
        num_threads: Total number of threads to generate
        in_scope_ratio: Ratio of in-scope threads

    Returns:
        List of thread scenario dictionaries with metadata
    """
    num_in_scope = int(num_threads * in_scope_ratio)
    num_out_of_scope = num_threads - num_in_scope

    thread_bank = []

    # Generate in-scope threads
    print(f"\n📝 Generating {num_in_scope} in-scope thread personas...")
    sys.stdout.flush()
    for i in range(num_in_scope):
        scenario = random.choice(IN_SCOPE_SCENARIOS)
        persona = generate_persona(scenario, in_scope=True)

        thread_bank.append({
            "id": f"thread_{i+1:03d}",
            "persona": persona,
            "initial_intent": scenario["initial_intent"],
            "follow_up_topics": "|".join(scenario["follow_up_topics"]),
            "in_scope": "yes",
            "category": scenario["category"]
        })

        if (i + 1) % 5 == 0 or (i + 1) == num_in_scope:
            print(f"  ✓ Generated {i + 1}/{num_in_scope} in-scope personas")
            sys.stdout.flush()

    # Generate out-of-scope threads
    print(f"\n📝 Generating {num_out_of_scope} out-of-scope thread personas...")
    sys.stdout.flush()
    for i in range(num_out_of_scope):
        scenario = random.choice(OUT_OF_SCOPE_SCENARIOS)
        persona = generate_persona(scenario, in_scope=False)

        thread_bank.append({
            "id": f"thread_{num_in_scope + i + 1:03d}",
            "persona": persona,
            "initial_intent": scenario["initial_intent"],
            "follow_up_topics": "|".join(scenario["follow_up_topics"]),
            "in_scope": "no",
            "category": scenario["category"]
        })

        if (i + 1) % 5 == 0 or (i + 1) == num_out_of_scope:
            print(f"  ✓ Generated {i + 1}/{num_out_of_scope} out-of-scope personas")
            sys.stdout.flush()

    # Shuffle to mix in-scope and out-of-scope
    random.shuffle(thread_bank)

    # Reassign IDs after shuffling
    for i, thread in enumerate(thread_bank):
        thread["id"] = f"thread_{i+1:03d}"

    return thread_bank


def save_thread_bank(thread_bank: List[Dict[str, str]], output_path: Path):
    """Save thread bank to CSV file."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ["id", "persona", "initial_intent", "follow_up_topics", "in_scope", "category"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()
        for thread in thread_bank:
            writer.writerow(thread)


def print_summary(thread_bank: List[Dict[str, str]]):
    """Print summary of generated thread bank."""
    print("\n" + "=" * 80)
    print("THREAD BANK SUMMARY")
    print("=" * 80)

    total = len(thread_bank)
    in_scope = sum(1 for t in thread_bank if t["in_scope"] == "yes")
    out_of_scope = total - in_scope

    print(f"Total threads: {total}")
    print(f"  In-scope (can answer): {in_scope} ({in_scope/total*100:.1f}%)")
    print(f"  Out-of-scope (cannot answer): {out_of_scope} ({out_of_scope/total*100:.1f}%)")

    # Category breakdown
    categories = {}
    for t in thread_bank:
        cat = t.get("category", "unknown")
        scope = "in_scope" if t["in_scope"] == "yes" else "out_of_scope"
        if scope not in categories:
            categories[scope] = {}
        categories[scope][cat] = categories[scope].get(cat, 0) + 1

    print("\nCategories by scope:")
    if "in_scope" in categories:
        print(f"\n  In Scope ({sum(categories['in_scope'].values())} threads):")
        for cat, count in sorted(categories["in_scope"].items()):
            print(f"    - {cat}: {count}")

    if "out_of_scope" in categories:
        print(f"\n  Out Of Scope ({sum(categories['out_of_scope'].values())} threads):")
        for cat, count in sorted(categories["out_of_scope"].items()):
            print(f"    - {cat}: {count}")

    # Show sample
    print("\n" + "=" * 80)
    print("SAMPLE THREAD PERSONAS (showing 3)")
    print("=" * 80)

    for thread in thread_bank[:3]:
        scope_label = "IN-SCOPE" if thread["in_scope"] == "yes" else "OUT-OF-SCOPE"
        print(f"\n[{thread['id']}] {scope_label} ({thread['category']})")
        print(f"  Intent: {thread['initial_intent']}")
        print(f"  Persona: {thread['persona']}")
        print(f"  Follow-ups: {thread['follow_up_topics'][:80]}...")

    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(
        description="Generate thread bank with personas for multi-turn conversations",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--num-threads",
        type=int,
        default=20,
        help="Number of thread personas to generate (default: 20)"
    )
    parser.add_argument(
        "--in-scope-ratio",
        type=float,
        default=0.6,
        help="Ratio of in-scope threads (default: 0.6)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/thread_bank.csv",
        help="Output path for thread bank (default: data/thread_bank.csv)"
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview without saving"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.num_threads < 1:
        parser.error("num-threads must be at least 1")
    if not 0.0 <= args.in_scope_ratio <= 1.0:
        parser.error("in-scope-ratio must be between 0.0 and 1.0")

    print("=" * 80)
    print("THREAD BANK GENERATOR")
    print("=" * 80)
    print(f"Generating {args.num_threads} thread personas")
    print(f"  In-scope: {args.in_scope_ratio:.0%}")
    print(f"  Out-of-scope: {1-args.in_scope_ratio:.0%}")
    if args.preview:
        print("Mode: PREVIEW (will not save)")
    print("=" * 80)
    sys.stdout.flush()

    # Generate thread bank
    thread_bank = generate_thread_bank(args.num_threads, args.in_scope_ratio)

    # Print summary
    print_summary(thread_bank)

    # Save if not preview
    if not args.preview:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"\n💾 Saving thread bank to {output_path}...")
        sys.stdout.flush()
        save_thread_bank(thread_bank, output_path)
        print(f"✓ Saved {len(thread_bank)} thread personas")
        print(f"\n✅ Thread bank ready at: {output_path}")
        print(f"   Use with: python scripts/generate_threads.py")
        sys.stdout.flush()
    else:
        print("\n⚠️  Preview mode - thread bank not saved")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
