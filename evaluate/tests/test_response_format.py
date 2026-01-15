# Quick test script for the response format evaluator
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluate.evaluators import evaluate_response_format


class MockMessage:
    """Mock message for testing."""
    def __init__(self, content):
        self.content = content


class MockRun:
    """Mock run for testing."""
    def __init__(self, response_text):
        self.outputs = {
            "messages": [MockMessage(response_text)]
        }


class MockInputs:
    """Mock inputs for testing."""
    def __init__(self, question):
        self.question = question

    def get(self, key, default=None):
        return getattr(self, key, default)


class MockExample:
    """Mock example for testing."""
    def __init__(self, question):
        self.inputs = MockInputs(question)


def test_evaluator():
    """Test the response format evaluator with a sample response."""

    # Sample response with good format
    good_response = """**LangGraph checkpoints allow you to save and restore graph state for persistence and error recovery.**

Checkpoints are created using a `CheckpointSaver` class. Here's how to set it up:

```python
from langgraph.checkpoint.postgres import PostgresCheckpointSaver

# Configure the checkpoint saver
checkpointer = PostgresCheckpointSaver(connection_string="postgresql://...")
```

The checkpointer automatically saves state after each node execution.

**Relevant docs:**

- [Checkpoint savers](https://docs.langgraph.com/checkpoint-savers) - Overview of checkpoint persistence
- [PostgreSQL checkpointer](https://docs.langgraph.com/checkpoint-postgres) - PostgreSQL implementation details"""

    # Create mock objects
    run = MockRun(good_response)
    example = MockExample("How do LangGraph checkpoints work?")

    # Run evaluator
    print("Testing response format evaluator...")
    print(f"Question: {example.inputs.get('question')}")
    print(f"\nResponse preview: {good_response[:100]}...\n")

    result = evaluate_response_format(run, example)

    print(f"Evaluation result:")
    print(f"  Key: {result['key']}")
    print(f"  Score: {result['score']:.2%}")
    print(f"  Comment: {result['comment'][:200]}...")

    print("\nEvaluator test completed successfully!")


if __name__ == "__main__":
    test_evaluator()
