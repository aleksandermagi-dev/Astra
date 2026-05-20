from __future__ import annotations

import json
from pathlib import Path

from .models import CampaignPlan, ContentPost, IdeaItem, MarketLogEntry, ReplyDraft, WorkflowContentItem


def format_ideas_text(ideas: list[IdeaItem]) -> str:
    return "\n\n".join(f"{item.rank}. {item.topic}\n{item.reason}" for item in ideas)


def format_post_text(post: ContentPost) -> str:
    tags = " ".join(post.hashtags) if post.hashtags else "None"
    platform_notes = post.platform_notes or "None"
    script = "\n".join(post.script_lines)
    return (
        f"TOPIC:\n{post.topic}\n\n"
        f"HOOK:\n{post.hook}\n\n"
        f"SCRIPT:\n{script}\n\n"
        f"CAPTION:\n{post.caption}\n\n"
        f"HASHTAGS:\n{tags}\n\n"
        f"SUGGESTED POST TIME:\n{post.suggested_post_time}\n\n"
        f"PLATFORM NOTES:\n{platform_notes}\n\n"
        f"RETENTION CHECK:\n{post.retention_check}"
    )


def format_posts_text(posts: list[ContentPost]) -> str:
    return "\n\n---\n\n".join(format_post_text(post) for post in posts)


def format_posts_markdown(posts: list[ContentPost]) -> str:
    blocks: list[str] = []
    for index, post in enumerate(posts, start=1):
        tags = " ".join(post.hashtags) if post.hashtags else "None"
        platform_notes = post.platform_notes or "None"
        blocks.append(
            "\n".join(
                [
                    f"## Post {index}: {post.topic}",
                    "",
                    "**HOOK**  ",
                    post.hook,
                    "",
                    "**SCRIPT**  ",
                    "  \n".join(post.script_lines),
                    "",
                    "**CAPTION**  ",
                    post.caption,
                    "",
                    "**HASHTAGS**  ",
                    tags,
                    "",
                    "**SUGGESTED POST TIME**  ",
                    post.suggested_post_time,
                    "",
                    "**PLATFORM NOTES**  ",
                    platform_notes,
                    "",
                    "**RETENTION CHECK**  ",
                    post.retention_check,
                ]
            )
        )
    return "\n\n".join(blocks)


def format_posts_json(posts: list[ContentPost]) -> str:
    payload = [
        {
            "topic": post.topic,
            "hook": post.hook,
            "script_lines": post.script_lines,
            "caption": post.caption,
            "hashtags": post.hashtags,
            "platform_notes": post.platform_notes,
            "retention_check": post.retention_check,
            "suggested_post_time": post.suggested_post_time,
        }
        for post in posts
    ]
    return json.dumps(payload, indent=2)


def format_workflow_item_text(item: WorkflowContentItem) -> str:
    hashtags = " ".join(item.hashtags) if item.hashtags else "None"
    script = "\n".join(item.script_lines)
    platform_notes = item.platform_notes or "None"
    return (
        f"ID: {item.id}\n"
        f"TOPIC: {item.topic}\n"
        f"PLATFORM: {item.platform}\n"
        f"STAGE: {item.workflow_stage}\n"
        f"STATUS: {item.status}\n"
        f"SAFETY: {item.safety.decision}\n"
        f"SUGGESTED POST TIME: {item.suggested_post_time}\n"
        f"CREATED AT: {item.created_at}\n\n"
        f"HOOK:\n{item.hook}\n\n"
        f"SCRIPT:\n{script}\n\n"
        f"CAPTION:\n{item.caption}\n\n"
        f"HASHTAGS:\n{hashtags}\n\n"
        f"PLATFORM NOTES:\n{platform_notes}\n\n"
        f"RETENTION CHECK:\n{item.retention_check}\n\n"
        f"SAFETY REASONS:\n{'; '.join(item.safety.reasons) if item.safety.reasons else 'Aligned'}"
    )


