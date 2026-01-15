#!/usr/bin/env python3
"""Generate multi-turn conversation threads using simulated users.

This script uses the thread_bank.csv created by generate_thread_bank.py
to generate realistic multi-turn conversations between simulated users
and the KB agent.

Usage:
    # First, generate a thread bank
    python scripts/generate_thread_bank.py --num-threads 20

    # Then generate threads using the bank
    python scripts/generate_threads.py --num-threads 10

    # Generate all threads in the bank
    python scripts/generate_threads.py --num-threads 20
"""

import argparse
import asyncio
import csv
import random
import sys
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage
from langchain.chat_models import init_chat_model
from langsmith import tracing_context
from src.agent.config import DEFAULT_MODEL
from src.agent.docs_graph import docs_agent

# Load environment variables
load_dotenv()

# Initialize LLM for simulated user
simulated_user_llm = init_chat_model(DEFAULT_MODEL.id, temperature=0.8)


class StoppingCondition(BaseModel):
    """Structured output for stopping condition detection."""
    should_stop: bool = Field(description="True if stopping condition was met, False if conversation should continue")
    reason: str = Field(description="Brief reason for the decision")


class SimulatedUser:
    """Simulated user that generates realistic conversation turns."""

    def __init__(self, persona: str, initial_intent: str, follow_up_topics: List[str]):
        self.persona = persona
        self.initial_intent = initial_intent
        self.follow_up_topics = follow_up_topics
        self.conversation_history = []

    def get_initial_message(self) -> str:
        """Generate the initial message from the user."""
        prompt = f"""You are a customer with the following persona:

{self.persona}

Generate a natural, conversational first message to a credit card support agent where you ask about: {self.initial_intent}

Requirements:
- Be natural and conversational (like a real customer)
- Keep it 1-3 sentences
- Don't be overly formal or robotic
- Get straight to the point

Generate ONLY the customer's message (no labels, no "Customer:" prefix):"""

        # Trace simulated user generation to separate project
        with tracing_context(project_name="synthetic-generation"):
            response = simulated_user_llm.invoke([{"role": "user", "content": prompt}])
        message = response.content.strip()
        self.conversation_history.append({"role": "user", "content": message})
        return message

    def _check_stopping_condition(self, agent_response: str) -> tuple[bool, str]:
        """Check if the conversation should stop based on satisfaction or repetition.

        Returns:
            (should_stop, reason) - whether to stop and why
        """
        # Build conversation trajectory
        trajectory = "\n\n".join([
            f"{'Customer' if msg['role'] == 'user' else 'Agent'}: {msg['content']}"
            for msg in self.conversation_history
        ])
        trajectory += f"\n\nAgent: {agent_response}"

        structured_llm = simulated_user_llm.with_structured_output(schema=StoppingCondition)
        stopping_prompt = """Determine if the stopping condition was met from the following conversation history.

To meet the stopping condition, the conversation must follow one of the following scenarios:
1. All inquiries are satisfied with clear, actionable answers, user has explicitly confirmed they have no more questions or would very clearly naturally conclude the conversation
2. Next steps are completely clear (no ambiguity), user has received thorough explanations, and there are genuinely no other reasonable follow-up questions
3. The conversation has been going in circles for 3+ turns with no new information being exchanged
4. The agent clearly cannot help with the topic (completely out of scope), has explained this clearly, and user has asked 3+ follow-up questions about the same out-of-scope topic

IMPORTANT: Be conservative - only stop if you're very confident the user would naturally end the conversation. If there's any reasonable follow-up question the user might ask, do NOT stop. One or two exchanges is usually NOT enough unless the answer was extremely comprehensive and the user explicitly confirmed satisfaction.

The conversation between the customer and the customer support assistant:
{conversation}
"""

        # Trace stopping condition check to separate project
        with tracing_context(project_name="synthetic-generation"):
            result = structured_llm.invoke([SystemMessage(content=stopping_prompt.format(conversation=trajectory))])
        return result.should_stop, result.reason

    def get_follow_up(self, agent_response: str, turn_number: int, max_turns: int) -> tuple[bool, str]:
        """Generate a follow-up message based on the agent's response.

        Returns:
            (should_continue, message) - whether to continue and the follow-up message
        """
        # First check if stopping condition is met
        should_stop, reason = self._check_stopping_condition(agent_response)
        if should_stop:
            return False, None

        # Check max turns
        if turn_number >= max_turns:
            return False, None

        # Build conversation context
        context = "\n\n".join([
            f"{'You' if msg['role'] == 'user' else 'Agent'}: {msg['content']}"
            for msg in self.conversation_history
        ])

        prompt = f"""You are a customer with the following persona:

{self.persona}

Conversation so far:
{context}

Agent's latest response:
{agent_response}

Your goal is to ask follow-up questions about these topics if relevant: {', '.join(self.follow_up_topics)}

Turn {turn_number}/{max_turns}

Based on the agent's response, decide:
1. If you're satisfied with the answers and have no more questions, respond with ONLY: "STOP"
2. If the agent clearly can't help and you've already asked follow-ups, respond with ONLY: "STOP"
3. If you have a NEW natural follow-up question that you haven't asked before, ask it

Requirements if asking a follow-up:
- Be natural and conversational
- React to what the agent said (thank them if helpful, express concern if there's an issue)
- Ask about something NEW - don't repeat or rephrase questions you've already asked
- Ask about something specific from your follow-up topics or clarify something from their response
- Keep it 1-3 sentences

Generate ONLY your response (either "STOP" or your follow-up message, no labels):"""

        # Trace simulated user follow-up generation to separate project
        with tracing_context(project_name="synthetic-generation"):
            response = simulated_user_llm.invoke([{"role": "user", "content": prompt}])
        message = response.content.strip()

        # Check if user wants to stop
        if message.upper() == "STOP":
            return False, None

        self.conversation_history.append({"role": "assistant", "content": agent_response})
        self.conversation_history.append({"role": "user", "content": message})
        return True, message


