#!/usr/bin/env python3
"""Generate a bank of test questions for trace generation.

This script creates a question bank with:
1. In-scope questions (variations of existing KB questions)
2. Out-of-scope questions (related banking topics not in KB)

The question bank is saved to data/question_bank.csv for reuse.

Usage:
    # Generate default question bank (100 questions, 80% in-scope)
    python scripts/generate_question_bank.py

    # Generate custom size bank
    python scripts/generate_question_bank.py --num-questions 200 --in-scope-ratio 0.7

    # Preview without saving
    python scripts/generate_question_bank.py --num-questions 10 --preview
"""

import argparse
import csv
import random
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langsmith import tracing_context
from src.agent.config import DEFAULT_MODEL

# Load environment variables
load_dotenv()

# Initialize LLM for question generation/rewording
question_generator = init_chat_model(DEFAULT_MODEL.id, temperature=0.7)


# Irrelevant but above threshold - banking topics that match on generic terms but aren't in KB
IRRELEVANT_BUT_MATCHES_TOPICS = [
    {
        "category": "savings_accounts",
        "examples": [
            "What's the interest rate on my savings account?",
            "How do I open a high-yield savings account?",
            "Can I transfer money from savings to checking?",
            "What's the minimum balance for a savings account?",
            "Do you offer money market savings accounts?",
        ]
    },
    {
        "category": "debit_cards",
        "examples": [
            "How do I activate my new debit card?",
            "What's the daily withdrawal limit on my debit card?",
            "Can I use my debit card internationally?",
            "How do I report a lost debit card?",
            "What are the ATM fees for my debit card?",
        ]
    },
    {
        "category": "wire_transfers",
        "examples": [
            "How long does a wire transfer take?",
            "What are the fees for domestic wire transfers?",
            "Can I cancel a wire transfer after it's sent?",
            "What information do I need to receive a wire transfer?",
            "Are there daily limits on wire transfers?",
        ]
    },
    {
        "category": "checks_deposits",
        "examples": [
            "How do I deposit a check using mobile app?",
            "How long does it take for a check to clear?",
            "Can I order new checks through online banking?",
            "What's the hold policy for large checks?",
            "How do I stop payment on a check?",
        ]
    },
    {
        "category": "atm_services",
        "examples": [
            "Where's the nearest ATM location?",
            "Can I deposit cash at any ATM?",
            "What's my daily ATM withdrawal limit?",
            "How do I avoid ATM fees?",
            "Can I check my balance at an ATM?",
        ]
    },
    {
        "category": "account_alerts",
        "examples": [
            "How do I set up low balance alerts?",
            "Can I get text notifications for transactions?",
            "How do I change my alert preferences?",
            "What types of account alerts are available?",
            "Can I get email alerts for deposits?",
        ]
    },
    {
        "category": "mobile_app",
        "examples": [
            "How do I reset my mobile banking password?",
            "Is the mobile app available for Android?",
            "Can I pay bills through the mobile app?",
            "How do I enable biometric login on the app?",
            "What features are available in the mobile app?",
        ]
    },
    {
        "category": "branch_services",
        "examples": [
            "What are your branch hours?",
            "Do I need an appointment to visit a branch?",
            "Where's the closest branch to me?",
            "Can I open an account at any branch?",
            "What services are available at the branch?",
        ]
    },
]

