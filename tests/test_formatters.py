from astra.formatters import format_post_text, format_posts_markdown, format_queue_summary, format_workflow_item_text
from astra.models import ContentPost, WorkflowContentItem


def _sample_post() -> ContentPost:
    return ContentPost(
        topic="Why humans hate silence",
        hook="Silence exposes the thoughts you're dodging",
        script_lines=["Most people don't fear noise.", "They fear what shows up without it."],
        caption="Your playlist might be emotional camouflage.",
        tags=["#philosophy", "#mindset"],
        platform_notes="TikTok version should cut faster after line one.",
        retention_check="The hook creates tension and the second line deepens it",
        suggested_post_time="evening",
    )


def _sample_item() -> WorkflowContentItem:
    return WorkflowContentItem(
        id="abcd1234",
        topic="Why humans hate silence",
        hook="Silence exposes the thoughts you're dodging",
        script_lines=["Most people don't fear noise.", "They fear what shows up without it."],
        caption="Your playlist might be emotional camouflage.",
        hashtags=["#philosophy", "#mindset"],
        platform="tiktok",
        suggested_post_time="2026-03-30T18:00",
        status="queued",
        created_at="2026-03-29T12:00:00Z",
        workflow_stage="platform_variant",
        source_item_id="root1234",
        platform_notes="TikTok version should cut faster after line one.",
        retention_check="The hook creates tension and the second line deepens it",
    )


def test_format_post_text_matches_required_sections() -> None:
    rendered = format_post_text(_sample_post())
    assert "TOPIC:" in rendered
    assert "HOOK:" in rendered
    assert "SCRIPT:" in rendered
    assert "HASHTAGS:" in rendered
    assert "RETENTION CHECK:" in rendered


def test_format_posts_markdown_renders_heading() -> None:
    rendered = format_posts_markdown([_sample_post()])
    assert "## Post 1:" in rendered
    assert "**CAPTION**" in rendered


def test_format_workflow_item_text_includes_status_and_platform() -> None:
    rendered = format_workflow_item_text(_sample_item())
    assert "STATUS: queued" in rendered
    assert "PLATFORM: tiktok" in rendered
    assert "SAFETY: PASS" in rendered


def test_format_queue_summary_lists_key_fields() -> None:
    rendered = format_queue_summary([_sample_item()])
    assert "abcd1234 | tiktok" in rendered
    assert "| PASS" in rendered
