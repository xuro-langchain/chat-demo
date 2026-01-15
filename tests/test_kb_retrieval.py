"""Tests for KB retrieval tools"""
import pytest
from src.tools.kb_retrieval_tools import (
    search_knowledge_base,
    get_article_by_topic,
    list_available_topics,
    search_kb_tool,
    get_topic_details,
    list_topics
)

def test_load_kb_data():
    """Test that KB data loads successfully from both datasets"""
    results = search_knowledge_base("payment", top_k=1)
    assert len(results) > 0, "Should load data from CSV files"
    assert 'question' in results[0]
    assert 'retrieved_chunks' in results[0]
    assert 'answer' in results[0]

def test_search_knowledge_base():
    """Test basic search functionality"""
    # Search for payment-related topics
    results = search_knowledge_base("payment processing", top_k=5)

    assert len(results) > 0, "Should find payment-related results"
    assert all('similarity_score' in r for r in results), "All results should have similarity scores"

    # Verify results are sorted by relevance
    scores = [r['similarity_score'] for r in results]
    assert scores == sorted(scores, reverse=True), "Results should be sorted by similarity"

def test_search_with_min_similarity():
    """Test filtering by minimum similarity"""
    # Search with high threshold
    results = search_knowledge_base("xyz123nonsense", top_k=5, min_similarity=0.3)

    # Should return empty or very few results for nonsense query
    assert len(results) < 3, "Nonsense query should return few results"

def test_get_article_by_topic():
    """Test retrieving specific article"""
    # Get list of topics first
    topics = list_available_topics()
    assert len(topics) > 0, "Should have topics available"

    # Get first topic
    topic = topics[0]
    article = get_article_by_topic(topic)

    assert article is not None, f"Should find article for topic: {topic}"
    assert article['question'] == topic
    assert 'retrieved_chunks' in article
    assert 'answer' in article

def test_list_available_topics():
    """Test listing topics"""
    all_topics = list_available_topics()

    assert len(all_topics) > 0, "Should have topics available"
    assert all(isinstance(t, str) for t in all_topics), "All topics should be strings"

    # Test category filtering
    payment_topics = list_available_topics(category="payment")
    assert len(payment_topics) > 0, "Should have payment-related topics"
    assert all("payment" in t.lower() for t in payment_topics), "Filtered topics should contain keyword"

def test_search_kb_tool():
    """Test the LLM tool function"""
    result = search_kb_tool("how to make a payment", num_results=3)

    assert isinstance(result, str), "Tool should return string"
    assert len(result) > 0, "Tool should return non-empty result"
    assert "Result 1" in result or "No relevant information" in result, "Should have formatted results"

def test_get_topic_details_tool():
    """Test the topic details tool"""
    # Get a valid topic first
    topics = list_available_topics()
    topic = topics[0]

    result = get_topic_details(topic)

    assert isinstance(result, str), "Tool should return string"
    assert topic in result, "Result should include topic name"
    assert len(result) > 100, "Result should have substantial content"

def test_list_topics_tool():
    """Test the list topics tool"""
    result = list_topics()

    assert isinstance(result, str), "Tool should return string"
    assert "Available topics" in result, "Should have header"
    assert "Total:" in result, "Should have count"

def test_list_topics_with_category():
    """Test listing topics with category filter"""
    result = list_topics(category="dispute")

    assert isinstance(result, str), "Tool should return string"
    if "No topics found" not in result:
        assert "dispute" in result.lower(), "Should have dispute-related topics"

def test_search_across_both_datasets():
    """Test that search works across both ground truth and synthetic data"""
    # Search for account closure (ground truth data)
    results_gt = search_knowledge_base("account closure", top_k=5)

    # Search for rewards (synthetic data)
    results_syn = search_knowledge_base("rewards redemption", top_k=5)

    assert len(results_gt) > 0, "Should find ground truth data"
    assert len(results_syn) > 0, "Should find synthetic data"

    # Both should have same structure
    assert results_gt[0].keys() == results_syn[0].keys(), "Results should have same structure"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