def format_workflow_items_text(items: list[WorkflowContentItem]) -> str:
    return "\n\n---\n\n".join(format_workflow_item_text(item) for item in items)


def format_campaign_plan_markdown(plan: CampaignPlan) -> str:
    lines = [
        f"# {plan.product} Campaign",
        "",
        f"Goal: {plan.goal}",
        "",
        plan.summary,
        "",
        "| Day | Channel | Angle | CTA | Reply focus | Objection to watch | Tracking goal |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for day in plan.days:
        lines.append(
            f"| {day.day} | {day.channel} | {day.angle} | {day.cta} | {day.reply_focus} | {day.objection_to_watch} | {day.tracking_goal} |"
        )
    if plan.notes:
        lines.extend(["", f"Notes: {plan.notes}"])
    return "\n".join(lines)


def format_reply_draft_markdown(reply: ReplyDraft) -> str:
    return "\n".join(
        [
            f"# {reply.product} Reply Draft",
            "",
            f"Scenario: {reply.scenario}",
            "",
            "User signal:",
            reply.user_signal,
            "",
            "Reply:",
            reply.reply,
            "",
            "Follow-up:",
            reply.follow_up,
            "",
            "Tracking note:",
            reply.tracking_note,
        ]
    )


def format_feedback_summary(entries: list[MarketLogEntry]) -> str:
    if not entries:
        return "No market log entries found."
    replies = sum(entry.replies for entry in entries)
    clicks = sum(entry.clicks for entry in entries)
    purchases = sum(entry.purchases for entry in entries)
    setup_requests = sum(entry.setup_requests for entry in entries)
    objections = _top_text_fragments(entry.objections for entry in entries)
    buyer_language = _top_text_fragments(entry.buyer_language for entry in entries)
    next_actions = [entry.next_action for entry in entries if entry.next_action.strip()]
    return "\n".join(
        [
            "# Market Feedback Summary",
            "",
            f"Posts tracked: {len(entries)}",
            f"Replies: {replies}",
            f"Clicks: {clicks}",
            f"Purchases: {purchases}",
            f"Setup requests: {setup_requests}",
            "",
            "Top objections:",
            *[f"- {item}" for item in objections],
            "",
            "Buyer language:",
            *[f"- {item}" for item in buyer_language],
            "",
            "Next actions:",
            *[f"- {item}" for item in next_actions[:5]],
        ]
    )


def format_experiment_suggestions(entries: list[MarketLogEntry]) -> str:
    if not entries:
        return "No market log entries found."
    objections = _top_text_fragments(entry.objections for entry in entries)
    buyer_language = _top_text_fragments(entry.buyer_language for entry in entries)
    suggestions = [
        "Test one post that directly answers the most repeated objection.",
        "Turn the strongest buyer phrase into a headline or first line.",
        "Compare GitHub inspection CTA against feedback/setup form CTA.",
        "Ask one narrow setup question in replies to qualify serious builders.",
    ]
    return "\n".join(
        [
            "# Experiment Suggestions",
            "",
            "Signals used:",
            *[f"- Objection: {item}" for item in objections[:3]],
            *[f"- Buyer language: {item}" for item in buyer_language[:3]],
            "",
            "Suggested experiments:",
            *[f"- {item}" for item in suggestions],
        ]
    )


def format_queue_summary(items: list[WorkflowContentItem]) -> str:
    if not items:
        return "Queue is empty."
    return "\n".join(
        f"{item.id} | {item.platform} | {item.topic} | {item.suggested_post_time} | {item.status} | {item.safety.decision}"
        for item in items
    )


def write_output(path: str, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8")


def _top_text_fragments(values) -> list[str]:
    counts: dict[str, int] = {}
    for value in values:
        for part in str(value or "").replace(";", ",").split(","):
            cleaned = part.strip()
            if cleaned:
                counts[cleaned] = counts.get(cleaned, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [item for item, _ in ranked[:5]] or ["None recorded yet."]
