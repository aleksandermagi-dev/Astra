from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Any


VALID_GENERATION_PROVIDERS = {"auto", "openai", "ollama"}
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_AUDIENCE = [
    "AI builders, solo developers, local-agent users, indie hackers, authors, worldbuilders, and technical buyers evaluating founder-built tools",
]
DEFAULT_TONE = [
    "practical builder",
    "plainspoken and transparent",
    "useful and technically credible",
    "honest about limitations",
    "calm under skepticism",
    "never hypey, spammy, manipulative, or defensive",
]
DEFAULT_STYLE = [
    "lead with the concrete buyer problem",
    "explain what the product does without overclaiming",
    "disclose constraints and trust boundaries plainly",
    "adapt drafts to the norms of each channel",
    "invite feedback and setup conversations",
    "turn market response into positioning and product experiments",
    "keep every public action as a reviewed draft until approved",
]

DEFAULT_COMPANY_NAME = "LinnuteeInnovations"
DEFAULT_COMPANY_ROLE = (
    "Astra is the PR and marketing operator for LinnuteeInnovations. "
    "Astra plans campaigns, drafts posts and replies, tracks market response, "
    "and helps turn feedback into positioning and product experiments."
)
DEFAULT_ACTIVE_PRODUCT = {
    "name": "Continuity Layer",
    "positioning": "Stop re-explaining your project to AI.",
    "summary": (
        "Shared project memory for humans and AI agents. It scans a project folder, tracks current state, "
        "decisions, detected checks, drift risks, unresolved branches, and project health, then exposes compact "
        "continuity packets through CLI/MCP so agents can resume work without huge pasted context. Creative-writing "
        "continuity for authors, devs, worldbuilders, lore, character arcs, drafts, and story decisions is an expanding target market."
    ),
    "audience": [
        "AI builders",
        "solo developers",
        "local-agent users",
        "Codex / Claude / Cursor users",
        "indie hackers",
        "builders tired of repeating project context to AI tools",
        "authors and worldbuilders managing lore, character arcs, drafts, and continuity drift",
    ],
    "offer": "$19 paid early access, with an optional $99 setup session through the feedback/setup form",
    "links": {
        "github": "https://github.com/aleksandermagi-dev/ContinuityAgent",
        "checkout": "https://linnuteeinnovations.lemonsqueezy.com/checkout/buy/d672a3ab-665e-488d-ba78-44f59c0b0140",
        "feedback_setup": "https://tally.so/r/VLbJVy",
    },
    "trust_points": [
        "local-first",
        "SQLite-backed",
        "Windows-first private beta",
        "no silent file mutation",
        "detected commands are recommended, not auto-run",
        "agent updates create drafts until reviewed",
        "installer is not code-signed yet, so Windows may warn users",
    ],
}


@dataclass(slots=True)
class ProductProfile:
    name: str
    positioning: str = ""
    summary: str = ""
    audience: list[str] = field(default_factory=list)
    offer: str = ""
    links: dict[str, str] = field(default_factory=dict)
    trust_points: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, payload: Any) -> "ProductProfile":
        data = payload if isinstance(payload, dict) else {}
        return cls(
            name=str(data.get("name", "Unnamed product")),
            positioning=str(data.get("positioning", "")),
            summary=str(data.get("summary", "")),
            audience=[str(item) for item in data.get("audience", [])],
            offer=str(data.get("offer", "")),
            links={str(key): str(value) for key, value in dict(data.get("links", {})).items()},
            trust_points=[str(item) for item in data.get("trust_points", [])],
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "positioning": self.positioning,
            "summary": self.summary,
            "audience": list(self.audience),
            "offer": self.offer,
            "links": dict(self.links),
            "trust_points": list(self.trust_points),
        }


