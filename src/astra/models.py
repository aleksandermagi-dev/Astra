from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


VALID_WORKFLOW_PLATFORMS = {
    "reddit",
    "x_bluesky",
    "indie_hackers",
    "hacker_news",
    "devto",
    "email_update",
    "direct_reply",
    "tiktok",
    "youtube_shorts",
}
VALID_IDEA_PLATFORMS = VALID_WORKFLOW_PLATFORMS | {"all"}
VALID_STATUSES = {"draft", "approved", "queued", "publishing", "posted", "failed"}
VALID_WORKFLOW_STAGES = {"master", "platform_variant"}
VALID_POST_TIME_SLOTS = {"morning", "afternoon", "evening"}
VALID_SAFETY_DECISIONS = {"PASS", "REWRITE", "DISCARD"}
VALID_SAFETY_DIMENSIONS = {"tone", "topic", "quality", "brand", "posting"}
VALID_REPLY_SCENARIOS = {"skeptical_user", "interested_builder", "setup_lead", "why_not_readme_notion"}

# Backward-compatible alias used by the older CLI/tests.
VALID_PLATFORMS = set(VALID_IDEA_PLATFORMS)


def _clean_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} cannot be empty.")
    return cleaned


def _normalize_lines(value: Any) -> list[str]:
    if isinstance(value, str):
        lines = [line.strip() for line in value.splitlines() if line.strip()]
    elif isinstance(value, list):
        lines = [_clean_string(item, "script line") for item in value if str(item).strip()]
    else:
        raise ValueError("script_lines must be a list of strings or a multiline string.")
    if not lines:
        raise ValueError("script_lines cannot be empty.")
    return lines


def _normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_tags = [part.strip() for part in value.replace(",", " ").split()]
    elif isinstance(value, list):
        raw_tags = [str(part).strip() for part in value]
    else:
        raise ValueError("hashtags must be a string, list, or null.")
    return [tag for tag in raw_tags if tag]


def _normalize_optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _clean_string(value, field_name)


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


@dataclass(slots=True)
class IdeaItem:
    rank: int
    topic: str
    reason: str

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError("rank must be >= 1.")
        self.topic = _clean_string(self.topic, "topic")
        self.reason = _clean_string(self.reason, "reason")

    @classmethod
    def from_mapping(cls, payload: dict[str, Any], rank: int | None = None) -> "IdeaItem":
        item_rank = rank if rank is not None else int(payload.get("rank", 0))
        return cls(
            rank=item_rank,
            topic=payload.get("topic", ""),
            reason=payload.get("reason", ""),
        )


@dataclass(slots=True)
class ContentPost:
    topic: str
    hook: str
    script_lines: list[str]
    caption: str
    tags: list[str] = field(default_factory=list)
    platform_notes: str | None = None
    retention_check: str = ""
    suggested_post_time: str = "afternoon"

    def __post_init__(self) -> None:
        self.topic = _clean_string(self.topic, "topic")
        self.hook = _clean_string(self.hook, "hook")
        self.script_lines = _normalize_lines(self.script_lines)
        self.caption = _clean_string(self.caption, "caption")
        self.tags = _normalize_tags(self.tags)
        if self.platform_notes is not None:
            self.platform_notes = _clean_string(self.platform_notes, "platform_notes")
        self.retention_check = _clean_string(self.retention_check, "retention_check")
        self.suggested_post_time = _clean_string(self.suggested_post_time, "suggested_post_time").lower()
        if len([chunk for chunk in self.retention_check.split(".") if chunk.strip()]) > 1:
            raise ValueError("retention_check must be one short sentence.")

    @property
    def hashtags(self) -> list[str]:
        return list(self.tags)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "ContentPost":
        script_value = payload.get("script_lines", payload.get("script", ""))
        return cls(
            topic=payload.get("topic", payload.get("TOPIC", "")),
            hook=payload.get("hook", payload.get("HOOK", "")),
            script_lines=script_value,
            caption=payload.get("caption", payload.get("CAPTION", "")),
            tags=payload.get("hashtags", payload.get("tags", payload.get("OPTIONAL TAGS", []))),
            platform_notes=payload.get("platform_notes", payload.get("PLATFORM NOTES")),
            retention_check=payload.get(
                "retention_check",
                payload.get("RETENTION CHECK", ""),
            ),
            suggested_post_time=payload.get("suggested_post_time", "afternoon"),
        )