# Out-of-scope topics (completely unrelated - should return no or very few results)
# These are diverse finance topics clearly outside credit card support KB
OUT_OF_SCOPE_TOPICS = [
    {
        "category": "cryptocurrency",
        "examples": [
            "What's your policy on Bitcoin mining rewards for cardholders?",
            "Can I stake Ethereum using funds from my credit card?",
            "Do you support Web3 wallet integration with my account?",
            "How do I set up DeFi protocol payments with my card?",
            "What are the tax reporting requirements for crypto transactions on my card?",
        ]
    },
    {
        "category": "investment_products",
        "examples": [
            "What's the expense ratio on your index fund options?",
            "Can I set up a Roth IRA with automatic contributions?",
            "How do I rebalance my 401k portfolio through your platform?",
            "What are the margin rates for options trading on your brokerage?",
            "Can I invest in commodities futures through my account?",
        ]
    },
    {
        "category": "mortgage_loans",
        "examples": [
            "What's the APR for a 30-year fixed jumbo mortgage?",
            "Can I get pre-approved for a construction loan?",
            "Do you offer reverse mortgages for seniors?",
            "What are the closing costs for an FHA refinance?",
            "How does your bridge loan process work for home purchases?",
        ]
    },
    {
        "category": "business_banking",
        "examples": [
            "What's the interest rate on a $500K SBA loan?",
            "Can I get a merchant account for my e-commerce business?",
            "Do you offer factoring services for accounts receivable?",
            "What are the requirements for a business line of credit over $1M?",
            "Can I integrate QuickBooks with my business checking account?",
        ]
    },
    {
        "category": "international_banking",
        "examples": [
            "How do I open a multicurrency IBAN account?",
            "What are the SWIFT transfer fees to Asia-Pacific countries?",
            "Do you support SEPA transfers for European payments?",
            "Can I get foreign currency exchange at your offshore branches?",
            "What documentation is needed for cross-border remittances over $10K?",
        ]
    },
    {
        "category": "insurance_products",
        "examples": [
            "What's the death benefit on your whole life insurance policies?",
            "Can I bundle homeowners and auto insurance through your bank?",
            "Do you offer long-term care insurance for policyholders?",
            "What are the premium rates for disability income insurance?",
            "Can I add an umbrella liability policy to my existing coverage?",
        ]
    },
    {
        "category": "tax_services",
        "examples": [
            "Can you help me file my taxes through your tax preparation service?",
            "What tax documents do I need for capital gains reporting?",
            "Do you offer tax advisory services for high net worth individuals?",
            "How do I get a tax transcript for my business?",
            "What are the tax implications of my IRA withdrawal?",
        ]
    },
    {
        "category": "student_loans",
        "examples": [
            "What are the interest rates on federal student loans?",
            "Can I refinance my student loans with you?",
            "What's the income-driven repayment plan options?",
            "How do I apply for student loan forbearance?",
            "Do you offer parent PLUS loans?",
        ]
    },
    {
        "category": "auto_loans",
        "examples": [
            "What's your current APR for new car loans?",
            "Can I get pre-approved for an auto loan?",
            "What's the maximum loan term for used cars?",
            "Do you finance classic or collector vehicles?",
            "How do I refinance my existing car loan?",
        ]
    },
    {
        "category": "estate_planning",
        "examples": [
            "Do you offer trust services for estate planning?",
            "How do I set up a living trust with your wealth management team?",
            "What are the fees for estate administration services?",
            "Can you help with probate administration?",
            "Do you provide financial power of attorney services?",
        ]
    },
]


def load_kb_data() -> List[Dict[str, str]]:
    """Load questions from ground truth and synthetic datasets."""
    questions = []
    base_path = Path(__file__).parent.parent / "data"

    # Load both datasets
    for filename in ["dataset.csv", "synthetic_dataset.csv"]:
        filepath = base_path / filename
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    questions.append({
                        "question": row["question"],
                        "source": "ground_truth" if filename == "dataset.csv" else "synthetic"
                    })

    return questions


