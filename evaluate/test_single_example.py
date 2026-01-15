# Quick test with a single example
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from langsmith import Client, traceable, aevaluate
from langgraph_sdk import get_client
from evaluate.evaluators import evaluate_response_format


# Global LangGraph client
langgraph_client = None


def init_langgraph_client():
    """Initialize the LangGraph client."""
    global langgraph_client
    deployment_url = os.getenv("LANGGRAPH_DEPLOYMENT_URL")
    langsmith_api_key = os.getenv("LANGSMITH_API_KEY")
    langgraph_client = get_client(url=deployment_url, api_key=langsmith_api_key)


@traceable
async def run_agent(inputs: dict) -> dict:
    """Run the docs agent via deployment."""
    question = inputs["question"]
    print(f"\nQuestion: {question}")

    input_data = {
        "messages": [
            {"role": "user", "content": question}
        ]
    }

    config = {
        "configurable": {
            "model": "claude-haiku-4-5-20251001",
            "temperature": 0
        }
    }

    result = await langgraph_client.runs.wait(
        None,
        "docs_agent",
        input=input_data,
        config=config
    )

    return {"messages": result["messages"]}


async def main():
    """Run evaluation on a single example."""

    # Initialize clients
    print("Initializing LangGraph client...")
    init_langgraph_client()
    client = Client()

    # Get dataset
    dataset_name = os.getenv("EVAL_DATASET_NAME", "kb-agent-golden-set")
    dataset = client.read_dataset(dataset_name=dataset_name)
    print(f"Found dataset: {dataset_name}")

    # Get just the first example
    examples = list(client.list_examples(dataset_id=dataset.id, limit=1))

    if not examples:
        print("No examples found in dataset")
        return

    example = examples[0]
    print(f"Testing with: {example.inputs.get('question', 'N/A')[:60]}...")

    # Create a mini dataset with just this one example
    test_dataset_name = "jewel-test-single"

    # Delete if exists
    try:
        existing = client.read_dataset(dataset_name=test_dataset_name)
        client.delete_dataset(dataset_id=existing.id)
    except:
        pass

    # Create new dataset with single example
    test_dataset = client.create_dataset(dataset_name=test_dataset_name)
    client.create_example(
        dataset_id=test_dataset.id,
        inputs=example.inputs,
        outputs=example.outputs
    )

    print(f"\nRunning evaluation...")
    print(f"   Agent model: claude-haiku-4-5-20251001")
    print(f"   Judge model: gpt-5-nano")
    print()

    # Run evaluation
    results = await aevaluate(
        run_agent,
        data=test_dataset_name,
        evaluators=[evaluate_response_format],
        experiment_prefix="test-single",
        max_concurrency=1,
    )

    print(f"\nEvaluation complete!")
    print(f"   Experiment: {results.experiment_name}")

    # Cleanup
    client.delete_dataset(dataset_id=test_dataset.id)
    print(f"\nCleaned up test dataset")


if __name__ == "__main__":
    asyncio.run(main())
