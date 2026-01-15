#!/bin/bash
# Test GitHub API access to liam-langchain/Chat-Repo

echo "🔍 Testing GitHub API access to liam-langchain/Chat-Repo"
echo ""
echo "================================================"
echo "Test 1: Check GitHub Token"
echo "================================================"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ GITHUB_TOKEN environment variable not set"
    echo ""
    echo "To set it:"
    echo "  export GITHUB_TOKEN=ghp_your_token_here"
    echo ""
    echo "Create a token at: https://github.com/settings/tokens/new"
    echo "Required scope: 'repo' (for private repositories)"
    exit 1
else
    echo "✅ GITHUB_TOKEN is set (length: ${#GITHUB_TOKEN})"
fi

echo ""
echo "================================================"
echo "Test 2: Access Repository Info"
echo "================================================"

response=$(curl -s -w "\n%{http_code}" \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    https://api.github.com/repos/liam-langchain/Chat-Repo)

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "200" ]; then
    echo "✅ Successfully accessed repository!"
    echo ""
    echo "Repository info:"
    echo "$body" | jq -r '. | "  Name: \(.name)\n  Private: \(.private)\n  Default Branch: \(.default_branch)"' 2>/dev/null || echo "$body" | head -5
elif [ "$http_code" = "404" ]; then
    echo "❌ Repository not found (404)"
    echo ""
    echo "Possible reasons:"
    echo "  1. Repository doesn't exist"
    echo "  2. Token doesn't have access to private repo"
    echo "  3. Token needs 'repo' scope"
elif [ "$http_code" = "401" ]; then
    echo "❌ Unauthorized (401) - Invalid token"
else
    echo "❌ Request failed with HTTP $http_code"
    echo "$body"
fi

echo ""
echo "================================================"
echo "Test 3: List Repository Contents"
echo "================================================"

response=$(curl -s -w "\n%{http_code}" \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    https://api.github.com/repos/liam-langchain/Chat-Repo/contents/)

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "200" ]; then
    echo "✅ Successfully listed repository contents!"
    echo ""
    echo "Root directory files:"
    echo "$body" | jq -r '.[] | "  - \(.name) (\(.type))"' 2>/dev/null || echo "$body" | head -10
elif [ "$http_code" = "404" ]; then
    echo "❌ Contents not found (404)"
else
    echo "❌ Request failed with HTTP $http_code"
    echo "$body"
fi

echo ""
echo "================================================"
echo "Test 4: Search Code"
echo "================================================"

response=$(curl -s -w "\n%{http_code}" \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/search/code?q=LangChain+repo:liam-langchain/Chat-Repo")

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "200" ]; then
    total_count=$(echo "$body" | jq -r '.total_count' 2>/dev/null)
    echo "✅ Code search successful!"
    echo "  Total results: $total_count"
elif [ "$http_code" = "403" ]; then
    echo "❌ Forbidden (403) - Code search might be disabled or rate limited"
elif [ "$http_code" = "404" ]; then
    echo "❌ Not found (404)"
else
    echo "❌ Request failed with HTTP $http_code"
    echo "$body"
fi

echo ""
echo "================================================"
echo "Summary & Next Steps"
echo "================================================"
echo ""
echo "If tests failed:"
echo "1. Ensure GITHUB_TOKEN has 'repo' scope"
echo "2. Verify the repository exists and is accessible"
echo "3. Check token at: https://github.com/settings/tokens"
echo ""
echo "For MCP configuration, the token should be set in:"
echo "  - Environment variable: GITHUB_TOKEN"
echo "  - Or in your MCP server configuration"
