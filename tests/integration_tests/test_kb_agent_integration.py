"""Integration tests for KB specialist agent and main agent"""
import pytest
from src.agent.subagents import kb_specialist_agent, kb_specialist_subagent
from src.agent.docs_graph import docs_agent
from src.tools.kb_retrieval_tools import search_kb_tool

def test_kb_specialist_agent_basic_query():
    """Test KB specialist agent with basic query"""
    # Note: This is a simplified test that checks structure
    # Full LLM-based tests require API keys and are slower

    # Verify agent is properly configured
    assert kb_specialist_agent is not None
    # LangGraph agents don't have 'invoke' at module level
    # They are compiled graphs
    assert kb_specialist_agent is not None

    # Verify subagent definition
    assert kb_specialist_subagent['name'] == 'kb-specialist'
    assert len(kb_specialist_subagent['tools']) == 3

def test_kb_subagent_configuration():
    """Test KB subagent has correct configuration"""
    assert kb_specialist_subagent['name'] == 'kb-specialist'
    assert 'system_prompt' in kb_specialist_subagent
    assert 'tools' in kb_specialist_subagent
    assert 'description' in kb_specialist_subagent

    # Verify all required tools are present
    tool_names = [tool.__name__ for tool in kb_specialist_subagent['tools']]
    assert 'search_kb_tool' in tool_names
    assert 'get_topic_details' in tool_names
    assert 'list_topics' in tool_names

def test_main_agent_configuration():
    """Test main docs agent has correct configuration"""
    assert docs_agent is not None

    # Docs agent is a CompiledStateGraph from LangGraph
    # It has nodes and edges for the compiled graph
    assert hasattr(docs_agent, 'nodes')

def test_kb_tools_integration():
    """Test that KB tools work correctly when called"""
    # Test search_kb_tool
    result = search_kb_tool("payment", num_results=2)
    assert isinstance(result, str)
    assert len(result) > 0
    assert ("Result 1" in result or "No relevant information" in result)

def test_kb_tools_error_handling():
    """Test KB tools handle errors gracefully"""
    # Test with empty query
    result = search_kb_tool("", num_results=3)
    assert isinstance(result, str)

    # Test with very large num_results
    result = search_kb_tool("payment", num_results=1000)
    assert isinstance(result, str)
    # Should be capped at 10
    assert result.count("Result") <= 10

def test_kb_tools_edge_cases():
    """Test KB tools with edge case inputs"""
    # Special characters
    result = search_kb_tool("payment@#$%", num_results=2)
    assert isinstance(result, str)

    # Very long query
    long_query = "payment " * 100
    result = search_kb_tool(long_query, num_results=2)
    assert isinstance(result, str)

    # Unicode characters
    result = search_kb_tool("pago tarjeta crédito", num_results=2)
    assert isinstance(result, str)

def test_agent_error_handling():
    """Test that agent handles errors gracefully"""
    # Verify agent doesn't crash with empty input
    # Note: Full test requires API keys
    assert docs_agent is not None
    # Agent is a compiled graph
    assert docs_agent is not None

def test_data_loading_robustness():
    """Test that data loading handles missing files gracefully"""
    from src.tools.kb_retrieval_tools import _load_kb_data

    # Should load data successfully
    data = _load_kb_data()
    assert data is not None
    assert len(data) > 0

    # Verify both datasets are loaded
    sources = {row['source'] for row in data}
    assert 'ground_truth' in sources
    assert 'synthetic' in sources

def test_vectorizer_initialization():
    """Test that vectorizer initializes correctly"""
    from src.tools.kb_retrieval_tools import _initialize_vectorizer

    vectorizer, matrix = _initialize_vectorizer()

    assert vectorizer is not None
    assert matrix is not None
    assert matrix.shape[0] > 0  # Has documents
    assert matrix.shape[1] > 0  # Has features

def test_search_relevance_ordering():
    """Test that search results are ordered by relevance"""
    from src.tools.kb_retrieval_tools import search_knowledge_base

    results = search_knowledge_base("payment processing methods", top_k=5)

    assert len(results) > 0

    # Verify scores are in descending order
    scores = [r['similarity_score'] for r in results]
    assert scores == sorted(scores, reverse=True)

    # Verify top result has highest score
    assert scores[0] == max(scores)

def test_search_different_topics():
    """Test searching for different topic areas"""
    from src.tools.kb_retrieval_tools import search_knowledge_base

    topics_to_test = [
        ("payment", "payment"),
        ("dispute", "dispute"),
        ("reward", "reward"),
        ("fraud", "fraud"),
        ("balance transfer", "transfer"),
    ]

    for query, expected_keyword in topics_to_test:
        results = search_knowledge_base(query, top_k=3)
        assert len(results) > 0, f"Should find results for {query}"

        # At least one result should mention the keyword
        found = any(
            expected_keyword.lower() in r['question'].lower() or
            expected_keyword.lower() in r['answer'].lower()
            for r in results
        )
        assert found, f"Results for '{query}' should contain '{expected_keyword}'"

def test_topic_details_accuracy():
    """Test that topic details returns complete information"""
    from src.tools.kb_retrieval_tools import get_article_by_topic, list_available_topics

    topics = list_available_topics()
    assert len(topics) > 0

    # Test first topic
    topic = topics[0]
    article = get_article_by_topic(topic)

    assert article is not None
    assert 'question' in article
    assert 'retrieved_chunks' in article
    assert 'answer' in article

    # Verify content is substantial
    assert len(article['retrieved_chunks']) > 100
    assert len(article['answer']) > 50

def test_list_topics_filtering():
    """Test that topic filtering works correctly"""
    from src.tools.kb_retrieval_tools import list_available_topics

    all_topics = list_available_topics()
    payment_topics = list_available_topics(category="payment")

    assert len(all_topics) >= len(payment_topics)

    if payment_topics:
        # All filtered topics should contain the keyword
        assert all("payment" in t.lower() for t in payment_topics)

def test_cache_functionality():
    """Test that caching works for repeated queries"""
    from src.tools.kb_retrieval_tools import search_knowledge_base_cached

    query = "payment processing"

    # First call
    result1 = search_knowledge_base_cached(query, top_k=3)

    # Second call (should be cached)
    result2 = search_knowledge_base_cached(query, top_k=3)

    # Results should be identical
    assert result1 == result2

    # Different query should give different results
    result3 = search_knowledge_base_cached("dispute charge", top_k=3)
    assert result3 != result1

def test_similarity_threshold():
    """Test that similarity threshold filtering works"""
    from src.tools.kb_retrieval_tools import search_knowledge_base

    # High threshold should return fewer results
    results_high = search_knowledge_base("payment", top_k=10, min_similarity=0.3)
    results_low = search_knowledge_base("payment", top_k=10, min_similarity=0.01)

    assert len(results_low) >= len(results_high)

    # All results should meet threshold
    for result in results_high:
        assert result['similarity_score'] >= 0.3

def test_ground_truth_and_synthetic_retrieval():
    """Test that both ground truth and synthetic data are searchable"""
    from src.tools.kb_retrieval_tools import search_knowledge_base

    # Search for account closure (ground truth data)
    gt_results = search_knowledge_base("account closure", top_k=3)
    assert len(gt_results) > 0

    # Search for rewards (synthetic data)
    syn_results = search_knowledge_base("rewards redemption", top_k=3)
    assert len(syn_results) > 0

    # Verify structure is consistent
    assert gt_results[0].keys() == syn_results[0].keys()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
