# Generate golden dataset for KB retrieval agent evaluation
import os
from pathlib import Path
from dotenv import load_dotenv
from langsmith import Client

# Load environment variables
ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH)


def create_golden_dataset():
    """Create a dataset with 15 carefully curated banking/credit card support examples.

    Each example has:
    - inputs: {"question": str}
    - outputs: {"expected_keywords": list[str], "expected_topics": list[str]}

    The expected outputs are used by evaluators to check retrieval accuracy.
    """

    client = Client()

    # Create dataset
    dataset_name = os.getenv("EVAL_DATASET_NAME", "kb-agent-golden-set")

    try:
        dataset = client.read_dataset(dataset_name=dataset_name)
        print(f"Dataset '{dataset_name}' already exists. Deleting...")
        client.delete_dataset(dataset_id=dataset.id)
    except:
        pass

    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description="Golden dataset for KB retrieval agent evaluation with 15 banking/credit card support examples"
    )

    # Golden examples - covering various banking topics
    examples = [
        # Payment processing questions
        {
            "inputs": {"question": "How do I make a payment on my credit card?"},
            "outputs": {
                "expected_keywords": ["payment", "online", "phone", "mail", "branch"],
                "expected_topics": ["payment processing", "payment methods"],
                "query_type": "payment_method"
            }
        },
        {
            "inputs": {"question": "How long does it take for a payment to process?"},
            "outputs": {
                "expected_keywords": ["payment", "processing", "1 business day", "5-7 days"],
                "expected_topics": ["payment processing"],
                "query_type": "payment_timing"
            }
        },
        {
            "inputs": {"question": "Can I set up automatic payments?"},
            "outputs": {
                "expected_keywords": ["automatic", "payment", "setup", "full balance", "minimum"],
                "expected_topics": ["automatic payment setup"],
                "query_type": "payment_automation"
            }
        },

        # Dispute and chargeback questions
        {
            "inputs": {"question": "How do I dispute a charge on my card?"},
            "outputs": {
                "expected_keywords": ["dispute", "charge", "60 days", "online", "phone"],
                "expected_topics": ["dispute process", "filing a dispute"],
                "query_type": "dispute_filing"
            }
        },
        {
            "inputs": {"question": "What is a chargeback and how long does it take?"},
            "outputs": {
                "expected_keywords": ["chargeback", "30-90 days", "investigation", "Fair Credit Billing Act"],
                "expected_topics": ["chargeback rights and timeline"],
                "query_type": "chargeback_process"
            }
        },

        # Rewards questions
        {
            "inputs": {"question": "How do I redeem my rewards points?"},
            "outputs": {
                "expected_keywords": ["rewards", "redeem", "cash back", "travel", "gift cards"],
                "expected_topics": ["rewards redemption options"],
                "query_type": "rewards_redemption"
            }
        },
        {
            "inputs": {"question": "Can I combine points from multiple cards?"},
            "outputs": {
                "expected_keywords": ["combine", "points", "transfer", "same account"],
                "expected_topics": ["combining and transferring points"],
                "query_type": "rewards_transfer"
            }
        },

        # Card activation
        {
            "inputs": {"question": "How do I activate my new credit card?"},
            "outputs": {
                "expected_keywords": ["activate", "mobile app", "online", "phone", "ATM"],
                "expected_topics": ["card activation"],
                "query_type": "activation"
            }
        },

        # Fraud and security
        {
            "inputs": {"question": "What should I do if my card is stolen?"},
            "outputs": {
                "expected_keywords": ["stolen", "report", "immediately", "fraud", "replacement"],
                "expected_topics": ["reporting lost or stolen cards"],
                "query_type": "fraud_stolen"
            }
        },
        {
            "inputs": {"question": "Am I liable for fraudulent charges?"},
            "outputs": {
                "expected_keywords": ["liability", "zero liability", "unauthorized", "fraud", "protection"],
                "expected_topics": ["zero liability protection"],
                "query_type": "fraud_liability"
            }
        },

        # Balance transfers
        {
            "inputs": {"question": "How long does a balance transfer take?"},
            "outputs": {
                "expected_keywords": ["balance transfer", "7-14 business days", "processing"],
                "expected_topics": ["balance transfer"],
                "query_type": "transfer_timing"
            }
        },

        # Credit limit questions
        {
            "inputs": {"question": "How do I request a credit limit increase?"},
            "outputs": {
                "expected_keywords": ["credit limit", "increase", "request", "online", "phone"],
                "expected_topics": ["credit limit increase"],
                "query_type": "credit_increase"
            }
        },

        # Statement questions
        {
            "inputs": {"question": "Where can I view my monthly statements?"},
            "outputs": {
                "expected_keywords": ["statements", "online banking", "mobile app", "download", "PDF"],
                "expected_topics": ["accessing account statements"],
                "query_type": "statements"
            }
        },

        # Interest and fees
        {
            "inputs": {"question": "How is interest calculated on my balance?"},
            "outputs": {
                "expected_keywords": ["interest", "APR", "average daily balance", "calculation"],
                "expected_topics": ["how credit card interest is calculated"],
                "query_type": "interest_calculation"
            }
        },

        # Account closure
        {
            "inputs": {"question": "What happens to my rewards if I close my account?"},
            "outputs": {
                "expected_keywords": ["rewards", "close", "account", "30 days", "redeem"],
                "expected_topics": ["account closure"],
                "query_type": "closure_rewards"
            }
        }
    ]

    # Add examples to dataset
    client.create_examples(
        dataset_id=dataset.id,
        examples=examples
    )

    print(f"Created dataset '{dataset_name}' with {len(examples)} examples")
    print(f"   Dataset ID: {dataset.id}")
    print(f"   View at: https://smith.langchain.com/datasets/{dataset.id}")

    return dataset


if __name__ == "__main__":
    # Verify LangSmith env vars are set
    if not os.getenv("LANGSMITH_API_KEY"):
        print("Error: LANGSMITH_API_KEY not set")
        print("   Set it with: export LANGSMITH_API_KEY=your_key")
        exit(1)

    create_golden_dataset()
