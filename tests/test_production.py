from __future__ import annotations

from pathlib import Path

import pytest

from astra.config import AstraConfig, ElevenLabsConfig, VideoConfig
from astra.models import WorkflowContentItem
from astra.production import ProductionPipeline, ProductionPipelineError
from astra.script_engine import ScriptEngine
from astra.video_engine import VideoEngine
from astra.voice_engine import VoiceEngine, VoiceEngineConfigError


def _approved_item(**overrides) -> WorkflowContentItem:
    payload = {
        "id": "item1234",
        "topic": "Why attention is harder to keep than ever",
        "hook": "Attention got easier to steal.",
        "script_lines": [
            "That sounds efficient until your brain starts expecting interruption.",
            "The feed trained your pace before you noticed.",
            "So now stillness feels slower than it used to.",
        ],
        "caption": "Attention gets shaped before people notice it.",
        "hashtags": ["#attention", "#psychology"],
        "platform": "tiktok",
        "suggested_post_time": "afternoon",
        "status": "approved",
        "created_at": "2026-03-30T12:00:00Z",
        "workflow_stage": "platform_variant",
        "source_item_id": "master0001",
        "platform_notes": "Fast cuts. Highlight interruption. Keep the tone calm.",
        "retention_check": "It interrupts expectation and stays open-loop",
    }
    payload.update(overrides)
    return WorkflowContentItem.from_mapping(payload)


def test_script_engine_exports_script_and_caption(tmp_path) -> None:
    item = _approved_item()

    script_path, caption_path = ScriptEngine().export(item, tmp_path)

    assert script_path.read_text(encoding="utf-8").startswith("Attention got easier to steal.")
    caption_text = caption_path.read_text(encoding="utf-8")
    assert "Attention gets shaped before people notice it." in caption_text
    assert "#attention #psychology" in caption_text


def test_voice_engine_builds_expected_request(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    def fake_transport(payload: dict[str, object]) -> bytes:
        captured.update(payload)
        return b"mp3-bytes"

    engine = VoiceEngine(
        ElevenLabsConfig(
            api_key="voice-key",
            voice_id="voice-123",
            model_id="eleven_multilingual_v2",
            stability=0.4,
            similarity_boost=0.9,
            style=0.3,
            use_speaker_boost=True,
        ),
        transport=fake_transport,
    )

    target = engine.generate_audio(_approved_item(), tmp_path / "audio.mp3")

    assert target.read_bytes() == b"mp3-bytes"
    assert captured["voice_id"] == "voice-123"
    assert "Attention got easier to steal." in str(captured["text"])


def test_voice_engine_requires_api_key_and_voice_id() -> None:
    engine = VoiceEngine(ElevenLabsConfig())
    with pytest.raises(VoiceEngineConfigError):
        engine.build_request(_approved_item())


def test_video_engine_builds_line_windows_from_audio_duration() -> None:
    engine = VideoEngine(VideoConfig())

    timeline = engine.build_timeline(_approved_item(), 8.0)

    assert timeline.duration == 8.0
    assert len(timeline.line_windows) == 4
    assert timeline.line_windows[0][1] == 0.0
    assert timeline.line_windows[-1][2] == 8.0


def test_production_pipeline_exports_all_ready_artifacts(tmp_path) -> None:
    class FakeVoiceEngine:
        def generate_audio(self, item: WorkflowContentItem, output_path: str | Path) -> Path:
            target = Path(output_path)
            target.write_bytes(b"audio")
            return target

    class FakeVideoEngine:
        def render_video(self, item: WorkflowContentItem, audio_path: str | Path, output_path: str | Path) -> Path:
            target = Path(output_path)
            target.write_bytes(b"video")
            return target

    pipeline = ProductionPipeline(
        AstraConfig(
            elevenlabs=ElevenLabsConfig(api_key="voice-key", voice_id="voice-123"),
            video=VideoConfig(),
        ),
        voice_engine=FakeVoiceEngine(),
        video_engine=FakeVideoEngine(),
    )

    result = pipeline.produce(_approved_item(), base_dir=tmp_path / "outputs")

    assert result.ready_dir.parent.name == "ready"
    assert result.artifacts["script"].name == "script.txt"
    assert result.artifacts["caption"].name == "caption.txt"
    assert result.artifacts["audio"].name == "audio.mp3"
    assert result.artifacts["video"].name == "video.mp4"


def test_production_pipeline_rejects_non_approved_items(tmp_path) -> None:
    pipeline = ProductionPipeline(
        AstraConfig(elevenlabs=ElevenLabsConfig(api_key="voice-key", voice_id="voice-123"))
    )

    with pytest.raises(ValueError):
        pipeline.produce(_approved_item(status="draft"), base_dir=tmp_path / "outputs")


def test_production_pipeline_rejects_non_pass_safety(tmp_path) -> None:
    pipeline = ProductionPipeline(
        AstraConfig(elevenlabs=ElevenLabsConfig(api_key="voice-key", voice_id="voice-123"))
    )

    with pytest.raises(ValueError):
        pipeline.produce(
            _approved_item(
                safety={
                    "decision": "DISCARD",
                    "dimension_results": {"topic": "DISCARD"},
                    "reasons": ["Unsafe topic."],
                    "scores": {},
                    "rewrite_attempts": 1,
                    "last_evaluated_at": "2026-03-30T12:00:00Z",
                }
            ),
            base_dir=tmp_path / "outputs",
        )


def test_production_pipeline_preserves_partial_artifacts_on_video_failure(tmp_path) -> None:
    class FakeVoiceEngine:
        def generate_audio(self, item: WorkflowContentItem, output_path: str | Path) -> Path:
            target = Path(output_path)
            target.write_bytes(b"audio")
            return target

    class BrokenVideoEngine:
        def render_video(self, item: WorkflowContentItem, audio_path: str | Path, output_path: str | Path) -> Path:
            raise RuntimeError("encoder boom")

    pipeline = ProductionPipeline(
        AstraConfig(elevenlabs=ElevenLabsConfig(api_key="voice-key", voice_id="voice-123")),
        voice_engine=FakeVoiceEngine(),
        video_engine=BrokenVideoEngine(),
    )

    with pytest.raises(ProductionPipelineError) as exc_info:
        pipeline.produce(_approved_item(), base_dir=tmp_path / "outputs")

    assert "Video generation failed" in str(exc_info.value)
    assert "audio" in exc_info.value.artifacts
