"""Tests for Pydantic models."""

from signal_miner.models import AssetStatus, ProcessingState, SignalType, new_id
from signal_miner.models.assets import (
    PriorityScore,
    RequirementAsset,
    UserStory,
)
from signal_miner.models.feedback import (
    ExtractionResult,
    FeedbackAuthor,
    FeedbackContent,
    PipelineRun,
    RawFeedback,
    Signal,
)


class TestIdGeneration:
    def test_new_id_with_prefix(self):
        result = new_id("rfb")
        assert result.startswith("rfb_")
        assert len(result) > 4

    def test_new_id_without_prefix(self):
        result = new_id()
        assert "_" not in result
        assert len(result) == 20

    def test_unique_ids(self):
        ids = {new_id("test") for _ in range(100)}
        assert len(ids) == 100


class TestRawFeedback:
    def test_create_minimal(self):
        fb = RawFeedback(
            source_type="manual",
            source_id="test",
            dedupe_key="abc",
            content=FeedbackContent(text="some feedback"),
        )
        assert fb.source_type == "manual"
        assert fb.content.text == "some feedback"
        assert fb.processing_state == ProcessingState.PENDING
        assert fb.id.startswith("rfb_")

    def test_create_with_author(self):
        fb = RawFeedback(
            source_type="csv",
            source_id="import_1",
            dedupe_key="xyz",
            content=FeedbackContent(subject="Bug", text="It crashes"),
            author=FeedbackAuthor(name="Alice", company="Acme", segment="enterprise", mrr=500.0),
        )
        assert fb.author.name == "Alice"
        assert fb.author.mrr == 500.0


class TestSignal:
    def test_create(self):
        sig = Signal(
            raw_feedback_id="rfb_123",
            signal_type=SignalType.FEATURE_REQUEST,
            summary="User wants dark mode",
            evidence=["I want dark mode"],
            implicit_need="Reduce eye strain during night use",
            confidence=0.85,
        )
        assert sig.signal_type == SignalType.FEATURE_REQUEST
        assert sig.confidence == 0.85
        assert sig.id.startswith("sig_")


class TestPipelineRun:
    def test_immutable(self):
        run = PipelineRun(step="extraction", status="running", progress=0.5, message="Working...")
        # Frozen model — should not allow mutation
        try:
            run.progress = 0.8
            raise AssertionError("Should have raised")
        except Exception:
            pass

    def test_to_event_payload(self):
        run = PipelineRun(step="extraction", status="running", progress=0.5, message="Working...")
        payload = run.to_event_payload()
        assert payload["step"] == "extraction"
        assert payload["progress"] == 0.5
        assert "run_id" in payload


class TestExtractionResult:
    def test_parse(self, sample_extraction_response):
        result = ExtractionResult.model_validate(sample_extraction_response)
        assert len(result.signals) == 2
        assert result.signals[0].signalType == "bug_report"
        assert result.signals[0].confidence == 0.9


class TestAssetModels:
    def test_user_story_str(self):
        story = UserStory(role="PM", action="export reports", benefit="I can share with stakeholders")
        assert "As a PM" in str(story)

    def test_priority_score(self):
        score = PriorityScore(frequency=0.8, severity=0.9, confidence=0.7)
        assert score.frequency == 0.8

    def test_requirement_asset(self):
        req = RequirementAsset(
            title="PDF Export Fix",
            user_stories=[UserStory(role="user", action="export to PDF", benefit="I can share reports")],
            acceptance_criteria=["PDF generates successfully", "File size < 10MB"],
            decision_reasoning="High-severity bug affecting enterprise customers with $500+ MRR",
        )
        assert req.id.startswith("req_")
        assert len(req.acceptance_criteria) == 2
        assert req.status == AssetStatus.DRAFT
