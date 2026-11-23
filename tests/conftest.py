"""Test fixtures and configuration."""

import pytest


@pytest.fixture
def sample_feedback_data():
    """Sample feedback items for testing."""
    return [
        {
            "source_type": "manual",
            "source_id": "test",
            "dedupe_key": "test_1",
            "content": {
                "subject": "Can't export reports",
                "text": "I've been trying to export my monthly reports to PDF but the button doesn't work. This is really frustrating because I need to share these with my team every week. We're paying for the enterprise plan and this basic feature doesn't work."
            },
            "author": {"name": "Alice", "company": "Acme Corp", "segment": "enterprise"},
        },
        {
            "source_type": "manual",
            "source_id": "test",
            "dedupe_key": "test_2",
            "content": {
                "subject": "Feature request: Dark mode",
                "text": "Would love to have a dark mode option. I work late nights and the bright white screen is hard on my eyes. Several of my team members have also asked for this."
            },
            "author": {"name": "Bob", "segment": "smb"},
        },
        {
            "source_type": "manual",
            "source_id": "test",
            "dedupe_key": "test_3",
            "content": {
                "subject": None,
                "text": "Great product, keep it up!"
            },
            "author": {"name": "Charlie"},
        },
        {
            "source_type": "manual",
            "source_id": "test",
            "dedupe_key": "test_4",
            "content": {
                "subject": "Considering switching to competitor",
                "text": "We've been using your tool for 2 years but honestly the lack of API access is making us consider switching to CompetitorX. They offer a REST API that we can integrate with our internal tools. Our dev team has been asking for this for months."
            },
            "author": {"name": "Diana", "company": "BigCo", "segment": "enterprise", "mrr": 500.0},
        },
    ]


@pytest.fixture
def sample_extraction_response():
    """Sample LLM extraction response for testing."""
    return {
        "signals": [
            {
                "signalType": "bug_report",
                "summary": "PDF export button is not functional",
                "evidence": ["the button doesn't work", "I've been trying to export my monthly reports to PDF"],
                "implicitNeed": "User needs reliable report export functionality to share with team",
                "confidence": 0.9,
            },
            {
                "signalType": "complaint",
                "summary": "Enterprise customer frustrated with broken basic feature",
                "evidence": ["This is really frustrating", "We're paying for the enterprise plan and this basic feature doesn't work"],
                "implicitNeed": "Enterprise customers expect core features to work reliably",
                "confidence": 0.85,
            },
        ]
    }
