import pytest

from astra.models import CampaignDay, CampaignPlan, AnalyticsLogEntry, ContentPost, PerformanceRecord, ReplyDraft, SafetyAssessment, WorkflowContentItem


def test_content_post_from_mapping_splits_multiline_script() -> None:
    post = ContentPost.from_mapping(
        {
            "topic": "AI got useful",
            "hook": "AI isn't scary because it's smart",
            "script": "It got scary when it got useful.\nThat's when the leverage exploded.",
            "caption": "Useful beats impressive.",
            "retention_check": "The hook flips the expected angle immediately",
            "suggested_post_time": "morning",
        }
    )
    assert post.script_lines == [
        "It got scary when it got useful.",
        "That's when the leverage exploded.",
    ]


def test_workflow_content_item_requires_source_for_platform_variant() -> None:
    with pytest.raises(ValueError):
        WorkflowContentItem(
            id="item1234",
            topic="AI trust",
            hook="hook",
            script_lines=["line"],
            caption="caption",
            hashtags=["#ai"],
            platform="tiktok",
            suggested_post_time="afternoon",
            status="draft",
            created_at="2026-03-29T00:00:00Z",
            workflow_stage="platform_variant",
            retention_check="One sentence only",
        )


def test_analytics_log_entry_validates_platform() -> None:
    with pytest.raises(ValueError):
        AnalyticsLogEntry.from_mapping({"platform": "instagram", "topic": "X", "date_posted": "2026-03-29", "post_id_or_url": "abc"})


def test_analytics_log_entry_accepts_pr_channels() -> None:
    entry = AnalyticsLogEntry.from_mapping(
        {"platform": "reddit", "topic": "Continuity Layer", "date_posted": "2026-03-29", "post_id_or_url": "abc"}
    )
    assert entry.platform == "reddit"


def test_performance_record_validates_platform() -> None:
    with pytest.raises(ValueError):
        PerformanceRecord.from_mapping({"topic": "X", "hook": "Y", "platform": "instagram"})


def test_workflow_content_item_supports_persisted_safety_metadata() -> None:
    item = WorkflowContentItem.from_mapping(
        {
            "id": "item1234",
            "topic": "AI trust",
            "hook": "Useful looks harmless until it changes leverage.",
            "script_lines": ["Line one.", "Line two."],
            "caption": "Leverage changes the story.",
            "hashtags": ["#ai"],
            "platform": "tiktok",
            "suggested_post_time": "afternoon",
            "status": "draft",
            "created_at": "2026-03-29T00:00:00Z",
            "workflow_stage": "platform_variant",
            "source_item_id": "root1234",
            "retention_check": "The angle stays open enough to think about.",
            "safety": {
                "decision": "REWRITE",
                "dimension_results": {"tone": "PASS", "quality": "REWRITE"},
                "reasons": ["Hook is too long."],
                "scores": {"hook_strength": 3, "curiosity": 4, "clarity": 3, "tone_alignment": 5, "safety_alignment": 5},
                "rewrite_attempts": 1,
                "last_evaluated_at": "2026-03-30T12:00:00Z",
            },
        }
    )

    assert item.safety.decision == "REWRITE"
    assert item.safety.dimension_results["quality"] == "REWRITE"
    assert item.safety.scores.clarity == 3


def test_campaign_plan_and_reply_draft_models_validate_pr_shapes() -> None:
    plan = CampaignPlan(
        product="Continuity Layer",
        goal="Launch",
        summary="One week of practical founder posts.",
        days=[
            CampaignDay(
                day=1,
                channel="reddit",
                angle="Ask for context-loss stories.",
                cta="Inspect GitHub.",
                reply_focus="Workflow pain.",
                objection_to_watch="Why not docs?",
                tracking_goal="Replies.",
            )
        ],
    )
    assert plan.days[0].channel == "reddit"

    reply = ReplyDraft(
        product="Continuity Layer",
        scenario="skeptical_user",
        user_signal="Is this just Notion?",
        reply="Fair concern.",
        follow_up="What do you paste today?",
        tracking_note="Track docs objection.",
    )
    assert reply.scenario == "skeptical_user"
