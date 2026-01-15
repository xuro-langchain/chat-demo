# Evaluation System

Evaluation system for the KB retrieval agent using LangSmith and LLM-as-judge.

## Quick Start

### 1. Generate Dataset

```bash
# Set LangSmith API key
export LANGSMITH_API_KEY=your_key

# Generate evaluation dataset (15 banking/credit card questions)
python evaluate/dataset_generator.py
```

This creates a dataset named `kb-agent-golden-set` with 15 examples covering:
- Payment processing
- Disputes & chargebacks
- Rewards programs
- Card activation
- Fraud protection
- Balance transfers
- Credit limits
- Statements
- Interest & fees
- Account closure

### 2. Run Evaluation

```bash
# Run evaluation on all examples
python evaluate/run_eval.py

# Run on first 3 examples only (for testing)
python evaluate/run_eval.py --num-examples 3
```

## How It Works

1. **Agent invocation**: Runs the local KB retrieval agent for each question
2. **Response evaluation**: Uses LLM-as-judge to evaluate response format and quality
3. **Results tracking**: Stores all runs in LangSmith for analysis

## Configuration

Edit `run_eval.py` to customize:
- `DATASET_NAME`: Dataset to evaluate on
- `EXPERIMENT_PREFIX`: Prefix for experiment naming
- `MAX_CONCURRENCY`: Number of concurrent evaluations

## Evaluators

Located in `evaluators/`:
- `response_format.py`: Checks if response is well-formatted and helpful

## Requirements

```bash
# Install evaluation dependencies (included in main dependencies)
pip install langsmith
```

Required environment variables:
- `LANGSMITH_API_KEY`: For evaluation tracking
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`: For running the agent

## View Results

After running evaluation:
1. Visit https://smith.langchain.com/
2. Navigate to "Experiments" tab
3. Find experiment with prefix `kb-agent-eval`

## Example Output

```
✅ Running local KB retrieval agent...
Found dataset: kb-agent-golden-set
   Examples: 15

Starting evaluation...
   Dataset: kb-agent-golden-set
   Agent: Local KB retrieval agent
   Evaluators: 1 (response_format)
   Max concurrency: 3

Processing: How do I make a payment on my credit card?...
Agent Response: Payments can be made through online banking...

Evaluation complete!
   View results: https://smith.langchain.com/

📊 Summary:
   response_format: 93.3% (n=15)
```
