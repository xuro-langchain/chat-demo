# Debug script to capture all stream events from docs_agent
import asyncio
import json
import os
from datetime import datetime
from langgraph_sdk import get_client

async def capture_stream_events():
    """Capture and save all stream events from a test query."""

    # Get client - use deployed URL from env
    api_url = os.getenv("LANGGRAPH_API_URL") or os.getenv("NEXT_PUBLIC_LANGGRAPH_API_URL")
    api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("NEXT_PUBLIC_LANGSMITH_API_KEY")

    if not api_url:
        raise ValueError("LANGGRAPH_API_URL or NEXT_PUBLIC_LANGGRAPH_API_URL must be set")

    print(f"🌐 Using API URL: {api_url}")

    client = get_client(
        url=api_url,
        api_key=api_key
    )

    # Create a unique thread ID for this test (using UUID format)
    import uuid
    thread_id = str(uuid.uuid4())

    print(f"🔍 Capturing stream events for thread: {thread_id}")
    print(f"📝 Query: 'how do subagents work'")
    print("-" * 80)

    # Prepare input
    input_data = {
        "messages": [
            {"role": "user", "content": "how do subagents work"}
        ]
    }

    # Collect all events
    all_events = []
    event_count = 0

    try:
        # Stream the response (matching frontend format)
        stream = client.runs.stream(
            thread_id,
            "docs_agent",
            input=input_data,
            config={
                "recursion_limit": 50,
                "configurable": {
                    "model": "claude-haiku-4-5",
                    "model_provider": "anthropic"
                }
            },
            stream_mode=["values", "updates", "messages"],
            stream_subgraphs=True,
            if_not_exists="create",
        )

        async for chunk in stream:
            event_count += 1

            # Convert chunk to dict for JSON serialization
            event_data = {
                "event_number": event_count,
                "event": chunk.event,
                "data": chunk.data,
            }

            # Try to capture metadata if available
            if hasattr(chunk, 'metadata'):
                event_data["metadata"] = chunk.metadata
            if hasattr(chunk, 'run_id'):
                event_data["run_id"] = chunk.run_id

            all_events.append(event_data)

            # Print summary
            print(f"Event #{event_count}: {chunk.event}")

            # If it's an updates event, show the keys
            if chunk.event == "updates" and isinstance(chunk.data, dict):
                node_names = list(chunk.data.keys())
                print(f"  → Nodes: {', '.join(node_names)}")

    except Exception as e:
        print(f"❌ Error during streaming: {e}")
        import traceback
        traceback.print_exc()

    print("-" * 80)
    print(f"✅ Captured {event_count} events")

    # Save to file in the same directory as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, "stream_events_debug.json")

    with open(output_file, 'w') as f:
        json.dump(all_events, f, indent=2, default=str)

    print(f"💾 Events saved to: {output_file}")

    # Also create a summary file with just event types and node names
    summary = []
    for event in all_events:
        event_type = event["event"]
        summary_item = {"event_number": event["event_number"], "event_type": event_type}

        if event_type == "updates" and isinstance(event.get("data"), dict):
            summary_item["nodes"] = list(event["data"].keys())

        summary.append(summary_item)

    summary_file = os.path.join(script_dir, "stream_events_summary.json")
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"📋 Summary saved to: {summary_file}")


if __name__ == "__main__":
    asyncio.run(capture_stream_events())
