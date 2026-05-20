from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import AstraConfig
from .models import WorkflowContentItem
from .outputs import create_ready_output_dir
from .script_engine import ScriptEngine
from .video_engine import VideoEngine
from .voice_engine import VoiceEngine


@dataclass(slots=True)
class ProductionResult:
    ready_dir: Path
    artifacts: dict[str, Path] = field(default_factory=dict)


class ProductionPipelineError(RuntimeError):
    def __init__(self, message: str, *, artifacts: dict[str, Path] | None = None) -> None:
        super().__init__(message)
        self.artifacts = artifacts or {}


class ProductionPipeline:
    def __init__(
        self,
        config: AstraConfig,
        *,
        script_engine: ScriptEngine | None = None,
        voice_engine: VoiceEngine | None = None,
        video_engine: VideoEngine | None = None,
    ) -> None:
        self.config = config
        self.script_engine = script_engine or ScriptEngine()
        self.voice_engine = voice_engine or VoiceEngine(config.elevenlabs)
        self.video_engine = video_engine or VideoEngine(config.video)

    def produce(
        self,
        item: WorkflowContentItem,
        *,
        base_dir: Path | None = None,
        now: datetime | None = None,
    ) -> ProductionResult:
        if item.status != "approved":
            raise ValueError("Only approved items can be produced into ready media.")
        if item.safety.decision != "PASS":
            raise ValueError("Only safety PASS items can be produced into ready media.")

        ready_dir = create_ready_output_dir(item, base_dir=base_dir, now=now)
        artifacts: dict[str, Path] = {}

        script_path, caption_path = self.script_engine.export(item, ready_dir)
        artifacts["script"] = script_path
        artifacts["caption"] = caption_path

        audio_path = ready_dir / "audio.mp3"
        try:
            artifacts["audio"] = self.voice_engine.generate_audio(item, audio_path)
        except Exception as exc:
            raise ProductionPipelineError(f"Voice generation failed: {exc}", artifacts=artifacts) from exc

        video_path = ready_dir / "video.mp4"
        try:
            artifacts["video"] = self.video_engine.render_video(item, artifacts["audio"], video_path)
        except Exception as exc:
            raise ProductionPipelineError(f"Video generation failed: {exc}", artifacts=artifacts) from exc

        return ProductionResult(ready_dir=ready_dir, artifacts=artifacts)
