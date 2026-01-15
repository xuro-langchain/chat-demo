# Exploratory Tests

This directory contains ad-hoc test scripts used for exploring and debugging features during development.

## Files

### API & Integration Testing
- `test_messages_endpoint.py` - Test different message endpoint variations for Pylon API
- `test_webhook.sh` - Test webhook functionality
- `test_all_tools.py` - Comprehensive test suite for all custom tools (Pylon + codebase)

### GitHub & MCP Testing
- `test_github_mcp_access.py` - Verify GitHub MCP access to liam-langchain/Chat-Repo
- `test_github_api_access.sh` - Test GitHub API access directly with curl

### Agent Testing
- `test_codebase_search.py` - Test the codebase search specialist agent

## Usage

These are exploratory scripts meant for manual testing and debugging. They are not part of the automated test suite.

Run individual scripts:
```bash
python tests/exploratory/test_all_tools.py
python tests/exploratory/test_github_mcp_access.py
bash tests/exploratory/test_github_api_access.sh
```
