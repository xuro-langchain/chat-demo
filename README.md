# KB Agent Demo - Threads & Insights

Demo showing LangSmith threads and insights using a customer support KB agent.

## Setup

```bash
# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Add your ANTHROPIC_API_KEY and LANGSMITH_API_KEY to .env
```

## Generate Test Data

```bash
# Generate 200 single-turn traces
python scripts/generate_traces.py

# Generate 20 multi-turn conversation threads
python scripts/generate_threads.py

# Generate question bank (if needed)
python scripts/generate_question_bank.py
```

## Run Evaluation

```bash
# Run evaluation on generated traces
python evaluate/run_eval.py

# Test single example
python evaluate/test_single_example.py
```

## View Results

All traces and threads appear in your LangSmith project. View:
- **Threads**: Multi-turn conversations with state
- **Insights**: Evaluation metrics and patterns

## Test Agent Locally

```bash
# Start LangGraph Studio
langgraph dev
```

Open http://localhost:8000 to test the agent interactively.
