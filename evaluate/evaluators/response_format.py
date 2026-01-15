# Response format evaluator using LangSmith SDK with Claude Haiku
from typing import Any, Optional
from langchain.chat_models import init_chat_model


# Global judge LLM - will be initialized lazily
_judge_llm = None


def _get_judge_llm():
    """Get or initialize the judge LLM."""
    global _judge_llm
    if _judge_llm is None:
        _judge_llm = init_chat_model("claude-haiku-4-5-20251001", temperature=0)
    return _judge_llm


def _extract_final_response(run: Any) -> Optional[str]:
    """Extract the final AI response from the run outputs.

    Args:
        run: The agent execution run containing outputs

    Returns:
        The final response text, or None if not found
    """
    if not hasattr(run, "outputs") or not run.outputs:
        return None

    messages = run.outputs.get("messages", [])

    if not messages:
        return None

    # Get last AI message (skip tool calls and user messages)
    # Iterate in reverse to find the most recent AI response
    for msg in reversed(messages):
        # Handle both dict and object message formats
        if isinstance(msg, dict):
            msg_type = msg.get("type", "")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])

            # Check if this is an AI message with content and no tool calls
            if msg_type == "ai" and content and not tool_calls:
                return content
        else:
            msg_type = getattr(msg, "type", "")
            content = getattr(msg, "content", "")
            tool_calls = getattr(msg, "tool_calls", [])

            # Check if this is an AI message with content and no tool calls
            if msg_type == "ai" and content and not tool_calls:
                return content

    return None


def _create_evaluation_prompt(question: str, response: str) -> str:
    """Create the evaluation prompt for the judge LLM.

    Args:
        question: The original question from the dataset
        response: The agent's response to evaluate

    Returns:
        A formatted prompt for the judge LLM
    """
    return f"""You are evaluating how well a customer service agent followed specific format guidelines.

QUESTION: {question}

AGENT'S RESPONSE:
{response}

Evaluate the response on these CRITICAL format requirements:

1. BOLD OPENING: First sentence starts with ** and ends with **, answers the question directly
   - Must be the very first sentence, no preamble
   - Must directly answer the core question

2. INLINE CODE: Proper use of backticks for inline code (filenames, config keys, commands, function names)

3. CODE BLOCKS: Code blocks properly formatted with triple backticks and language specification

4. LINK FORMAT: Links in proper [text](url) format in "Relevant docs:" section at the very end

5. SECTION HEADERS: Proper use of ## headers for distinct sections (only when needed)

6. NO PROHIBITED ELEMENTS: No emojis, apologies, meta-commentary, or preambles

Provide a score from 0.0 to 1.0 based on overall adherence to these format guidelines:
- 1.0: Perfectly follows all guidelines
- 0.9: Excellent - minor cosmetic issues only
- 0.8: Good - follows most guidelines with minor deviations
- 0.7: Acceptable - has bold opening and proper links, some format issues
- 0.6: Below average - missing some key elements
- 0.5: Needs improvement - missing multiple elements
- 0.3: Poor - violates most guidelines
- 0.0: Completely ignores all guidelines

Be lenient with minor formatting choices (e.g., ### vs plain text for "Relevant docs").
Focus on critical elements: bold opening, proper link format, no meta-commentary after links.

Respond with ONLY a number between 0.0 and 1.0, nothing else."""


def _parse_score(score_text: str) -> float:
    """Parse and validate the score from the judge LLM response.

    Args:
        score_text: The raw text response from the judge LLM

    Returns:
        A float between 0.0 and 1.0

    Raises:
        ValueError: If the score cannot be parsed as a float
    """
    score = float(score_text.strip())
    # Clamp score between 0 and 1
    return max(0.0, min(1.0, score))


def evaluate_response_format(run: Any, example: Any) -> dict:
    """Evaluate how well the agent adhered to the prompt format guidelines.

    This is the main evaluator function called by LangSmith. It extracts the
    agent's response, evaluates it using GPT-5-nano, and returns a score.

    Args:
        run: The agent execution run with final output
        example: The dataset example with the question

    Returns:
        A dict with keys:
            - key: "response_format"
            - score: float between 0.0 and 1.0
            - comment: human-readable description
    """
    # Extract final response from the run
    final_response = _extract_final_response(run)

    if not final_response:
        return {
            "key": "response_format",
            "score": 0.0,
            "comment": "No final response found"
        }

    # Validate response is substantive
    if len(final_response.strip()) < 20:
        return {
            "key": "response_format",
            "score": 0.0,
            "comment": "Response too short to evaluate format"
        }

    # Get question from example
    question = example.inputs.get("question", "")

    # Create evaluation prompt
    evaluation_prompt = _create_evaluation_prompt(question, final_response)

    # Get evaluation from Claude Haiku
    try:
        judge_llm = _get_judge_llm()
        result = judge_llm.invoke([
            {
                "role": "system",
                "content": "You are an expert evaluator. Respond with only a number between 0.0 and 1.0."
            },
            {
                "role": "user",
                "content": evaluation_prompt
            }
        ])

        # Parse and validate score
        score = _parse_score(result.content)

        # Print evaluator feedback for observability
        print(f"\n⚖️  Evaluator Score: {score:.1%}")
        print(f"   Comment: Format adherence score: {score:.1%}\n")

        return {
            "key": "response_format",
            "score": score,
            "comment": f"Format adherence score: {score:.1%}"
        }

    except ValueError as e:
        return {
            "key": "response_format",
            "score": 0.5,
            "comment": f"Failed to parse score: {str(e)}"
        }

    except Exception as e:
        return {
            "key": "response_format",
            "score": 0.5,
            "comment": f"Evaluation failed: {str(e)}"
        }
