#!/bin/bash
# Test Jewels Pylon webhook endpoint

# Check if LANGSMITH_API_KEY is set
if [ -z "$LANGSMITH_API_KEY" ]; then
    echo "Error: LANGSMITH_API_KEY environment variable is not set"
    exit 1
fi

# Configuration
DEPLOYMENT_URL="https://cs-deep-agent-d0e302e626015171bbff3ea73f931eb1.us.langgraph.app"
ENDPOINT="/pylon/jewels"

echo "🚀 Testing Jewels Pylon Webhook"
echo "================================"
echo ""

# Test ticket details
TICKET_ID="9109"
QUESTION="What is LangGraph and how does it work?"
EMAIL="liambush302@gmail.com"

echo "📋 Test Details:"
echo "  Ticket ID: $TICKET_ID"
echo "  Question: $QUESTION"
echo "  Email: $EMAIL"
echo ""

echo "🔄 Sending webhook request..."
echo ""

# Make the request
response=$(curl -s -X POST \
  -H "x-api-key: $LANGSMITH_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"issue_id\": \"$TICKET_ID\",
    \"issue_body\": \"$QUESTION\",
    \"requester_email\": \"$EMAIL\"
  }" \
  "$DEPLOYMENT_URL$ENDPOINT")

# Display response
echo "📥 Response:"
echo "$response" | jq '.'

# Check if successful
if echo "$response" | jq -e '.status == "success"' > /dev/null 2>&1; then
    echo ""
    echo "✅ Webhook test passed!"
    echo "Check ticket #$TICKET_ID in Pylon for the agent's response"
    exit 0
else
    echo ""
    echo "❌ Webhook test failed!"
    exit 1
fi