def generate_question_variation(original_question: str) -> str:
    """Use LLM to create a variation of an existing question."""
    prompt = f"""Generate ONE reworded version of this banking/credit card question. Mix up the style - sometimes make it short and direct, other times make it longer with realistic scenario context.

Original: {original_question}

Requirements:
- Generate exactly ONE reworded question (not a list)
- Ask the exact same information but with completely different wording
- Vary the sentence structure and style (e.g., formal vs casual, direct vs indirect, short vs detailed)
- Vary the length: can be 1 sentence OR 2-4 sentences with scenario context
- Use synonyms and alternative expressions where possible
- For longer versions, add realistic scenario details to make it natural
- Keep it conversational
- Don't add new information or change the core question

Example variations (you should generate just ONE like these):
- "What's the process for terminating my credit card?"
- "I've been thinking about switching to a different credit card provider because I found better rewards elsewhere. What's the process to close my current account with you, and are there any fees or things I should be aware of?"
- "My spouse and I are consolidating our finances and we want to close this account and merge everything into a joint card. Can you walk me through the closure process?"
- "I'm trying to pay my credit card bill but I'm not sure what options are available. Do you accept bank transfers?"
- "There's a charge on my statement from last week that I definitely didn't make - looks like someone used my card at a store I've never been to. How do I go about disputing this transaction and getting my money back?"

Now generate ONE reworded question:"""

    # Trace question generation to separate project
    with tracing_context(project_name="synthetic-generation"):
        response = question_generator.invoke([{"role": "user", "content": prompt}])
    return response.content.strip()


def generate_out_of_scope_question(category: str, base_example: str) -> str:
    """Generate a variation of an out-of-scope question."""
    prompt = f"""Reword this banking question to ask the same thing but with different phrasing:

Original: {base_example}

Requirements:
- Ask the exact same information but with different words
- Keep it natural and conversational
- Keep it similar length (1-2 sentences max)

Reworded question:"""

    # Trace question generation to separate project
    with tracing_context(project_name="synthetic-generation"):
        response = question_generator.invoke([{"role": "user", "content": prompt}])
    return response.content.strip()


def generate_question_bank(
    num_questions: int,
    in_scope_ratio: float = 0.4,
    irrelevant_ratio: float = 0.3,
    out_of_scope_ratio: float = 0.3
) -> List[Dict[str, str]]:
    """Generate a bank of test questions with three categories.

    Args:
        num_questions: Total number of questions to generate
        in_scope_ratio: Ratio of in-scope questions (can be answered from KB)
        irrelevant_ratio: Ratio of irrelevant questions (matches on generic terms but can't answer)
        out_of_scope_ratio: Ratio of completely out-of-scope questions (no or very low matches)

    Returns:
        List of question dictionaries with metadata
    """
    # Validate ratios
    total_ratio = in_scope_ratio + irrelevant_ratio + out_of_scope_ratio
    if abs(total_ratio - 1.0) > 0.01:
        raise ValueError(f"Ratios must sum to 1.0, got {total_ratio}")

    kb_questions = load_kb_data()
    num_in_scope = int(num_questions * in_scope_ratio)
    num_irrelevant = int(num_questions * irrelevant_ratio)
    num_out_of_scope = num_questions - num_in_scope - num_irrelevant

    question_bank = []

    # Generate in-scope questions (variations of existing KB questions)
    print(f"\n📝 Generating {num_in_scope} in-scope question variations...")
    # Sample without replacement to ensure variety
    base_questions_sample = random.sample(kb_questions, min(num_in_scope, len(kb_questions)))
    # If we need more than available, extend with additional samples
    while len(base_questions_sample) < num_in_scope:
        base_questions_sample.extend(random.sample(kb_questions, min(num_in_scope - len(base_questions_sample), len(kb_questions))))

    for i in range(num_in_scope):
        base_question = base_questions_sample[i]
        variation = generate_question_variation(base_question["question"])
        question_bank.append({
            "id": f"in_scope_{i+1:04d}",
            "question": variation,
            "original_question": base_question["question"],
            "in_scope": "yes",
            "relevance": "in_scope",
            "category": "in_scope",
            "source": base_question["source"]
        })
        if (i + 1) % 10 == 0 or (i + 1) == num_in_scope:
            print(f"  ✓ Generated {i + 1}/{num_in_scope} in-scope questions")

    # Generate irrelevant but matches questions
    print(f"\n📝 Generating {num_irrelevant} irrelevant (but matches) questions...")
    for i in range(num_irrelevant):
        topic = random.choice(IRRELEVANT_BUT_MATCHES_TOPICS)
        base_example = random.choice(topic["examples"])
        variation = generate_out_of_scope_question(topic["category"], base_example)

        question_bank.append({
            "id": f"irrelevant_{i+1:04d}",
            "question": variation,
            "original_question": base_example,
            "in_scope": "no",
            "relevance": "irrelevant_match",
            "category": topic["category"],
            "source": "generated"
        })
        if (i + 1) % 10 == 0 or (i + 1) == num_irrelevant:
            print(f"  ✓ Generated {i + 1}/{num_irrelevant} irrelevant questions")

    # Generate completely out-of-scope questions
    print(f"\n📝 Generating {num_out_of_scope} completely out-of-scope questions...")
    for i in range(num_out_of_scope):
        topic = random.choice(OUT_OF_SCOPE_TOPICS)
        base_example = random.choice(topic["examples"])
        variation = generate_out_of_scope_question(topic["category"], base_example)

        question_bank.append({
            "id": f"out_of_scope_{i+1:04d}",
            "question": variation,
            "original_question": base_example,
            "in_scope": "no",
            "relevance": "out_of_scope",
            "category": topic["category"],
            "source": "generated"
        })
        if (i + 1) % 10 == 0 or (i + 1) == num_out_of_scope:
            print(f"  ✓ Generated {i + 1}/{num_out_of_scope} out-of-scope questions")

    # Shuffle to mix all three types
    random.shuffle(question_bank)

    # Re-assign sequential IDs after shuffling
    for i, q in enumerate(question_bank):
        q["id"] = f"q_{i+1:04d}"

    return question_bank


