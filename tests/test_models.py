import pytest

from astra.models import (
    CampaignDay,
    CampaignPlan,
    AnalyticsLogEntry,
    ContentPost,
    PerformanceRecord,
    ReplyDraft,
    SafetyAssessment,
    WorkflowContentItem,
    normalize_model_text,
)


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


def test_content_post_normalizes_ollama_list_and_object_text_fields() -> None:
    post = ContentPost.from_mapping(
        {
            "topic": ["Continuity Layer", "launch"],
            "hook": ["Stop re-explaining", "your project to AI."],
            "script_lines": [{"pain": "Agents start cold.", "fix": "Continuity packets keep context small."}],
            "caption": {"cta": "Try the beta", "price": "$19 early access"},
            "hashtags": ["#ai"],
            "platform_notes": ["Post as founder.", "Track objections."],
            "retention_check": ["Names the pain fast"],
            "suggested_post_time": "morning",
        }
    )

    assert post.topic == "Continuity Layer launch"
    assert post.hook == "Stop re-explaining your project to AI."
    assert post.script_lines == ["pain: Agents start cold.; fix: Continuity packets keep context small."]
    assert post.caption == "cta: Try the beta; price: $19 early access"
    assert post.platform_notes == "Post as founder. Track objections."
    assert post.retention_check == "Names the pain fast"


def test_model_text_normalization_rejects_empty_values_with_field_name() -> None:
    with pytest.raises(ValueError, match="hook cannot be empty"):
        normalize_model_text([], "hook")


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


def test_campaign_plan_and_reply_draft_normalize_ollama_text_shapes() -> None:
    plan = CampaignPlan.from_mapping(
        {
            "product": ["Continuity", "Layer"],
            "goal": {"launch": "$19 early access"},
            "summary": ["Use practical posts.", "Track replies."],
            "days": [
                {
                    "day": 1,
                    "channel": "reddit",
                    "angle": ["Ask builders", "about repeated context."],
                    "cta": {"primary": "GitHub", "secondary": "feedback form"},
                    "reply_focus": ["context loss", "setup requests"],
                    "objection_to_watch": {"docs": "Why not README?"},
                    "tracking_goal": ["replies", "clicks"],
                }
            ],
            "notes": {"approval": "draft-first"},
        }
    )
    reply = ReplyDraft.from_mapping(
        {
            "product": ["Continuity", "Layer"],
            "scenario": "skeptical_user",
            "user_signal": ["Is this just Notion?"],
            "reply": {"ack": "Fair question.", "answer": "Docs help, but agents need current packets."},
            "follow_up": ["What do you paste most often?"],
            "tracking_note": {"theme": "README objection"},
        }
    )

    assert plan.product == "Continuity Layer"
    assert plan.days[0].cta == "primary: GitHub; secondary: feedback form"
    assert plan.notes == "approval: draft-first"
    assert reply.reply == "ack: Fair question.; answer: Docs help, but agents need current packets."
    assert reply.tracking_note == "theme: README objection"


def test_campaign_day_normalizes_channel_aliases() -> None:
    aliases = {
        "bluesky": "x_bluesky",
        "x": "x_bluesky",
        "x/bluesky": "x_bluesky",
        "hn": "hacker_news",
        "Hacker News": "hacker_news",
        "dev.to": "devto",
        "email": "email_update",
    }

    for alias, expected in aliases.items():
        day = CampaignDay(
            day=1,
            channel=alias,
            angle="Ask for feedback.",
            cta="Open GitHub.",
            reply_focus="Builder pain.",
            objection_to_watch="Why now?",
            tracking_goal="Replies.",
        )
        assert day.channel == expected
