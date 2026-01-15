# LangSmith Fetch

LangSmith Fetch is a CLI tool that brings LangSmith tracing directly into your terminal and IDE for debugging agents.

## Installation

```bash
pip install langsmith-fetch
```

## Authentication

Set your LangSmith API key:

```bash
export LANGSMITH_API_KEY=your_api_key
```

## Core Commands

### Fetch Recent Traces

```bash
# Get most recent trace from a project
langsmith-fetch traces --project-uuid <your-uuid> --format json

# Get traces from the last 30 minutes
langsmith-fetch traces --project-uuid <your-uuid> --last-n-minutes 30

# Get the last 5 traces
langsmith-fetch traces --project-uuid <your-uuid> --limit 5

# Get traces after a specific date
langsmith-fetch traces ./traces --project-uuid <your-uuid> --after 2025-12-01
```

### Fetch Threads

```bash
# Fetch most recent thread
langsmith-fetch threads --project-uuid <your-uuid>

# Export 50 threads to individual JSON files
langsmith-fetch threads ./my-data --limit 50
```

## Use Cases

### Quick Debugging Workflow

After running an agent locally, immediately fetch the trace:

```bash
langsmith-fetch traces --project-uuid <your-uuid> --format json
```

### Bulk Export for Evaluation

Export traces for building datasets, analysis, or test suites:

```bash
# Export threads to individual JSON files
langsmith-fetch threads ./my-data --limit 50

# Export traces with temporal filters
langsmith-fetch traces ./traces --project-uuid <your-uuid> --after 2025-12-01
```

### Integration with Coding Agents

Feed trace data directly to Claude Code or other AI coding assistants:

```bash
# Analyze traces with Claude Code
claude-code "use langsmith-fetch to analyze the traces in <project-uuid> and tell me why the agent failed"
```

## Output Formats

- `--format json` - JSON output for programmatic processing
- Files are saved as individual JSON files when providing an output directory

## Key Benefits

- No context-switching to web UI
- Pipe output to jq or other Unix tools
- Save traces to files for later analysis
- Feed data to coding agents
- Build scripts that process hundreds of traces
- Composable with any tool in your ecosystem

## Resources

- [GitHub Repository](https://github.com/langchain-ai/langsmith-fetch)
- [PyPI Package](https://pypi.org/project/langsmith-fetch/)