def save_question_bank(questions: List[Dict[str, str]], output_path: Path):
    """Save question bank to CSV file."""
    print(f"\n💾 Saving question bank to {output_path}...")

    fieldnames = ["id", "question", "in_scope", "relevance", "category", "source", "original_question"]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(questions)

    print(f"✓ Saved {len(questions)} questions")


def print_sample_questions(questions: List[Dict[str, str]], num_samples: int = 5):
    """Print sample questions from the bank."""
    print("\n" + "=" * 80)
    print(f"SAMPLE QUESTIONS (showing {num_samples} of {len(questions)})")
    print("=" * 80)

    samples = random.sample(questions, min(num_samples, len(questions)))

    for q in samples:
        relevance_labels = {
            "in_scope": "IN-SCOPE",
            "irrelevant_match": "IRRELEVANT-MATCH",
            "out_of_scope": "OUT-OF-SCOPE"
        }
        relevance = relevance_labels.get(q["relevance"], "UNKNOWN")
        print(f"\n[{q['id']}] {relevance} ({q['category']})")
        print(f"  Q: {q['question']}")
        if q.get('original_question'):
            print(f"  Original: {q['original_question'][:80]}...")


def print_summary(questions: List[Dict[str, str]]):
    """Print summary statistics of the question bank."""
    print("\n" + "=" * 80)
    print("QUESTION BANK SUMMARY")
    print("=" * 80)

    total = len(questions)
    in_scope = sum(1 for q in questions if q["relevance"] == "in_scope")
    irrelevant = sum(1 for q in questions if q["relevance"] == "irrelevant_match")
    out_of_scope = sum(1 for q in questions if q["relevance"] == "out_of_scope")

    print(f"Total questions: {total}")
    print(f"  In-scope (can answer): {in_scope} ({in_scope/total*100:.1f}%)")
    print(f"  Irrelevant match (generic term matches): {irrelevant} ({irrelevant/total*100:.1f}%)")
    print(f"  Out-of-scope (no/low matches): {out_of_scope} ({out_of_scope/total*100:.1f}%)")
    print()

    # Category breakdown by relevance
    print("Categories by relevance:")
    relevance_types = ["in_scope", "irrelevant_match", "out_of_scope"]
    for rel_type in relevance_types:
        rel_questions = [q for q in questions if q["relevance"] == rel_type]
        if rel_questions:
            rel_name = rel_type.replace("_", " ").title()
            print(f"\n  {rel_name} ({len(rel_questions)} questions):")
            categories = {}
            for q in rel_questions:
                cat = q["category"]
                categories[cat] = categories.get(cat, 0) + 1
            for cat, count in sorted(categories.items()):
                print(f"    - {cat}: {count}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate a bank of test questions for trace generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate default bank (100 questions, 80% in-scope)
  python scripts/generate_question_bank.py

  # Generate larger bank with different ratio
  python scripts/generate_question_bank.py --num-questions 200 --in-scope-ratio 0.7

  # Preview 20 questions without saving
  python scripts/generate_question_bank.py --num-questions 20 --preview

  # Use seed for reproducibility
  python scripts/generate_question_bank.py --seed 42
        """
    )

    parser.add_argument(
        "--num-questions",
        type=int,
        default=100,
        help="Number of questions to generate (default: 100)"
    )
    parser.add_argument(
        "--in-scope-ratio",
        type=float,
        default=0.4,
        help="Ratio of in-scope questions (default: 0.4)"
    )
    parser.add_argument(
        "--irrelevant-ratio",
        type=float,
        default=0.3,
        help="Ratio of irrelevant but matches questions (default: 0.3)"
    )
    parser.add_argument(
        "--out-of-scope-ratio",
        type=float,
        default=0.3,
        help="Ratio of completely out-of-scope questions (default: 0.3)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/question_bank.csv",
        help="Output file path (default: data/question_bank.csv)"
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview questions without saving"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (default: None)"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.num_questions < 1:
        parser.error("num-questions must be at least 1")
    if not 0.0 <= args.in_scope_ratio <= 1.0:
        parser.error("in-scope-ratio must be between 0.0 and 1.0")
    if not 0.0 <= args.irrelevant_ratio <= 1.0:
        parser.error("irrelevant-ratio must be between 0.0 and 1.0")
    if not 0.0 <= args.out_of_scope_ratio <= 1.0:
        parser.error("out-of-scope-ratio must be between 0.0 and 1.0")

    # Check ratios sum to ~1.0
    total_ratio = args.in_scope_ratio + args.irrelevant_ratio + args.out_of_scope_ratio
    if abs(total_ratio - 1.0) > 0.01:
        parser.error(f"Ratios must sum to 1.0, got {total_ratio:.2f}")

    # Set random seed if provided
    if args.seed is not None:
        random.seed(args.seed)
        print(f"🎲 Using random seed: {args.seed}")

    print("=" * 80)
    print("QUESTION BANK GENERATOR")
    print("=" * 80)
    print(f"Generating {args.num_questions} questions")
    print(f"  In-scope: {args.in_scope_ratio:.0%}")
    print(f"  Irrelevant match: {args.irrelevant_ratio:.0%}")
    print(f"  Out-of-scope: {args.out_of_scope_ratio:.0%}")
    if args.preview:
        print("Mode: PREVIEW (will not save)")
    print("=" * 80)

    # Generate question bank
    questions = generate_question_bank(
        args.num_questions,
        args.in_scope_ratio,
        args.irrelevant_ratio,
        args.out_of_scope_ratio
    )

    # Print summary
    print_summary(questions)

    # Print sample questions
    print_sample_questions(questions, num_samples=10)

    # Save unless in preview mode
    if not args.preview:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_question_bank(questions, output_path)
        print(f"\n✅ Question bank ready at: {output_path}")
        print(f"   Use with: python scripts/generate_traces.py")
    else:
        print("\n⚠️  Preview mode - questions not saved")


if __name__ == "__main__":
    main()