@dataclass(slots=True)
class SafetyScorecard:
    hook_strength: int | None = None
    curiosity: int | None = None
    clarity: int | None = None
    tone_alignment: int | None = None
    safety_alignment: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("hook_strength", "curiosity", "clarity", "tone_alignment", "safety_alignment"):
            value = getattr(self, field_name)
            if value is not None and not 1 <= value <= 5:
                raise ValueError(f"{field_name} must be between 1 and 5.")

    @classmethod
    def from_mapping(cls, payload: Any) -> "SafetyScorecard":
        if isinstance(payload, cls):
            return payload
        data = payload if isinstance(payload, dict) else {}
        return cls(
            hook_strength=_coerce_int(data.get("hook_strength")),
            curiosity=_coerce_int(data.get("curiosity")),
            clarity=_coerce_int(data.get("clarity")),
            tone_alignment=_coerce_int(data.get("tone_alignment")),
            safety_alignment=_coerce_int(data.get("safety_alignment")),
        )


@dataclass(slots=True)
class SafetyAssessment:
    decision: str = "PASS"
    dimension_results: dict[str, str] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    scores: SafetyScorecard = field(default_factory=SafetyScorecard)
    rewrite_attempts: int = 0
    last_evaluated_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.decision = _clean_string(self.decision, "decision").upper()
        if self.decision not in VALID_SAFETY_DECISIONS:
            raise ValueError("decision must be PASS, REWRITE, or DISCARD.")
        normalized_results: dict[str, str] = {}
        for key, value in dict(self.dimension_results or {}).items():
            dimension = _clean_string(str(key), "dimension").lower()
            if dimension not in VALID_SAFETY_DIMENSIONS:
                raise ValueError(f"Unknown safety dimension '{dimension}'.")
            outcome = _clean_string(str(value), "dimension result").upper()
            if outcome not in VALID_SAFETY_DECISIONS:
                raise ValueError("dimension result must be PASS, REWRITE, or DISCARD.")
            normalized_results[dimension] = outcome
        self.dimension_results = normalized_results
        self.reasons = [_clean_string(reason, "reason") for reason in self.reasons]
        if self.rewrite_attempts < 0:
            raise ValueError("rewrite_attempts must be >= 0.")
        if not isinstance(self.scores, SafetyScorecard):
            self.scores = SafetyScorecard.from_mapping(self.scores)
        self.last_evaluated_at = _clean_string(self.last_evaluated_at, "last_evaluated_at")

    @classmethod
    def from_mapping(cls, payload: Any) -> "SafetyAssessment":
        if isinstance(payload, cls):
            return payload
        data = payload if isinstance(payload, dict) else {}
        return cls(
            decision=str(data.get("decision", "PASS")),
            dimension_results=dict(data.get("dimension_results", {})),
            reasons=list(data.get("reasons", [])),
            scores=SafetyScorecard.from_mapping(data.get("scores")),
            rewrite_attempts=int(data.get("rewrite_attempts", 0)),
            last_evaluated_at=str(data.get("last_evaluated_at", _utc_now_iso())),
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WorkflowContentItem:
    id: str
    topic: str
    hook: str
    script_lines: list[str]
    caption: str
    hashtags: list[str]
    platform: str
    suggested_post_time: str
    status: str
    created_at: str
    workflow_stage: str = "master"
    source_item_id: str | None = None
    platform_notes: str | None = None
    retention_check: str = ""
    safety: SafetyAssessment = field(default_factory=SafetyAssessment)

    def __post_init__(self) -> None:
        self.id = _clean_string(self.id, "id")
        self.topic = _clean_string(self.topic, "topic")
        self.hook = _clean_string(self.hook, "hook")
        self.script_lines = _normalize_lines(self.script_lines)
        self.caption = _clean_string(self.caption, "caption")
        self.hashtags = _normalize_tags(self.hashtags)
        self.platform = _clean_string(self.platform, "platform").lower()
        valid_platforms = VALID_WORKFLOW_PLATFORMS | {"master"}
        if self.platform not in valid_platforms:
            raise ValueError("platform must be master or a supported PR channel.")
        self.suggested_post_time = _clean_string(self.suggested_post_time, "suggested_post_time")
        self.status = _clean_string(self.status, "status").lower()
        if self.status not in VALID_STATUSES:
            raise ValueError("status must be draft, approved, queued, or posted.")
        self.created_at = _clean_string(self.created_at, "created_at")
        self.workflow_stage = _clean_string(self.workflow_stage, "workflow_stage").lower()
        if self.workflow_stage not in VALID_WORKFLOW_STAGES:
            raise ValueError("workflow_stage must be master or platform_variant.")
        self.source_item_id = _normalize_optional_string(self.source_item_id, "source_item_id")
        self.platform_notes = _normalize_optional_string(self.platform_notes, "platform_notes")
        self.retention_check = _clean_string(self.retention_check, "retention_check")
        if not isinstance(self.safety, SafetyAssessment):
            self.safety = SafetyAssessment.from_mapping(self.safety)
        if self.workflow_stage == "master" and self.platform != "master":
            raise ValueError("master items must use platform='master'.")
        if self.workflow_stage == "platform_variant" and self.platform == "master":
            raise ValueError("platform variants must target a supported PR channel.")
        if self.workflow_stage == "platform_variant" and not self.source_item_id:
            raise ValueError("platform variants must include source_item_id.")

    @classmethod
    def from_post(
        cls,
        post: ContentPost,
        *,
        platform: str = "master",
        workflow_stage: str = "master",
        source_item_id: str | None = None,
        status: str = "draft",
        created_at: str | None = None,
        item_id: str | None = None,
        safety: SafetyAssessment | None = None,
    ) -> "WorkflowContentItem":
        return cls(
            id=item_id or uuid4().hex[:8],
            topic=post.topic,
            hook=post.hook,
            script_lines=post.script_lines,
            caption=post.caption,
            hashtags=post.hashtags,
            platform=platform,
            suggested_post_time=post.suggested_post_time,
            status=status,
            created_at=created_at or _utc_now_iso(),
            workflow_stage=workflow_stage,
            source_item_id=source_item_id,
            platform_notes=post.platform_notes,
            retention_check=post.retention_check,
            safety=safety or SafetyAssessment(),
        )

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "WorkflowContentItem":
        return cls(
            id=payload.get("id", ""),
            topic=payload.get("topic", ""),
            hook=payload.get("hook", ""),
            script_lines=payload.get("script_lines", payload.get("script", "")),
            caption=payload.get("caption", ""),
            hashtags=payload.get("hashtags", payload.get("tags", [])),
            platform=payload.get("platform", ""),
            suggested_post_time=payload.get("suggested_post_time", ""),
            status=payload.get("status", ""),
            created_at=payload.get("created_at", ""),
            workflow_stage=payload.get("workflow_stage", "master"),
            source_item_id=payload.get("source_item_id"),
            platform_notes=payload.get("platform_notes"),
            retention_check=payload.get("retention_check", ""),
            safety=SafetyAssessment.from_mapping(payload.get("safety")),
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)

    def with_updates(self, **changes: Any) -> "WorkflowContentItem":
        payload = self.to_mapping()
        payload.update(changes)
        return WorkflowContentItem.from_mapping(payload)


@dataclass(slots=True)
class AnalyticsLogEntry:
    platform: str
    topic: str
    date_posted: str
    post_id_or_url: str
    views: float | None = None
    likes: float | None = None
    comments: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        self.platform = _clean_string(self.platform, "platform").lower()
        if self.platform not in VALID_WORKFLOW_PLATFORMS:
            raise ValueError("platform must be a supported PR channel.")
        self.topic = _clean_string(self.topic, "topic")
        self.date_posted = _clean_string(self.date_posted, "date_posted")
        self.post_id_or_url = _clean_string(self.post_id_or_url, "post_id_or_url")
        self.notes = str(self.notes or "").strip()

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "AnalyticsLogEntry":
        return cls(
            platform=payload.get("platform", ""),
            topic=payload.get("topic", ""),
            date_posted=payload.get("date_posted", ""),
            post_id_or_url=payload.get("post_id_or_url", payload.get("post_id", payload.get("url", ""))),
            views=_coerce_float(payload.get("views")),
            likes=_coerce_float(payload.get("likes")),
            comments=_coerce_float(payload.get("comments")),
            notes=str(payload.get("notes", "")),
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CampaignDay:
    day: int
    channel: str
    angle: str
    cta: str
    reply_focus: str
    objection_to_watch: str
    tracking_goal: str

    def __post_init__(self) -> None:
        if self.day < 1:
            raise ValueError("day must be >= 1.")
        self.channel = _clean_string(self.channel, "channel").lower()
        if self.channel not in VALID_WORKFLOW_PLATFORMS:
            raise ValueError("channel must be a supported PR channel.")
        self.angle = _clean_string(self.angle, "angle")
        self.cta = _clean_string(self.cta, "cta")
        self.reply_focus = _clean_string(self.reply_focus, "reply_focus")
        self.objection_to_watch = _clean_string(self.objection_to_watch, "objection_to_watch")
        self.tracking_goal = _clean_string(self.tracking_goal, "tracking_goal")

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "CampaignDay":
        return cls(
            day=int(payload.get("day", 0)),
            channel=str(payload.get("channel", "")),
            angle=str(payload.get("angle", "")),
            cta=str(payload.get("cta", "")),
            reply_focus=str(payload.get("reply_focus", "")),
            objection_to_watch=str(payload.get("objection_to_watch", "")),
            tracking_goal=str(payload.get("tracking_goal", "")),
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CampaignPlan:
    product: str
    goal: str
    summary: str
    days: list[CampaignDay]
    notes: str = ""

    def __post_init__(self) -> None:
        self.product = _clean_string(self.product, "product")
        self.goal = _clean_string(self.goal, "goal")
        self.summary = _clean_string(self.summary, "summary")
        if not self.days:
            raise ValueError("campaign plan must include at least one day.")
        self.days = [day if isinstance(day, CampaignDay) else CampaignDay.from_mapping(day) for day in self.days]
        self.notes = str(self.notes or "").strip()

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "CampaignPlan":
        return cls(
            product=str(payload.get("product", "")),
            goal=str(payload.get("goal", "")),
            summary=str(payload.get("summary", "")),
            days=[CampaignDay.from_mapping(item) for item in payload.get("days", [])],
            notes=str(payload.get("notes", "")),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "product": self.product,
            "goal": self.goal,
            "summary": self.summary,
            "days": [day.to_mapping() for day in self.days],
            "notes": self.notes,
        }


@dataclass(slots=True)
class ReplyDraft:
    product: str
    scenario: str
    user_signal: str
    reply: str
    follow_up: str
    tracking_note: str

    def __post_init__(self) -> None:
        self.product = _clean_string(self.product, "product")
        self.scenario = _clean_string(self.scenario, "scenario").lower()
        if self.scenario not in VALID_REPLY_SCENARIOS:
            raise ValueError("scenario must be a supported reply scenario.")
        self.user_signal = _clean_string(self.user_signal, "user_signal")
        self.reply = _clean_string(self.reply, "reply")
        self.follow_up = _clean_string(self.follow_up, "follow_up")
        self.tracking_note = _clean_string(self.tracking_note, "tracking_note")

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "ReplyDraft":
        return cls(
            product=str(payload.get("product", "")),
            scenario=str(payload.get("scenario", "")),
            user_signal=str(payload.get("user_signal", "")),
            reply=str(payload.get("reply", "")),
            follow_up=str(payload.get("follow_up", "")),
            tracking_note=str(payload.get("tracking_note", "")),
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MarketLogEntry:
    date: str = ""
    platform: str = ""
    post_url: str = ""
    angle: str = ""
    cta: str = ""
    replies: int = 0
    clicks: int = 0
    purchases: int = 0
    setup_requests: int = 0
    feedback_themes: str = ""
    objections: str = ""
    buyer_language: str = ""
    next_action: str = ""

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "MarketLogEntry":
        return cls(
            date=str(payload.get("date", "")),
            platform=str(payload.get("platform", "")),
            post_url=str(payload.get("post_url", payload.get("url", ""))),
            angle=str(payload.get("angle", "")),
            cta=str(payload.get("cta", "")),
            replies=int(payload.get("replies") or 0),
            clicks=int(payload.get("clicks") or 0),
            purchases=int(payload.get("purchases") or 0),
            setup_requests=int(payload.get("setup_requests") or 0),
            feedback_themes=str(payload.get("feedback_themes", "")),
            objections=str(payload.get("objections", "")),
            buyer_language=str(payload.get("buyer_language", "")),
            next_action=str(payload.get("next_action", "")),
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PublishResult:
    platform: str
    item_id: str
    status: str
    external_id: str = ""
    external_url: str = ""
    published_at: str = field(default_factory=_utc_now_iso)
    account_label: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        self.platform = _clean_string(self.platform, "platform").lower()
        self.item_id = _clean_string(self.item_id, "item_id")
        self.status = _clean_string(self.status, "status").lower()
        if self.status not in {"posted", "failed"}:
            raise ValueError("publish result status must be posted or failed.")
        self.external_id = str(self.external_id or "").strip()
        self.external_url = str(self.external_url or "").strip()
        self.published_at = _clean_string(self.published_at, "published_at")
        self.account_label = str(self.account_label or "").strip()
        self.error = str(self.error or "").strip()

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "PublishResult":
        return cls(
            platform=str(payload.get("platform", "")),
            item_id=str(payload.get("item_id", "")),
            status=str(payload.get("status", "")),
            external_id=str(payload.get("external_id", "")),
            external_url=str(payload.get("external_url", "")),
            published_at=str(payload.get("published_at", _utc_now_iso())),
            account_label=str(payload.get("account_label", "")),
            error=str(payload.get("error", "")),
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PerformanceRecord:
    topic: str
    hook: str
    platform: str
    views: float | None = None
    likes: float | None = None
    comments: float | None = None
    shares: float | None = None
    watch_time: float | None = None
    retention: float | None = None

    def __post_init__(self) -> None:
        self.topic = _clean_string(self.topic, "topic")
        self.hook = _clean_string(self.hook, "hook")
        self.platform = _clean_string(self.platform, "platform").lower()
        if self.platform not in VALID_WORKFLOW_PLATFORMS:
            raise ValueError("platform must be a supported PR channel.")

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "PerformanceRecord":
        return cls(
            topic=payload.get("topic", ""),
            hook=payload.get("hook", ""),
            platform=payload.get("platform", ""),
            views=_coerce_float(payload.get("views")),
            likes=_coerce_float(payload.get("likes")),
            comments=_coerce_float(payload.get("comments")),
            shares=_coerce_float(payload.get("shares")),
            watch_time=_coerce_float(payload.get("watch_time")),
            retention=_coerce_float(payload.get("retention")),
        )
