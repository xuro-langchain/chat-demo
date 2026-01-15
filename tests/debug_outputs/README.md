# Debug Outputs

This folder contains utilities for debugging stream events from the LangGraph agents.

## Files

- **debug_stream_events.py** - Script to capture all stream events from a test query
- **stream_events_debug.json** - Full stream event data (gitignored)
- **stream_events_summary.json** - Summary of events with node names (gitignored)

## Usage

Run the debug script from the project root:

```bash
# Set environment variables
export NEXT_PUBLIC_LANGGRAPH_API_URL="https://your-deployment.us.langgraph.app"
export LANGSMITH_API_KEY="your-api-key"

# Run the script
.venv/bin/python tests/debug_outputs/debug_stream_events.py
```

Or from anywhere:

```bash
cd /path/to/deepagent-template
NEXT_PUBLIC_LANGGRAPH_API_URL="https://your-deployment.us.langgraph.app" \
LANGSMITH_API_KEY="your-api-key" \
.venv/bin/python tests/debug_outputs/debug_stream_events.py
```

## Output

The script will:
1. Create a new thread
2. Send the test query: "how do subagents work"
3. Capture all stream events (values, updates, messages)
4. Save full details to `stream_events_debug.json`
5. Save a summary to `stream_events_summary.json`

Use these files to understand what's being streamed and debug streaming behavior.
