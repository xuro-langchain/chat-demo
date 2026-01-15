#!/bin/bash
set -e

echo "Testing sync workflow locally..."

# Initialize git repos and set remotes if they don't exist
repos=(
  "deps/chat-repo/langchain/public/langchain:https://github.com/langchain-ai/langchain"
  "deps/chat-repo/langchain/public/langchain-mcp-adapters:https://github.com/langchain-ai/langchain-mcp-adapters"
  "deps/chat-repo/langgraph/public/langgraph:https://github.com/langchain-ai/langgraph"
  "deps/chat-repo/langgraph/public/langgraphjs:https://github.com/langchain-ai/langgraphjs"
  "deps/chat-repo/langsmith/public/langsmith-sdk:https://github.com/langchain-ai/langsmith-sdk"
)

echo "Step 1: Checking git repos..."
for repo_info in "${repos[@]}"; do
  path="${repo_info%%:*}"
  url="${repo_info##*:}"

  echo "  - $path"
  if [ ! -d "$path/.git" ]; then
    echo "    Initializing git repo..."
    cd "$path"
    git init
    git remote add origin "$url"
    cd - > /dev/null
  else
    echo "    ✓ Already initialized"
  fi
done

echo ""
echo "Step 2: Fetching and pulling latest changes..."

# Update langchain (uses master branch)
echo "  - langchain..."
cd deps/chat-repo/langchain/public/langchain
git fetch --depth=1 origin master
git reset --hard FETCH_HEAD
cd - > /dev/null

# Update langchain-mcp-adapters (uses main branch)
echo "  - langchain-mcp-adapters..."
cd deps/chat-repo/langchain/public/langchain-mcp-adapters
git fetch --depth=1 origin main
git reset --hard FETCH_HEAD
cd - > /dev/null

# Update langgraph (uses main branch)
echo "  - langgraph..."
cd deps/chat-repo/langgraph/public/langgraph
git fetch --depth=1 origin main
git reset --hard FETCH_HEAD
cd - > /dev/null

# Update langgraphjs (uses main branch)
echo "  - langgraphjs..."
cd deps/chat-repo/langgraph/public/langgraphjs
git fetch --depth=1 origin main
git reset --hard FETCH_HEAD
cd - > /dev/null

# Update langsmith-sdk (uses main branch)
echo "  - langsmith-sdk..."
cd deps/chat-repo/langsmith/public/langsmith-sdk
git fetch --depth=1 origin main
git reset --hard FETCH_HEAD
cd - > /dev/null

echo ""
echo "Step 3: Checking for changes..."
if [[ -n $(git status --porcelain) ]]; then
  echo "✓ Changes detected!"
  git status --short
else
  echo "✓ No changes (already up to date)"
fi

echo ""
echo "Test complete!"
