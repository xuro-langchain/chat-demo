# Deep Agent Demo with KB Retrieval

> A demonstration of the deep agent pattern using KB retrieval for intelligent customer support

[![LangGraph](https://img.shields.io/badge/Built%20with-LangGraph-blue)](https://langchain-ai.github.io/langgraph/)
[![DeepAgents](https://img.shields.io/badge/Powered%20by-DeepAgents-purple)](https://github.com/langchain-ai/deepagents)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## Overview

This project demonstrates the **deep agent pattern** with a practical KB retrieval system. The main agent orchestrates a specialized KB subagent to search and retrieve information from a unified knowledge base containing both ground truth and synthetic customer support data.

### Key Features

- **Deep Agent Architecture**: Orchestrator with specialized KB retrieval subagent
- **Unified Knowledge Base**: Ground truth + synthetic data (1776 entries total)
- **TF-IDF Search**: Fast, local retrieval using scikit-learn (no external APIs required)
- **Realistic Data**: Banking/credit card support covering 10+ topic areas
- **FastAPI Backend**: REST API for testing and integration
- **Complete Test Suite**: Verified retrieval functionality

## Architecture

```
                    ┌──────────────────┐
                    │  Main Agent      │
                    │  (Orchestrator)  │
                    └────────┬─────────┘
                             │
                        ┌────▼────┐
                        │   KB    │
                        │Subagent │
                        └────┬────┘
                             │
                    ┌────────▼────────┐
                    │  TF-IDF Search  │
                    │   (scikit-learn) │
                    └────────┬────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
           ┌────▼────┐              ┌────▼────┐
           │ Ground  │              │Synthetic│
           │ Truth   │              │  Data   │
           │  CSV    │              │   CSV   │
           └─────────┘              └─────────┘
```

### How It Works

1. **User asks a question** → Main orchestrator receives it
2. **Orchestrator delegates** → Calls KB specialist subagent
3. **KB specialist searches** → TF-IDF search across both datasets
4. **Orchestrator synthesizes** → Formats findings into final answer

## Data

The project includes two datasets in `data/`:

- **`dataset.csv`** (1726 rows) - Ground truth data about account closures (DO NOT MODIFY)
- **`synthetic_dataset.csv`** (50 rows) - Generated support data covering:
  - Payment processing
  - Disputes & chargebacks
  - Rewards programs
  - Card activation
  - Fraud protection
  - Balance transfers
  - Credit limit changes
  - Account statements
  - Interest rates & fees
  - Lost/stolen cards

Both datasets are loaded and searched together for unified retrieval.

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

```bash
# Clone the repository
cd /path/to/chatbot

# Install dependencies with uv
uv sync

# Or with pip
pip install -e .
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys
```

#### Required Environment Variables

At minimum, you need ONE LLM provider:

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic Claude (recommended) |
| `OPENAI_API_KEY` | OpenAI GPT models |

Optional:

| Variable | Description |
|----------|-------------|
| `LANGSMITH_API_KEY` | LangSmith for tracing/monitoring |
| `LANGSMITH_PROJECT` | Project name (default: "deep-agent-demo") |

### Running Tests

```bash
# Run KB retrieval tests
uv run pytest tests/test_kb_retrieval.py -v

# Run all tests
uv run pytest -v
```

### Running the Agent

#### Option 1: LangGraph Studio (Recommended)

```bash
# Start LangGraph Studio
langgraph dev
```

Then open http://localhost:8000 to interact with the agent visually.

#### Option 2: FastAPI Server

```bash
# Start the server
uv run uvicorn src.api.server:app --reload --port 8000

# API docs at http://localhost:8000/docs
```

## Project Structure

```
chatbot/
├── data/
│   ├── dataset.csv              # Ground truth (DO NOT MODIFY)
│   └── synthetic_dataset.csv    # Synthetic support data
├── src/
│   ├── agent/
│   │   ├── docs_graph.py        # Main deep agent
│   │   ├── subagents.py         # KB specialist subagent
│   │   └── config.py            # Model config & middleware
│   ├── prompts/
│   │   ├── deep_agent_prompt.py # Orchestrator prompt
│   │   └── subagents/
│   │       └── kb_specialist_prompt.py  # KB specialist prompt
│   ├── tools/
│   │   └── kb_retrieval_tools.py  # TF-IDF search tools
│   └── api/
│       ├── fastapi_app.py       # FastAPI application
│       └── server.py            # Server entry point
├── scripts/
│   └── generate_synthetic_data.py  # Data generation script
└── tests/
    └── test_kb_retrieval.py     # KB retrieval tests
```

## KB Retrieval Tools

The project uses TF-IDF (Term Frequency-Inverse Document Frequency) for fast, local retrieval:

### `search_kb_tool(query, num_results)`
Main search function that returns formatted results.

```python
from src.tools.kb_retrieval_tools import search_kb_tool

results = search_kb_tool("how to make a payment", num_results=3)
```

### `get_topic_details(topic)`
Get complete information about a specific topic.

```python
details = get_topic_details("payment processing")
```

### `list_topics(category)`
List available topics, optionally filtered by category.

```python
topics = list_topics(category="payment")
```

## Understanding the Deep Agent Pattern

### Main Agent (Orchestrator)

```python
from deepagents import create_deep_agent

docs_agent = create_deep_agent(
    tools=[search_kb_tool, get_topic_details, list_topics],
    system_prompt=research_instructions,
    subagents=[kb_specialist_subagent],
    model=configurable_model,
)
```

### KB Specialist Subagent

```python
kb_specialist_subagent = {
    "name": "kb-specialist",
    "description": "Knowledge base expert for customer support",
    "system_prompt": kb_specialist_prompt,
    "tools": [search_kb_tool, get_topic_details, list_topics],
}
```

### Research Workflow

1. Main agent receives: "How long does a balance transfer take?"
2. Orchestrator delegates to KB specialist
3. KB specialist searches: `search_kb_tool("balance transfer")`
4. Returns structured JSON with answer, key points, and details
5. Orchestrator formats final response

## Generating More Synthetic Data

To expand the synthetic dataset:

```bash
# Edit scripts/generate_synthetic_data.py to add more topics
# Then run:
python3 scripts/generate_synthetic_data.py
```

The script generates realistic procedural support data following the same pattern as the ground truth.

## API Endpoints

### Core Endpoints

- `GET /` - API info
- `GET /health` - Health check
- `POST /generate-title` - Generate conversation titles

### Integration Endpoints (for testing)

- `POST /pylon/jewels` - Pylon webhook
- `POST /slack/events` - Slack webhook

## Development

### Adding New Topics

1. Edit `scripts/generate_synthetic_data.py`
2. Add new topic template with questions and chunks
3. Run script to regenerate `synthetic_dataset.csv`
4. Tests will automatically pick up new data

### Modifying Prompts

All prompts are in `src/prompts/`:
- `deep_agent_prompt.py` - Main orchestrator logic
- `subagents/kb_specialist_prompt.py` - KB specialist instructions

### Testing

```bash
# Run all tests
uv run pytest -v

# Run specific test
uv run pytest tests/test_kb_retrieval.py::test_search_knowledge_base -v

# Run with coverage
uv run pytest --cov=src/tools tests/test_kb_retrieval.py
```

## Performance

The TF-IDF approach provides:
- **Fast search**: < 100ms for typical queries
- **No external dependencies**: Runs completely locally
- **Scalable**: Handles 1000+ documents efficiently
- **Interpretable**: Similarity scores show relevance

For production with larger datasets (10k+ entries), consider upgrading to dense embeddings (OpenAI, Sentence Transformers, etc.).

## Learn More

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [DeepAgents Pattern](https://github.com/langchain-ai/deepagents)
- [LangChain Documentation](https://docs.langchain.com/)

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Acknowledgments

This demo simplifies production customer support infrastructure to demonstrate the deep agent pattern with practical KB retrieval.