@dataclass(slots=True)
class YouTubeUploadConfig:
    channel_label: str = ""
    default_visibility: str = "private"
    default_category: str = "Education"

    @classmethod
    def from_mapping(cls, payload: Any) -> "YouTubeUploadConfig":
        data = payload if isinstance(payload, dict) else {}
        return cls(
            channel_label=str(data.get("channel_label", "")),
            default_visibility=str(data.get("default_visibility", "private")),
            default_category=str(data.get("default_category", "Education")),
        )


@dataclass(slots=True)
class TikTokPostingConfig:
    account_label: str = ""
    default_visibility: str = "private"
    default_disclosure: str = "organic"

    @classmethod
    def from_mapping(cls, payload: Any) -> "TikTokPostingConfig":
        data = payload if isinstance(payload, dict) else {}
        return cls(
            account_label=str(data.get("account_label", "")),
            default_visibility=str(data.get("default_visibility", "private")),
            default_disclosure=str(data.get("default_disclosure", "organic")),
        )


@dataclass(slots=True)
class BlueskyPostingConfig:
    handle: str = ""
    app_password: str | None = None
    service_url: str = "https://bsky.social"

    @property
    def configured(self) -> bool:
        return bool(self.handle and self.app_password)

    @property
    def account_label(self) -> str:
        return self.handle or "not configured"

    @classmethod
    def from_mapping(cls, payload: Any) -> "BlueskyPostingConfig":
        data = payload if isinstance(payload, dict) else {}
        return cls(
            handle=os.getenv("ASTRA_BLUESKY_HANDLE") or str(data.get("handle", "")),
            app_password=os.getenv("ASTRA_BLUESKY_APP_PASSWORD") or data.get("app_password"),
            service_url=(os.getenv("ASTRA_BLUESKY_SERVICE_URL") or str(data.get("service_url", "https://bsky.social"))).rstrip("/"),
        )


@dataclass(slots=True)
class ElevenLabsConfig:
    api_key: str | None = None
    voice_id: str = ""
    model_id: str = "eleven_multilingual_v2"
    stability: float = 0.45
    similarity_boost: float = 0.8
    style: float = 0.2
    use_speaker_boost: bool = True

    @classmethod
    def from_mapping(cls, payload: Any) -> "ElevenLabsConfig":
        data = payload if isinstance(payload, dict) else {}
        env_api_key = os.getenv("ELEVENLABS_API_KEY")
        return cls(
            api_key=env_api_key or data.get("api_key"),
            voice_id=str(data.get("voice_id", "")),
            model_id=str(data.get("model_id", "eleven_multilingual_v2")),
            stability=float(data.get("stability", 0.45)),
            similarity_boost=float(data.get("similarity_boost", 0.8)),
            style=float(data.get("style", 0.2)),
            use_speaker_boost=bool(data.get("use_speaker_boost", True)),
        )


@dataclass(slots=True)
class VideoConfig:
    width: int = 1080
    height: int = 1920
    fps: int = 24
    background_color: str = "#050505"
    text_color: str = "#F5F5F5"
    accent_color: str = "#8BE9FD"
    font: str = "Arial-Bold"
    font_size: int = 78
    text_margin: int = 120
    line_gap: int = 18
    fade_seconds: float = 0.22
    drift_pixels: int = 32

    @classmethod
    def from_mapping(cls, payload: Any) -> "VideoConfig":
        data = payload if isinstance(payload, dict) else {}
        return cls(
            width=int(data.get("width", 1080)),
            height=int(data.get("height", 1920)),
            fps=int(data.get("fps", 24)),
            background_color=str(data.get("background_color", "#050505")),
            text_color=str(data.get("text_color", "#F5F5F5")),
            accent_color=str(data.get("accent_color", "#8BE9FD")),
            font=str(data.get("font", "Arial-Bold")),
            font_size=int(data.get("font_size", 78)),
            text_margin=int(data.get("text_margin", 120)),
            line_gap=int(data.get("line_gap", 18)),
            fade_seconds=float(data.get("fade_seconds", 0.22)),
            drift_pixels=int(data.get("drift_pixels", 32)),
        )


