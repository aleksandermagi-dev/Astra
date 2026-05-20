from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable
from urllib import request

from .config import ElevenLabsConfig
from .models import WorkflowContentItem


class VoiceEngineConfigError(RuntimeError):
    """Raised when voice generation is not configured."""


VoiceTransport = Callable[[dict[str, object]], bytes]


@dataclass(slots=True)
class VoiceRequest:
    text: str
    voice_id: str
    model_id: str
    stability: float
    similarity_boost: float
    style: float
    use_speaker_boost: bool
    api_key: str

    def to_mapping(self) -> dict[str, object]:
        return {
            "text": self.text,
            "voice_id": self.voice_id,
            "model_id": self.model_id,
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style": self.style,
            "use_speaker_boost": self.use_speaker_boost,
            "api_key": self.api_key,
        }


def default_voice_transport(payload: dict[str, object]) -> bytes:
    api_key = str(payload["api_key"])
    voice_id = str(payload["voice_id"])
    body = json.dumps(
        {
            "text": payload["text"],
            "model_id": payload["model_id"],
            "voice_settings": {
                "stability": payload["stability"],
                "similarity_boost": payload["similarity_boost"],
                "style": payload["style"],
                "use_speaker_boost": payload["use_speaker_boost"],
            },
        }
    ).encode("utf-8")
    req = request.Request(
        url=f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=body,
        headers={
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key,
        },
        method="POST",
    )
    with request.urlopen(req) as response:
        return response.read()


class VoiceEngine:
    def __init__(
        self,
        config: ElevenLabsConfig,
        *,
        transport: VoiceTransport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or default_voice_transport

    def build_request(self, item: WorkflowContentItem) -> VoiceRequest:
        if not self.config.api_key:
            raise VoiceEngineConfigError("ELEVENLABS_API_KEY is required for `produce`.")
        if not self.config.voice_id:
            raise VoiceEngineConfigError("Set `elevenlabs.voice_id` in config before running `produce`.")
        text = "\n\n".join([item.hook, *item.script_lines])
        return VoiceRequest(
            text=text,
            voice_id=self.config.voice_id,
            model_id=self.config.model_id,
            stability=self.config.stability,
            similarity_boost=self.config.similarity_boost,
            style=self.config.style,
            use_speaker_boost=self.config.use_speaker_boost,
            api_key=self.config.api_key,
        )

    def generate_audio(self, item: WorkflowContentItem, output_path: str | Path) -> Path:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = self.build_request(item).to_mapping()
        audio_bytes = self.transport(payload)
        target.write_bytes(audio_bytes)
        return target
