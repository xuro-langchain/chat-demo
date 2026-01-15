# Evaluation Tests

Unit tests and integration tests for the evaluation system.

## Tests

- **`test_response_format.py`** - Unit test for the response format evaluator
- **`test_invoke.py`** - Integration test for invoking the agent

## Usage

Run tests to verify evaluators work correctly:

```bash
# Test the response format evaluator
python evaluate/tests/test_response_format.py

# Test agent invocation
python evaluate/tests/test_invoke.py
```

These tests help ensure your evaluators are working correctly before running full evaluations.
