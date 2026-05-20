from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Iterable

from .models import ContentPost, SafetyAssessment, SafetyScorecard, WorkflowContentItem


STRONG_TOPIC_BLOCKERS = (
    "kill yourself",
    "suicide",
    "bomb",
    "how to make a bomb",
    "murder",
    "lynch",
    "terrorist",
    "ethnic cleansing",
)
REWRITE_TOPIC_FLAGS = (
    "cure",
    "guaranteed return",
    "inside stock",
    "hack people",
    "manipulate people",
    "medical advice",
    "panic",
    "collapse is coming",
)
TONE_DISCARD_FLAGS = (
    "wake up before it's too late",
    "everyone is lying to you",
    "they are controlling you",
    "you should be scared",
)
TONE_REWRITE_FLAGS = (
    "disaster",
    "terrifying",
    "everyone needs to",
    "you need to",
    "the truth is",
    "obviously",
    "rebellious",
    "aggressive",
    "chaotic",
    "urgent",
    "dramatic",
    "panic",
    "hype",
    "hypey",
    "game changer",
    "revolutionary",
)
BRAND_REWRITE_FLAGS = (
    "idiot",
    "stupid",
    "brainwashed",
    "nihilistic",
    "destroy the system",
    "rigged against you",
    "wake up",
    "sheeple",
    "quiet rebellion",
)
IDENTITY_REWRITE_FLAGS = (
    "in reality",
    "it is important to note",
    "studies show",
    "therefore",
    "in conclusion",
    "bro",
    "literally",
    "insane",
    "crazy",
    "mind-blowing",
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class AstraSafetyLayer:
    def evaluate_post(
        self,
        post: ContentPost,
        *,
        recent_items: Iterable[WorkflowContentItem] | None = None,
        rewrite_attempts: int = 0,
    ) -> SafetyAssessment:
        combined = " ".join([post.topic, post.hook, *post.script_lines, post.caption, post.platform_notes or ""]).lower()
        dimension_results: dict[str, str] = {}
        reasons: list[str] = []

        tone = self._evaluate_tone(combined)
        topic = self._evaluate_topic(combined)
        quality = self._evaluate_quality(post)
        brand = self._evaluate_brand(combined)
        posting = self._evaluate_posting(post, recent_items or [])

        for dimension, outcome, dimension_reasons in (tone, topic, quality, brand, posting):
            dimension_results[dimension] = outcome
            reasons.extend(dimension_reasons)

        decision = self._collapse_decision(dimension_results.values())
        scores = self._score_post(post, dimension_results)
        return SafetyAssessment(
            decision=decision,
            dimension_results=dimension_results,
            reasons=_dedupe(reasons),
            scores=scores,
            rewrite_attempts=rewrite_attempts,
            last_evaluated_at=_utc_now_iso(),
        )

    def evaluate_item(
        self,
        item: WorkflowContentItem,
        *,
        recent_items: Iterable[WorkflowContentItem] | None = None,
        rewrite_attempts: int | None = None,
    ) -> SafetyAssessment:
        post = ContentPost(
            topic=item.topic,
            hook=item.hook,
            script_lines=item.script_lines,
            caption=item.caption,
            tags=item.hashtags,
            platform_notes=item.platform_notes,
            retention_check=item.retention_check,
            suggested_post_time=item.suggested_post_time,
        )
        return self.evaluate_post(
            post,
            recent_items=recent_items,
            rewrite_attempts=item.safety.rewrite_attempts if rewrite_attempts is None else rewrite_attempts,
        )

    def apply_to_item(
        self,
        item: WorkflowContentItem,
        *,
        recent_items: Iterable[WorkflowContentItem] | None = None,
        rewrite_attempts: int | None = None,
    ) -> WorkflowContentItem:
        safety = self.evaluate_item(item, recent_items=recent_items, rewrite_attempts=rewrite_attempts)
        return item.with_updates(safety=safety)

    def _evaluate_tone(self, combined: str) -> tuple[str, str, list[str]]:
        reasons: list[str] = []
        if any(flag in combined for flag in TONE_DISCARD_FLAGS):
            reasons.append("Tone drifts into alarmist or destabilizing framing.")
            return ("tone", "DISCARD", reasons)
        if any(flag in combined for flag in TONE_REWRITE_FLAGS):
            reasons.append("Tone needs calmer, less hypey, less reactive phrasing.")
            return ("tone", "REWRITE", reasons)
        return ("tone", "PASS", reasons)

    def _evaluate_topic(self, combined: str) -> tuple[str, str, list[str]]:
        reasons: list[str] = []
        if any(flag in combined for flag in STRONG_TOPIC_BLOCKERS):
            reasons.append("Topic crosses into dangerous or harmful territory.")
            return ("topic", "DISCARD", reasons)
        if any(flag in combined for flag in REWRITE_TOPIC_FLAGS):
            reasons.append("Topic needs safer, higher-level framing.")
            return ("topic", "REWRITE", reasons)
        return ("topic", "PASS", reasons)

    def _evaluate_quality(self, post: ContentPost) -> tuple[str, str, list[str]]:
        reasons: list[str] = []
        combined = " ".join([post.hook, *post.script_lines, post.caption]).lower()
        hook_words = len(post.hook.split())
        avg_words = sum(len(line.split()) for line in post.script_lines) / len(post.script_lines)
        repeated_lines = [line for line, count in Counter(post.script_lines).items() if count > 1]
        if repeated_lines:
            reasons.append("Quality is repetitive.")
        if hook_words > 24:
            reasons.append("Hook is too long for a clear PR draft.")
        if avg_words > 45:
            reasons.append("Draft is too dense for a practical marketing asset.")
        if any(flag in combined for flag in ("in reality", "in conclusion", "the answer is", "the lesson is")):
            reasons.append("Quality drifts into over-explaining or lecture language.")
        if not any(
            phrase in combined
            for phrase in (
                "but",
                "what matters more is",
                "the part people miss is",
                "but that's not the full story",
                "pain",
                "problem",
                "feedback",
                "local-first",
                "beta",
                "trust",
                "setup",
                "github",
                "?",
            )
        ):
            reasons.append("Draft needs a clearer problem, contrast, or question.")
        if post.platform_notes is None or len(post.platform_notes.split()) < 4:
            reasons.append("Platform notes are too thin.")
        if reasons:
            return ("quality", "REWRITE", reasons)
        return ("quality", "PASS", reasons)

    def _evaluate_brand(self, combined: str) -> tuple[str, str, list[str]]:
        reasons: list[str] = []
        if any(flag in combined for flag in BRAND_REWRITE_FLAGS):
            reasons.append("Content feels off-brand for LinnuteeInnovations' practical builder voice.")
        if any(flag in combined for flag in IDENTITY_REWRITE_FLAGS):
            reasons.append("Content drifts away from Astra's plainspoken PR marketer identity.")
        if "!!" in combined or "???" in combined:
            reasons.append("Content feels too exaggerated for Astra's voice.")
        if reasons:
            return ("brand", "REWRITE", _dedupe(reasons))
        return ("brand", "PASS", reasons)

    def _evaluate_posting(
        self,
        post: ContentPost,
        recent_items: Iterable[WorkflowContentItem],
    ) -> tuple[str, str, list[str]]:
        reasons: list[str] = []
        topic_slug = post.topic.lower().strip()
        active_items = [item for item in recent_items if item.safety.decision != "DISCARD"]
        topic_matches = [item for item in active_items if item.topic.lower().strip() == topic_slug]
        if len(topic_matches) >= 2:
            reasons.append("Topic repetition is too high against recent content.")
        for item in active_items:
            similarity = SequenceMatcher(None, post.hook.lower(), item.hook.lower()).ratio()
            if similarity >= 0.82:
                reasons.append("Hook is too similar to a recent item.")
                break
        if reasons:
            return ("posting", "REWRITE", reasons)
        return ("posting", "PASS", reasons)

    def _collapse_decision(self, outcomes: Iterable[str]) -> str:
        values = list(outcomes)
        if "DISCARD" in values:
            return "DISCARD"
        if "REWRITE" in values:
            return "REWRITE"
        return "PASS"

    def _score_post(self, post: ContentPost, dimension_results: dict[str, str]) -> SafetyScorecard:
        hook_strength = max(1, min(5, 6 - max(1, len(post.hook.split()) // 3)))
        curiosity = 5 if any(token in " ".join(post.script_lines + [post.hook]).lower() for token in ("?", "but", "what if", "instead")) else 3
        clarity = 5 if max(len(line.split()) for line in post.script_lines) <= 10 else 3
        tone_alignment = 5 if dimension_results["tone"] == "PASS" and dimension_results["brand"] == "PASS" else 2
        safety_alignment = 5 if dimension_results["topic"] == "PASS" and dimension_results["posting"] == "PASS" else 2
        return SafetyScorecard(
            hook_strength=hook_strength,
            curiosity=curiosity,
            clarity=clarity,
            tone_alignment=tone_alignment,
            safety_alignment=safety_alignment,
        )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
