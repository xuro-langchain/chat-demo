# Test Suite

Test suite for the deep agent demo with KB retrieval.

## Structure

```
tests/
├── test_kb_retrieval.py           # Unit tests for KB tools (10 tests)
└── integration_tests/
    └── test_kb_agent_integration.py  # Integration tests for agent (16 tests)
```

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_kb_retrieval.py -v

# Run with coverage
uv run pytest --cov=src/tools tests/test_kb_retrieval.py
```

## Test Coverage

### KB Retrieval Tools (10 tests)
- Data loading from both datasets
- Search functionality and relevance
- Similarity thresholds
- Topic retrieval
- Category filtering
- Caching

### Agent Integration (16 tests)
- Agent and subagent configuration
- Tool integration
- Error handling
- Edge cases
- Data loading robustness
- Search relevance ordering
- Cross-dataset retrieval

## Requirements

All tests run locally without external API calls. The only requirement is that the CSV data files exist in the `data/` directory.

## Example Output

```
======================== 26 passed, 4 warnings in 1.68s ========================
```
