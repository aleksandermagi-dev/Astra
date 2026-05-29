from __future__ import annotations

import json
from typing import Any, Protocol
from urllib import error as urlerror
from urllib import request as urlrequest

from openai import OpenAI

from .config import AstraConfig
from .models import CampaignPlan, ContentPost, IdeaItem, ReplyDraft, SafetyAssessment, WorkflowContentItem
from .prompts import (
    build_batch_prompt,
    build_campaign_prompt,
    build_format_prompt,
    build_ideas_prompt,
    build_posts_prompt,
    build_reply_prompt,
    build_rewrite_prompt,
    build_system_prompt,
)
from .safety_layer import AstraSafetyLayer


class ResponseTransport(Protocol):
    def __call__(self, *, system_prompt: str, user_prompt: str, model: str) -> str: ...


def openai_transport(*, system_prompt: str, user_prompt: str, model: str) -> str:
    client = OpenAI()
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    parts: list[str] = []
    for item in getattr(response, "output", []):
        for content in getattr(item, "content", []):
            text = getattr(content, "text", None)
            if text:
                parts.append(text)
    return "\n".join(parts)


def ollama_transport_factory(*, base_url: str, ollama_model: str) -> ResponseTransport:
    def transport(*, system_prompt: str, user_prompt: str, model: str) -> str:
        prompt = "\n\n".join(
            [
                "System:",
                system_prompt.strip(),
                "User:",
                user_prompt.strip(),
                "Return only valid JSON. Do not wrap the JSON in Markdown.",
            ]
        )
        payload = {
            "model": ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        request = urlrequest.Request(
            f"{base_url.rstrip('/')}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlrequest.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urlerror.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace").strip()
            detail = f" Ollama said: {body}" if body else ""
            raise RuntimeError(
                f"Ollama returned HTTP {exc.code} at {base_url}.{detail} "
                f"Open Ollama or run `ollama serve`, and make sure `{ollama_model}` is installed."
            ) from exc
        except (OSError, urlerror.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Ollama is not reachable at {base_url}. Open Ollama or run `ollama serve`, "
                f"and make sure `{ollama_model}` is installed."
            ) from exc
        text = str(data.get("response") or "").strip()
        if not text:
            raise RuntimeError("Ollama returned an empty response.")
        return text

    return transport


def default_transport_for_config(config: AstraConfig) -> ResponseTransport:
    if config.active_provider == "ollama":
        return ollama_transport_factory(base_url=config.ollama_url, ollama_model=config.ollama_model)
    return openai_transport


# Backward-compatible name for callers that import the original transport.
default_transport = openai_transport


class AstraGenerator:
    def __init__(self, config: AstraConfig, transport: ResponseTransport | None = None) -> None:
        self.config = config
        self.transport = transport or default_transport_for_config(config)
        self.safety_layer = AstraSafetyLayer()

    def generate_ideas(
        self,
        *,
        topic: str | None,
        count: int,
        platform: str,
    ) -> list[IdeaItem]:
        payload = self._request_json(build_ideas_prompt(topic, count, platform))
        ideas = payload.get("ideas", [])
        return [IdeaItem.from_mapping(item, rank=index) for index, item in enumerate(ideas, start=1)]

    def generate_posts(
        self,
        *,
        topic: str,
        count: int,
        rewrite: bool = True,
    ) -> list[ContentPost]:
        payload = self._request_json(build_batch_prompt(topic, count))
        posts = [ContentPost.from_mapping(item) for item in payload.get("posts", [])]
        if rewrite:
            posts = [self._stabilize_post(post)[0] for post in posts]
        return posts

    def generate_workflow_items(
        self,
        *,
        topic: str,
        count: int,
        recent_items: list[WorkflowContentItem] | None = None,
    ) -> list[WorkflowContentItem]:
        payload = self._request_json(build_batch_prompt(topic, count))
        posts = [ContentPost.from_mapping(item) for item in payload.get("posts", [])]
        items: list[WorkflowContentItem] = []
        for post in posts:
            stable_post, safety = self._stabilize_post(post, recent_items=recent_items)
            item = WorkflowContentItem.from_post(
                stable_post,
                platform="master",
                workflow_stage="master",
                safety=safety,
            )
            items.append(item)
        return items

    def generate_campaign_plan(self, *, goal: str, days: int = 7) -> CampaignPlan:
        payload = self._request_json(build_campaign_prompt(goal, self.config.active_product, days=days))
        return CampaignPlan.from_mapping(payload)

    def draft_product_posts(
        self,
        *,
        channel: str,
        count: int,
        goal: str | None = None,
        recent_items: list[WorkflowContentItem] | None = None,
    ) -> list[WorkflowContentItem]:
        payload = self._request_json(build_posts_prompt(self.config.active_product, channel, count, goal=goal))
        posts = [ContentPost.from_mapping(item) for item in payload.get("posts", [])]
        items: list[WorkflowContentItem] = []
        for post in posts:
            stable_post, safety = self._stabilize_post(post, recent_items=recent_items)
            items.append(
                WorkflowContentItem.from_post(
                    stable_post,
                    platform=channel,
                    workflow_stage="platform_variant",
                    source_item_id="product-profile",
                    safety=safety,
                )
            )
        return items

    def draft_reply(self, *, scenario: str, user_signal: str | None = None) -> ReplyDraft:
        payload = self._request_json(build_reply_prompt(self.config.active_product, scenario, user_signal=user_signal))
        return ReplyDraft.from_mapping(payload)

    def format_for_platform(
        self,
        item: WorkflowContentItem,
        platform: str,
        *,
        recent_items: list[WorkflowContentItem] | None = None,
    ) -> WorkflowContentItem:
        payload = self._request_json(build_format_prompt(_workflow_item_to_dict(item), platform))
        post, safety = self._stabilize_post(ContentPost.from_mapping(payload), recent_items=recent_items)
        return WorkflowContentItem.from_post(
            post,
            platform=platform,
            workflow_stage="platform_variant",
            source_item_id=item.id,
            safety=safety,
        )

    def assess_item(
        self,
        item: WorkflowContentItem,
        *,
        recent_items: list[WorkflowContentItem] | None = None,
    ) -> WorkflowContentItem:
        return item.with_updates(safety=self.safety_layer.evaluate_item(item, recent_items=recent_items))

    def _stabilize_post(
        self,
        post: ContentPost,
        *,
        recent_items: list[WorkflowContentItem] | None = None,
    ) -> tuple[ContentPost, SafetyAssessment]:
        safety = self.safety_layer.evaluate_post(post, recent_items=recent_items)
        if safety.decision == "PASS":
            return post, safety
        if safety.decision == "DISCARD":
            return post, safety
        rewritten = self._rewrite_post(post, safety)
        rewritten_safety = self.safety_layer.evaluate_post(
            rewritten,
            recent_items=recent_items,
            rewrite_attempts=safety.rewrite_attempts + 1,
        )
        if rewritten_safety.decision == "REWRITE":
            rewritten_safety = SafetyAssessment.from_mapping(
                {
                    **rewritten_safety.to_mapping(),
                    "decision": "DISCARD",
                    "reasons": [*rewritten_safety.reasons, "Rewrite did not clear the safety gate."],
                }
            )
        return rewritten, rewritten_safety

    def _rewrite_post(self, post: ContentPost, safety: SafetyAssessment) -> ContentPost:
        payload = self._request_json(build_rewrite_prompt(_post_to_dict(post), safety_reasons=safety.reasons))
        return ContentPost.from_mapping(payload)

    def _request_json(self, user_prompt: str) -> dict[str, Any]:
        raw = self.transport(
            system_prompt=build_system_prompt(self.config),
            user_prompt=user_prompt,
            model=self.config.active_generation_model,
        )
        try:
            return json.loads(_extract_json(raw))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model response was not valid JSON: {raw}") from exc


def _extract_json(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return cleaned


def _looks_weak(post: ContentPost) -> bool:
    hook_words = len(post.hook.split())
    avg_line_words = sum(len(line.split()) for line in post.script_lines) / len(post.script_lines)
    combined = " ".join([post.hook, *post.script_lines, post.caption]).lower()
    flat_cues = (
        "in reality",
        "the truth is",
        "this means",
        "in conclusion",
        "the answer is",
        "you should",
        "the lesson is",
        "this proves",
    )
    preachy_cues = (
        "you need to",
        "you have to",
        "stop doing",
        "start doing",
    )
    too_conclusive = any(cue in combined for cue in flat_cues)
    too_preachy = any(cue in combined for cue in preachy_cues)
    no_open_loop = not any(
        cue in combined
        for cue in (
            "but here's",
            "that's not the weird part",
            "it gets stranger",
            "what if",
            "?",
        )
    )
    weak_platform_notes = post.platform_notes is None or len(post.platform_notes.split()) < 4
    bad_platform_note_tone = post.platform_notes is not None and any(
        cue in post.platform_notes.lower()
        for cue in ("rebellious", "aggressive", "chaotic", "fear", "alarmist")
    )
    summary_caption = post.caption.lower().startswith("this is about") or post.caption.lower().startswith("the point is")
    return (
        hook_words > 12
        or avg_line_words > 10
        or len(post.caption.split()) > 18
        or too_conclusive
        or too_preachy
        or no_open_loop
        or weak_platform_notes
        or bad_platform_note_tone
        or summary_caption
    )


def _post_to_dict(post: ContentPost) -> dict[str, Any]:
    return {
        "topic": post.topic,
        "hook": post.hook,
        "script_lines": post.script_lines,
        "caption": post.caption,
        "hashtags": post.hashtags,
        "platform_notes": post.platform_notes,
        "retention_check": post.retention_check,
        "suggested_post_time": post.suggested_post_time,
    }


def _workflow_item_to_dict(item: WorkflowContentItem) -> dict[str, Any]:
    return {
        "topic": item.topic,
        "hook": item.hook,
        "script_lines": item.script_lines,
        "caption": item.caption,
        "hashtags": item.hashtags,
        "platform_notes": item.platform_notes,
        "retention_check": item.retention_check,
        "suggested_post_time": item.suggested_post_time,
    }