def load_thread_bank(bank_path: Path) -> List[Dict[str, str]]:
    """Load thread personas from the thread bank CSV file."""
    if not bank_path.exists():
        raise FileNotFoundError(
            f"Thread bank not found at {bank_path}\n"
            f"Generate one first with: python scripts/generate_thread_bank.py"
        )

    threads = []
    with open(bank_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            threads.append({
                "id": row["id"],
                "persona": row["persona"],
                "initial_intent": row["initial_intent"],
                "follow_up_topics": row["follow_up_topics"].split("|"),
                "in_scope": row["in_scope"] == "yes",
                "category": row["category"]
            })

    return threads


def select_threads(
    thread_bank: List[Dict[str, str]],
    num_threads: int,
    in_scope_ratio: float = None
) -> List[Dict[str, str]]:
    """Select threads from the bank for generation.

    Args:
        thread_bank: Full thread bank
        num_threads: Number of threads to select
        in_scope_ratio: If specified, enforce this ratio of in-scope threads

    Returns:
        Selected threads
    """
    if num_threads > len(thread_bank):
        print(f"⚠️  Warning: Requested {num_threads} threads but bank only has {len(thread_bank)}")
        print(f"   Using all {len(thread_bank)} threads from the bank")
        return thread_bank

    if in_scope_ratio is None:
        # Random selection without ratio constraint
        return random.sample(thread_bank, num_threads)

    # Select with ratio constraint
    in_scope_threads = [t for t in thread_bank if t["in_scope"]]
    out_of_scope_threads = [t for t in thread_bank if not t["in_scope"]]

    num_in_scope = int(num_threads * in_scope_ratio)
    num_out_of_scope = num_threads - num_in_scope

    # Check if we have enough threads
    if num_in_scope > len(in_scope_threads):
        print(f"⚠️  Warning: Need {num_in_scope} in-scope threads but bank only has {len(in_scope_threads)}")
        num_in_scope = len(in_scope_threads)
        num_out_of_scope = num_threads - num_in_scope

    if num_out_of_scope > len(out_of_scope_threads):
        print(f"⚠️  Warning: Need {num_out_of_scope} out-of-scope threads but bank only has {len(out_of_scope_threads)}")
        num_out_of_scope = len(out_of_scope_threads)
        num_in_scope = num_threads - num_out_of_scope

    # Sample from each pool
    selected = []
    if num_in_scope > 0:
        selected.extend(random.sample(in_scope_threads, num_in_scope))
    if num_out_of_scope > 0:
        selected.extend(random.sample(out_of_scope_threads, num_out_of_scope))

    # Shuffle to mix in-scope and out-of-scope
    random.shuffle(selected)

    return selected


async def run_thread_async(thread_data: Dict, max_turns: int = 5) -> Dict[str, Any]:
    """Run a multi-turn conversation thread with a simulated user.

    Args:
        thread_data: Thread metadata including persona
        max_turns: Maximum number of user turns (default: 5)

    Returns:
        Thread result with conversation history
    """
    try:
        # Create simulated user with the persona
        simulated_user = SimulatedUser(
            persona=thread_data["persona"],
            initial_intent=thread_data["initial_intent"],
            follow_up_topics=thread_data["follow_up_topics"]
        )

        conversation_history = []
        turn_count = 0

        # Create a unique thread_id for this conversation
        thread_id = thread_data["id"]
        config = {"configurable": {"thread_id": thread_id}}

        # Get initial message from simulated user
        user_message = await asyncio.to_thread(
            simulated_user.get_initial_message
        )

        while turn_count < max_turns:
            turn_count += 1

            # Add user message to history
            conversation_history.append({
                "role": "user",
                "content": user_message,
                "turn": turn_count
            })

            # Get agent response - pass config with thread_id to maintain conversation state
            input_data = {"messages": [{"role": "user", "content": user_message}]}
            result = await asyncio.to_thread(docs_agent.invoke, input_data, config)

            # Extract agent's response
            messages = result.get("messages", [])
            agent_response = None
            for msg in reversed(messages):
                if hasattr(msg, "type") and msg.type == "ai" and hasattr(msg, "content"):
                    if msg.content and not getattr(msg, "tool_calls", []):
                        agent_response = msg.content
                        break

            if not agent_response:
                agent_response = "I apologize, but I'm having trouble responding right now."

            # Add agent response to history
            conversation_history.append({
                "role": "assistant",
                "content": agent_response,
                "turn": turn_count
            })

            # Check if we should continue
            if turn_count >= max_turns:
                break

            # Get next user message
            should_continue, user_message = await asyncio.to_thread(
                simulated_user.get_follow_up,
                agent_response,
                turn_count,
                max_turns
            )

            if not should_continue or not user_message:
                break

        return {
            **thread_data,
            "conversation": conversation_history,
            "num_turns": turn_count,
            "success": True
        }

    except Exception as e:
        return {
            **thread_data,
            "conversation": [],
            "num_turns": 0,
            "success": False,
            "error": str(e)
        }


async def generate_threads_async(
    threads: List[Dict[str, str]],
    max_turns: int = 5,
    max_concurrent: int = 2
):
    """Generate conversation threads by running simulated users.

    Args:
        threads: List of thread metadata
        max_turns: Maximum turns per thread
        max_concurrent: Maximum number of concurrent threads
    """
    print(f"\n🤖 Running {len(threads)} simulated conversation threads...")
    print(f"   Max turns per thread: {max_turns}")
    print(f"   Max concurrency: {max_concurrent}")
    print("-" * 80)
    sys.stdout.flush()

    results = []

    # Process in batches to control concurrency
    for i in range(0, len(threads), max_concurrent):
        batch = threads[i:i + max_concurrent]
        batch_num = (i // max_concurrent) + 1
        total_batches = (len(threads) + max_concurrent - 1) // max_concurrent

        print(f"\nBatch {batch_num}/{total_batches} ({len(batch)} threads)")
        sys.stdout.flush()

        # Run batch concurrently
        tasks = [run_thread_async(t, max_turns) for t in batch]
        batch_results = await asyncio.gather(*tasks)

        # Print results
        for j, result in enumerate(batch_results):
            thread_num = i + j + 1
            scope = "IN-SCOPE  " if result.get("in_scope") else "OUT-OF-SCOPE"
            status = "✓" if result["success"] else "✗"
            thread_id = result.get("id", "unknown")
            num_turns = result.get("num_turns", 0)

            print(f"  {status} [{thread_num:2d}/{len(threads)}] [{thread_id}] {scope} ({num_turns} turns): {result['initial_intent'][:40]}...")
            if not result["success"]:
                print(f"      Error: {result.get('error', 'Unknown error')}")
            sys.stdout.flush()

        results.extend(batch_results)

    return results


def print_summary(results: List[Dict]):
    """Print summary statistics of the thread generation."""
    print("\n" + "=" * 80)
    print("THREAD GENERATION SUMMARY")
    print("=" * 80)

    total = len(results)
    successful = sum(1 for r in results if r["success"])
    failed = total - successful

    in_scope = sum(1 for r in results if r.get("in_scope", False))
    out_of_scope = total - in_scope

    # Calculate average turns
    total_turns = sum(r.get("num_turns", 0) for r in results if r["success"])
    avg_turns = total_turns / successful if successful > 0 else 0

    print(f"Total threads: {total}")
    print(f"  Successful: {successful} ({successful/total*100:.1f}%)")
    if failed > 0:
        print(f"  Failed: {failed} ({failed/total*100:.1f}%)")
    print()
    print(f"Average turns per thread: {avg_turns:.1f}")
    print()
    print(f"In-scope threads: {in_scope} ({in_scope/total*100:.1f}%)")
    print(f"Out-of-scope threads: {out_of_scope} ({out_of_scope/total*100:.1f}%)")

    # Category breakdown
    categories = {}
    for r in results:
        cat = r.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    print("\nCategories:")
    for cat, count in sorted(categories.items()):
        print(f"  - {cat}: {count}")

    # Show sample conversation
    print("\n" + "=" * 80)
    print("SAMPLE CONVERSATION (first successful thread)")
    print("=" * 80)

    for result in results:
        if result["success"] and result.get("conversation"):
            print(f"\nThread: {result['id']} ({result['category']})")
            print(f"Persona: {result['persona'][:100]}...")
            print(f"\nConversation ({result['num_turns']} turns):\n")

            for msg in result["conversation"]:
                role = "USER" if msg["role"] == "user" else "AGENT"
                content = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
                print(f"[Turn {msg['turn']}] {role}: {content}\n")
            break

    print()
    print("✅ Threads have been generated in LangSmith.")
    print("   View at: https://smith.langchain.com/")
    sys.stdout.flush()


async def main():
    parser = argparse.ArgumentParser(
        description="Generate multi-turn conversation threads using simulated users",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 10 threads from the default thread bank
  python scripts/generate_threads.py --num-threads 10

  # Generate 20 threads with 70% in-scope
  python scripts/generate_threads.py --num-threads 20 --in-scope-ratio 0.7

  # Use custom thread bank
  python scripts/generate_threads.py --thread-bank data/my_threads.csv --num-threads 5

  # Longer conversations (up to 8 turns)
  python scripts/generate_threads.py --num-threads 10 --max-turns 8

Note: Generate the thread bank first with generate_thread_bank.py
        """
    )

    parser.add_argument(
        "--num-threads",
        type=int,
        default=10,
        help="Number of threads to generate (default: 10)"
    )
    parser.add_argument(
        "--thread-bank",
        type=str,
        default="data/thread_bank.csv",
        help="Path to thread bank CSV (default: data/thread_bank.csv)"
    )
    parser.add_argument(
        "--in-scope-ratio",
        type=float,
        default=None,
        help="Ratio of in-scope threads (0.0 to 1.0, default: use bank's ratio)"
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=5,
        help="Maximum turns per thread (default: 5)"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=2,
        help="Maximum concurrent threads (default: 2, lower than traces due to complexity)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (default: None)"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.num_threads < 1:
        parser.error("num-threads must be at least 1")
    if args.in_scope_ratio is not None and not 0.0 <= args.in_scope_ratio <= 1.0:
        parser.error("in-scope-ratio must be between 0.0 and 1.0")
    if args.max_turns < 1:
        parser.error("max-turns must be at least 1")
    if args.max_turns > 10:
        parser.error("max-turns should not exceed 10 to keep threads manageable")
    if args.max_concurrent < 1:
        parser.error("max-concurrent must be at least 1")

    # Set random seed if provided
    if args.seed is not None:
        random.seed(args.seed)
        print(f"🎲 Using random seed: {args.seed}")

    print("=" * 80)
    print("MULTI-TURN THREAD GENERATOR")
    print("=" * 80)
    sys.stdout.flush()

    # Load thread bank
    bank_path = Path(args.thread_bank)
    print(f"📚 Loading thread bank from: {bank_path}")
    sys.stdout.flush()
    try:
        thread_bank = load_thread_bank(bank_path)
        print(f"   Loaded {len(thread_bank)} thread personas")

        # Show bank composition
        in_scope_count = sum(1 for t in thread_bank if t["in_scope"])
        out_of_scope_count = len(thread_bank) - in_scope_count
        print(f"   Bank composition: {in_scope_count} in-scope, {out_of_scope_count} out-of-scope")
        sys.stdout.flush()

    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        sys.stdout.flush()
        return

    # Select threads
    print(f"\n🎯 Selecting {args.num_threads} threads...")
    if args.in_scope_ratio is not None:
        print(f"   Target ratio: {args.in_scope_ratio:.0%} in-scope")

    threads = select_threads(thread_bank, args.num_threads, args.in_scope_ratio)

    actual_in_scope = sum(1 for t in threads if t["in_scope"])
    actual_out_of_scope = len(threads) - actual_in_scope
    print(f"   Selected: {actual_in_scope} in-scope, {actual_out_of_scope} out-of-scope")
    print(f"   Max turns per thread: {args.max_turns}")
    print(f"   Max concurrent: {args.max_concurrent}")
    sys.stdout.flush()

    # Run threads to generate conversations
    results = await generate_threads_async(
        threads,
        max_turns=args.max_turns,
        max_concurrent=args.max_concurrent
    )

    # Print summary
    print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