@dataclass(slots=True)
class AstraConfig:
    provider: str = "auto"
    model: str = "gpt-5-mini"
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    ollama_url: str = DEFAULT_OLLAMA_URL
    default_platform: str = "all"
    default_count: int = 5
    default_post_time_slot: str = "afternoon"
    company_name: str = DEFAULT_COMPANY_NAME
    company_role: str = DEFAULT_COMPANY_ROLE
    active_product: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_ACTIVE_PRODUCT))
    products: dict[str, ProductProfile] = field(default_factory=lambda: {"continuity-layer": ProductProfile.from_mapping(DEFAULT_ACTIVE_PRODUCT)})
    default_product: str = "continuity-layer"
    audience: list[str] = field(default_factory=lambda: list(DEFAULT_AUDIENCE))
    tone: list[str] = field(default_factory=lambda: list(DEFAULT_TONE))
    style: list[str] = field(default_factory=lambda: list(DEFAULT_STYLE))
    youtube_upload: YouTubeUploadConfig = field(default_factory=YouTubeUploadConfig)
    tiktok_posting: TikTokPostingConfig = field(default_factory=TikTokPostingConfig)
    bluesky_posting: BlueskyPostingConfig = field(default_factory=BlueskyPostingConfig)
    elevenlabs: ElevenLabsConfig = field(default_factory=ElevenLabsConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    api_key: str | None = None

    @classmethod
    def load(cls, config_path: str | None = None) -> "AstraConfig":
        file_path = Path(config_path or os.getenv("ASTRA_CONFIG") or "astra.config.json")
        data: dict[str, Any] = {}
        if file_path.exists():
            data = json.loads(file_path.read_text(encoding="utf-8"))
        api_key = os.getenv("OPENAI_API_KEY")
        provider = _normalize_provider(os.getenv("ASTRA_PROVIDER", str(data.get("provider", "auto"))))
        model = os.getenv("ASTRA_MODEL", data.get("model", "gpt-5-mini"))
        ollama_model = os.getenv("ASTRA_OLLAMA_MODEL", str(data.get("ollama_model", DEFAULT_OLLAMA_MODEL)))
        ollama_url = (os.getenv("ASTRA_OLLAMA_URL", str(data.get("ollama_url", DEFAULT_OLLAMA_URL)))).rstrip("/")
        active_product = dict(data.get("active_product", DEFAULT_ACTIVE_PRODUCT))
        raw_products = data.get("products")
        products = _load_product_profiles(raw_products, active_product)
        default_product = str(data.get("default_product") or _slugify_product_name(active_product.get("name", "")) or "continuity-layer")
        if default_product not in products:
            products[default_product] = ProductProfile.from_mapping(active_product)
        return cls(
            provider=provider,
            model=model,
            ollama_model=ollama_model,
            ollama_url=ollama_url,
            default_platform=str(data.get("default_platform", "all")),
            default_count=int(data.get("default_count", 5)),
            default_post_time_slot=str(data.get("default_post_time_slot", "afternoon")),
            company_name=str(data.get("company_name", DEFAULT_COMPANY_NAME)),
            company_role=str(data.get("company_role", DEFAULT_COMPANY_ROLE)),
            active_product=products[default_product].to_mapping(),
            products=products,
            default_product=default_product,
            audience=list(data.get("audience", DEFAULT_AUDIENCE)),
            tone=list(data.get("tone", DEFAULT_TONE)),
            style=list(data.get("style", DEFAULT_STYLE)),
            youtube_upload=YouTubeUploadConfig.from_mapping(data.get("youtube_upload")),
            tiktok_posting=TikTokPostingConfig.from_mapping(data.get("tiktok_posting")),
            bluesky_posting=BlueskyPostingConfig.from_mapping(data.get("bluesky_posting")),
            elevenlabs=ElevenLabsConfig.from_mapping(data.get("elevenlabs")),
            video=VideoConfig.from_mapping(data.get("video")),
            api_key=api_key,
        )

    @property
    def active_provider(self) -> str:
        if self.provider == "auto":
            return "openai" if self.api_key else "ollama"
        return _normalize_provider(self.provider)

    @property
    def active_generation_model(self) -> str:
        return self.model if self.active_provider == "openai" else self.ollama_model

    def generation_configured(self) -> bool:
        if self.active_provider == "openai":
            return bool(self.api_key)
        return bool(self.ollama_model and self.ollama_url)

    def generation_error_message(self) -> str:
        if self.active_provider == "openai":
            return "OPENAI_API_KEY is required when ASTRA_PROVIDER=openai."
        return (
            f"Ollama generation is selected but not configured. Set ASTRA_OLLAMA_MODEL and ASTRA_OLLAMA_URL, "
            f"then open Ollama or run `ollama serve`. Current model: {self.ollama_model or 'missing'}."
        )

    def product_names(self) -> list[str]:
        return [profile.name for profile in self.products.values()]

    def get_product(self, product_ref: str | None = None) -> ProductProfile | None:
        if not product_ref:
            return self.products[self.default_product]
        if product_ref.lower() in {"company", "linnuteeinnovations", "none"}:
            return None
        normalized = _slugify_product_name(product_ref)
        if normalized in self.products:
            return self.products[normalized]
        exact = [
            profile
            for profile in self.products.values()
            if profile.name.lower() == product_ref.lower()
        ]
        if exact:
            return exact[0]
        partial = [
            profile
            for profile in self.products.values()
            if product_ref.lower() in profile.name.lower()
        ]
        if len(partial) == 1:
            return partial[0]
        raise ValueError(f"Unknown product profile: {product_ref}")

    def with_product(self, product_ref: str | None = None) -> "AstraConfig":
        product = self.get_product(product_ref)
        active_product = product.to_mapping() if product is not None else {
            "name": self.company_name,
            "positioning": "Founder-built practical tools from LinnuteeInnovations.",
            "summary": self.company_role,
            "audience": list(self.audience),
            "offer": "",
            "links": {},
            "trust_points": [
                "public actions remain drafts until approved",
                "practical usefulness over polished hype",
                "honest limitations and transparent founder-built updates",
            ],
        }
        if product is None:
            default_product = "company"
        else:
            default_product = _slugify_product_name(product.name)
        return AstraConfig(
            provider=self.provider,
            model=self.model,
            ollama_model=self.ollama_model,
            ollama_url=self.ollama_url,
            default_platform=self.default_platform,
            default_count=self.default_count,
            default_post_time_slot=self.default_post_time_slot,
            company_name=self.company_name,
            company_role=self.company_role,
            active_product=active_product,
            products=dict(self.products),
            default_product=default_product,
            audience=list(self.audience),
            tone=list(self.tone),
            style=list(self.style),
            youtube_upload=self.youtube_upload,
            tiktok_posting=self.tiktok_posting,
            bluesky_posting=self.bluesky_posting,
            elevenlabs=self.elevenlabs,
            video=self.video,
            api_key=self.api_key,
        )


def _normalize_provider(value: str) -> str:
    provider = str(value or "auto").strip().lower()
    if provider not in VALID_GENERATION_PROVIDERS:
        raise ValueError("ASTRA_PROVIDER must be auto, openai, or ollama.")
    return provider


def _slugify_product_name(name: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in str(name))
    parts = [part for part in cleaned.split("-") if part]
    return "-".join(parts)


def _load_product_profiles(raw_products: Any, active_product: dict[str, Any]) -> dict[str, ProductProfile]:
    profiles: dict[str, ProductProfile] = {}
    if isinstance(raw_products, dict):
        iterable = raw_products.values()
    elif isinstance(raw_products, list):
        iterable = raw_products
    else:
        iterable = [active_product]
    for raw in iterable:
        profile = ProductProfile.from_mapping(raw)
        profiles[_slugify_product_name(profile.name)] = profile
    if not profiles:
        profile = ProductProfile.from_mapping(active_product)
        profiles[_slugify_product_name(profile.name)] = profile
    return profiles
