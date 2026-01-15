#!/usr/bin/env python3
# Simple test to invoke the deployment URL without streaming
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from langgraph_sdk import get_client

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


async def test_invoke():
    """Test invoking the deployment with client.runs.wait()"""

    # Get configuration
    deployment_url = os.getenv("LANGGRAPH_DEPLOYMENT_URL")
    if not deployment_url:
        print("Error: LANGGRAPH_DEPLOYMENT_URL not set")
        return

    langsmith_api_key = os.getenv("LANGSMITH_API_KEY")
    if not langsmith_api_key:
        print("Error: LANGSMITH_API_KEY not set")
        return

    print(f"Connecting to: {deployment_url}")

    # Create client
    client = get_client(url=deployment_url, api_key=langsmith_api_key)

    # Use the docs_agent graph
    assistant_id = "docs_agent"
    print(f"Using assistant: {assistant_id}")

    # Test question
    question = "How do I use middleware in LangGraph?"
    print(f"\nQuestion: {question}")
    print("=" * 80)

    # Create input
    input_data = {
        "messages": [
            {"role": "user", "content": question}
        ]
    }

    # Configure to use gpt-5-nano
    config = {
        "configurable": {
            "model": "gpt-5-nano",
            "temperature": 0
        }
    }

    print(f"Invoking with model: gpt-5-nano")
    print("Waiting for response (no streaming)...")

    try:
        # Use client.runs.wait() to invoke without streaming
        result = await client.runs.wait(
            None,  # Stateless run (no thread persistence)
            assistant_id,
            input=input_data,
            config=config
        )

        print("\nGot response!")
        print("=" * 80)

        # Extract messages from result
        messages = result.get("messages", [])
        print(f"\nResponse messages ({len(messages)} total):\n")

        for i, msg in enumerate(messages, 1):
            if hasattr(msg, "type"):
                msg_type = msg.type.upper()
                content = getattr(msg, "content", "")
            elif isinstance(msg, dict):
                msg_type = msg.get("type", msg.get("role", "unknown")).upper()
                content = msg.get("content", "")
            else:
                msg_type = "UNKNOWN"
                content = str(msg)

            # Print message type and preview
            print(f"{i}. [{msg_type}]")

            if isinstance(content, str):
                if len(content) > 200:
                    print(f"   {content[:200]}...")
                else:
                    print(f"   {content}")
            else:
                print(f"   {str(content)[:200]}...")

            # Check for tool calls
            if hasattr(msg, "tool_calls"):
                tool_calls = msg.tool_calls
            elif isinstance(msg, dict):
                tool_calls = msg.get("tool_calls", [])
            else:
                tool_calls = []

            if tool_calls:
                print(f"   Tool calls: {len(tool_calls)}")
                for tc in tool_calls[:3]:  # Show first 3
                    if isinstance(tc, dict):
                        tool_name = tc.get("name", "unknown")
                        tool_args = tc.get("args", {})
                    else:
                        tool_name = getattr(tc, "name", "unknown")
                        tool_args = getattr(tc, "args", {})

                    # Show relevant args
                    if "query" in tool_args:
                        print(f"      - {tool_name}(query='{tool_args['query']}')")
                    else:
                        print(f"      - {tool_name}")

            print()

        print("=" * 80)
        print("Test complete!")

    except Exception as e:
        print(f"\nError invoking deployment: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_invoke())
