from __future__ import annotations

from astra.models import ContentPost, WorkflowContentItem
from astra.safety_layer import AstraSafetyLayer


def _post(**overrides) -> ContentPost:
    payload = {
        "topic": "Why attention drifts",
        "hook": "Attention should feel stronger now... but it doesn't.",
        "script_lines": [
            "More tools should make focus easier.",
            "Instead they train your brain to expect interruption.",
            "That shift is easy to miss until silence feels slower.",
        ],
        "caption": "Convenience can quietly change the pace of thought.",
        "tags": ["#focus"],
        "platform_notes": "Fast cuts. Highlight interruption.",
        "retention_check": "It opens with contrast and stays unresolved enough to think about.",
        "suggested_post_time": "afternoon",
    }
    payload.update(overrides)
    return ContentPost(**payload)


def _item(**overrides) -> WorkflowContentItem:
    payload = {
        "id": "item1234",
        "topic": "Why attention drifts",
        "hook": "Attention should feel stronger now... but it doesn't.",
        "script_lines": [
            "More tools should make focus easier.",
            "Instead they train your brain to expect interruption.",
            "That shift is easy to miss until silence feels slower.",
        ],
        "caption": "Convenience can quietly change the pace of thought.",
        "hashtags": ["#focus"],
        "platform": "tiktok",
        "suggested_post_time": "afternoon",
        "status": "approved",
        "created_at": "2026-03-30T12:00:00Z",
        "workflow_stage": "platform_variant",
        "source_item_id": "root1234",
        "platform_notes": "Fast cuts. Highlight interruption.",
        "retention_check": "It opens with contrast and stays unresolved enough to think about.",
    }
    payload.update(overrides)
    return WorkflowContentItem.from_mapping(payload)


def test_safety_layer_marks_mild_tone_issue_for_rewrite() -> None:
    safety = AstraSafetyLayer().evaluate_post(
        _post(script_lines=["This looks normal.", "But the truth is you should be worried."])
    )

    assert safety.decision == "REWRITE"
    assert safety.dimension_results["tone"] == "REWRITE"


def test_safety_layer_discards_strong_topic_violation() -> None:
    safety = AstraSafetyLayer().evaluate_post(_post(hook="Here is how to make a bomb.", caption="Chaos sells."))

    assert safety.decision == "DISCARD"
    assert safety.dimension_results["topic"] == "DISCARD"


def test_safety_layer_rewrites_weak_quality() -> None:
    safety = AstraSafetyLayer().evaluate_post(
        _post(
            hook="This is a very long generic hook that keeps explaining the point instead of creating tension fast",
            script_lines=["In reality the answer is simple and everyone should follow it immediately."],
            platform_notes="calm",
        )
    )

    assert safety.dimension_results["quality"] == "REWRITE"


def test_safety_layer_rewrites_off_brand_content() -> None:
    safety = AstraSafetyLayer().evaluate_post(
        _post(caption="Destroy the system before it destroys you.")
    )

    assert safety.dimension_results["brand"] == "REWRITE"


def test_safety_layer_rewrites_academic_or_robotic_identity_drift() -> None:
    safety = AstraSafetyLayer().evaluate_post(
        _post(
            script_lines=["It is important to note that studies show a measurable effect."],
            caption="Therefore the result is obvious.",
        )
    )

    assert safety.dimension_results["brand"] == "REWRITE"


def test_safety_layer_rewrites_exaggerated_identity_drift() -> None:
    safety = AstraSafetyLayer().evaluate_post(
        _post(hook="This changes everything!!!", caption="This is literally mind-blowing.")
    )

    assert safety.dimension_results["brand"] == "REWRITE"


def test_safety_layer_flags_recent_post_repetition() -> None:
    recent = [
        _item(id="item1", topic="Why attention drifts", hook="Attention should feel stronger now... but it doesn't."),
        _item(id="item2", topic="Why attention drifts", hook="Attention should feel stronger now... but it doesn't."),
    ]

    safety = AstraSafetyLayer().evaluate_post(_post(), recent_items=recent)

    assert safety.dimension_results["posting"] == "REWRITE"
