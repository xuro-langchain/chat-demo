# Main evaluation runner for the KB retrieval agent
import os
import sys
import asyncio
import argparse
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

from langsmith import Client, traceable, aevaluate

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.docs_graph import docs_agent
from evaluate.evaluators import evaluate_response_format


# Load environment variables
ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH)

# Configuration constants (from environment variables with defaults)
DATASET_NAME = os.getenv("EVAL_DATASET_NAME", "kb-agent-golden-set")
EXPERIMENT_PREFIX = os.getenv("EVAL_EXPERIMENT_PREFIX", "kb-agent-eval")
MAX_CONCURRENCY = 3


def _validate_environment() -> None:
    """Validate that all required environment variables are set.

    Raises:
        SystemExit: If any required environment variables are missing
    """
    required_vars = {
        "LANGSMITH_API_KEY": "LangSmith API key for evaluation tracking",
        "ANTHROPIC_API_KEY": "Anthropic API key (or OPENAI_API_KEY)",
    }

    missing_vars = []
    for var, description in required_vars.items():
        if var == "ANTHROPIC_API_KEY":
            # Either Anthropic or OpenAI is fine
            if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY"):
                missing_vars.append(f"  - ANTHROPIC_API_KEY or OPENAI_API_KEY: LLM provider API key")
        elif not os.getenv(var):
            missing_vars.append(f"  - {var}: {description}")

    if missing_vars:
        print("Error: Missing required environment variables:\n")
        print("\n".join(missing_vars))
        print("\nPlease set these variables in your .env file.")
        sys.exit(1)


@traceable
async def run_agent(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Target function that runs the KB retrieval agent locally.

    This function is called by LangSmith's evaluate function for each
    example in the dataset. It invokes the local agent and returns
    the response messages.

    Args:
        inputs: Dict with "question" key containing the user's question

    Returns:
        Dict with "messages" key containing the agent's response messages
    """
    question = inputs["question"]
    print(f"\nProcessing: {question[:80]}...")

    # Prepare agent input
    input_data = {
        "messages": [
            {"role": "user", "content": question}
        ]
    }

    # Invoke agent locally
    result = await asyncio.to_thread(docs_agent.invoke, input_data)

    # Print agent response for observability
    messages = result.get("messages", [])
    if messages:
        last_message = messages[-1]
        if hasattr(last_message, "content"):
            content = last_message.content
        elif isinstance(last_message, dict):
            content = last_message.get("content", "")
        else:
            content = str(last_message)

        print(f"\nAgent Response:")
        print(f"   {content[:500]}..." if len(content) > 500 else f"   {content}")
        print()

    return {"messages": result["messages"]}


def _load_dataset(client: Client) -> Any:
    """Load the evaluation dataset from LangSmith.

    Args:
        client: LangSmith client instance

    Returns:
        The loaded dataset

    Raises:
        SystemExit: If dataset cannot be found
    """
    try:
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
        print(f"Found dataset: {DATASET_NAME}")
        print(f"   Examples: {dataset.example_count}")
        return dataset

    except Exception as e:
        print(f"Error: Could not find dataset '{DATASET_NAME}'")
        print(f"   Run: python evaluate/dataset_generator.py")
        print(f"   Error: {e}")
        sys.exit(1)


def _print_evaluation_config() -> None:
    """Print the evaluation configuration."""
    print("\nStarting evaluation...")
    print(f"   Dataset: {DATASET_NAME}")
    print(f"   Agent: Local KB retrieval agent")
    print(f"   Evaluators: 1 (response_format)")
    print(f"   Max concurrency: {MAX_CONCURRENCY}")
    print()


def _print_results(results: Any) -> None:
    """Print evaluation results summary.

    Args:
        results: The evaluation results from aevaluate
    """
    print(f"\nEvaluation complete!")
    print(f"   View results: https://smith.langchain.com/")

    # Extract experiment ID from name if available
    if hasattr(results, "experiment_name"):
        experiment_id = results.experiment_name.split("-")[-1]
        print(f"   Experiment ID: {experiment_id}")

    # Print score summary
    print(f"\n📊 Summary:")

    # Results might be an object with properties, not a dict
    if hasattr(results, "__dict__"):
        results_dict = results.__dict__
    else:
        results_dict = {}

    for key, value in results_dict.items():
        if isinstance(value, dict) and "mean" in value:
            score = value["mean"] * 100 if value["mean"] is not None else 0
            count = value.get("count", 0)
            print(f"   {key}: {score:.1f}% (n={count})")


async def main(num_examples: int | None = None) -> None:
    """Main evaluation function.

    Validates environment, loads dataset, runs evaluation, and prints results.

    Args:
        num_examples: Optional number of examples to run (defaults to all)
    """
    # Validate environment variables
    _validate_environment()

    print("✅ Running local KB retrieval agent...")

    # Initialize LangSmith client
    client = Client()

    # Load dataset
    dataset = _load_dataset(client)

    # Get examples from dataset
    if num_examples is not None:
        # Fetch limited number of examples
        examples = list(client.list_examples(dataset_name=DATASET_NAME, limit=num_examples))
        data_input = examples
        print(f"\n   Running on {num_examples} example(s) only")
    else:
        data_input = DATASET_NAME

    # Print configuration
    _print_evaluation_config()

    # Run evaluation
    results = await aevaluate(
        run_agent,
        data=data_input,
        evaluators=[evaluate_response_format],
        experiment_prefix=EXPERIMENT_PREFIX,
        max_concurrency=MAX_CONCURRENCY,
    )

    # Print results
    _print_results(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run KB agent evaluation")
    parser.add_argument(
        "--num-examples",
        type=int,
        default=None,
        help="Run evaluation on only the first N examples (default: all)"
    )
    args = parser.parse_args()

    asyncio.run(main(num_examples=args.num_examples))
