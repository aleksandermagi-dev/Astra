from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config import VideoConfig
from .models import WorkflowContentItem


def _load_moviepy() -> Any:
    try:
        from moviepy import AudioFileClip, ColorClip, CompositeVideoClip, TextClip, vfx
    except ImportError:
        from moviepy.editor import AudioFileClip, ColorClip, CompositeVideoClip, TextClip  # type: ignore[no-redef]
        try:
            from moviepy.editor import vfx  # type: ignore[no-redef]
        except ImportError:
            vfx = None
    return type(
        "MoviePyModule",
        (),
        {
            "AudioFileClip": AudioFileClip,
            "ColorClip": ColorClip,
            "CompositeVideoClip": CompositeVideoClip,
            "TextClip": TextClip,
            "vfx": vfx,
        },
    )


def _set_attr(clip: Any, modern: str, legacy: str, value: Any) -> Any:
    method = getattr(clip, modern, None)
    if callable(method):
        return method(value)
    method = getattr(clip, legacy, None)
    if callable(method):
        return method(value)
    return clip


def _set_position(clip: Any, value: Any) -> Any:
    method = getattr(clip, "with_position", None)
    if callable(method):
        return method(value)
    method = getattr(clip, "set_position", None)
    if callable(method):
        return method(value)
    return clip


def _set_audio(clip: Any, audio_clip: Any) -> Any:
    method = getattr(clip, "with_audio", None)
    if callable(method):
        return method(audio_clip)
    method = getattr(clip, "set_audio", None)
    if callable(method):
        return method(audio_clip)
    return clip


def _apply_fade(clip: Any, fade_seconds: float, moviepy_module: Any) -> Any:
    fadein = getattr(clip, "fadein", None)
    fadeout = getattr(clip, "fadeout", None)
    if callable(fadein) and callable(fadeout):
        clip = fadein(fade_seconds)
        return fadeout(fade_seconds)
    vfx = getattr(moviepy_module, "vfx", None)
    if vfx is not None:
        with_effects = getattr(clip, "with_effects", None)
        fade_in_effect = getattr(vfx, "FadeIn", None)
        fade_out_effect = getattr(vfx, "FadeOut", None)
        if callable(with_effects) and fade_in_effect and fade_out_effect:
            return with_effects([fade_in_effect(fade_seconds), fade_out_effect(fade_seconds)])
    return clip


def _build_text_clip(
    moviepy_module: Any,
    *,
    text: str,
    config: VideoConfig,
    size: tuple[int, int | None],
) -> Any:
    kwargs = {
        "text": text,
        "font_size": config.font_size,
        "font": config.font,
        "color": config.text_color,
        "method": "caption",
        "size": size,
        "text_align": "center",
        "interline": config.line_gap,
    }
    try:
        return moviepy_module.TextClip(**kwargs)
    except TypeError:
        return moviepy_module.TextClip(
            txt=text,
            fontsize=config.font_size,
            font=config.font,
            color=config.text_color,
            method="caption",
            size=size,
            align="center",
            interline=config.line_gap,
        )


@dataclass(slots=True)
class VideoTimeline:
    duration: float
    line_windows: list[tuple[str, float, float]]


class VideoEngine:
    def __init__(
        self,
        config: VideoConfig,
        *,
        moviepy_loader: Callable[[], Any] | None = None,
    ) -> None:
        self.config = config
        self.moviepy_loader = moviepy_loader or _load_moviepy

    def build_timeline(self, item: WorkflowContentItem, audio_duration: float) -> VideoTimeline:
        lines = [item.hook, *item.script_lines]
        weights = [max(len(line.split()), 2) for line in lines]
        total_weight = sum(weights) or len(lines)
        current = 0.0
        windows: list[tuple[str, float, float]] = []
        for line, weight in zip(lines, weights):
            segment = audio_duration * (weight / total_weight)
            start = current
            end = audio_duration if line == lines[-1] else min(audio_duration, current + segment)
            windows.append((line, round(start, 3), round(end, 3)))
            current = end
        if windows:
            last_line, start, _ = windows[-1]
            windows[-1] = (last_line, start, round(audio_duration, 3))
        return VideoTimeline(duration=audio_duration, line_windows=windows)

    def render_video(self, item: WorkflowContentItem, audio_path: str | Path, output_path: str | Path) -> Path:
        moviepy = self.moviepy_loader()
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        audio_clip = moviepy.AudioFileClip(str(audio_path))
        duration = float(getattr(audio_clip, "duration", 0.0) or 0.0)
        if duration <= 0:
            raise ValueError("Audio clip duration must be greater than zero.")

        timeline = self.build_timeline(item, duration)
        bg_color = _hex_to_rgb(self.config.background_color)
        base_clip = moviepy.ColorClip(size=(self.config.width, self.config.height), color=bg_color, duration=duration)
        clips = [base_clip]
        text_width = self.config.width - (self.config.text_margin * 2)
        base_y = self.config.height * 0.43

        for index, (line, start, end) in enumerate(timeline.line_windows):
            line_duration = max(end - start, 0.6)
            text_clip = _build_text_clip(
                moviepy,
                text=line,
                config=self.config,
                size=(text_width, None),
            )
            text_clip = _set_attr(text_clip, "with_start", "set_start", start)
            text_clip = _set_attr(text_clip, "with_duration", "set_duration", line_duration)
            drift_direction = -1 if index % 2 == 0 else 1
            drift = drift_direction * self.config.drift_pixels
            text_clip = _set_position(
                text_clip,
                lambda t, base=base_y, amount=drift, span=max(line_duration, 0.001): (
                    "center",
                    int(base + (amount * (min(max(t, 0.0), span) / span))),
                ),
            )
            text_clip = _apply_fade(text_clip, min(self.config.fade_seconds, line_duration / 3), moviepy)
            clips.append(text_clip)

        final_clip = moviepy.CompositeVideoClip(clips, size=(self.config.width, self.config.height))
        final_clip = _set_audio(final_clip, audio_clip)
        write_videofile = getattr(final_clip, "write_videofile")
        write_videofile(
            str(target),
            fps=self.config.fps,
            codec="libx264",
            audio_codec="aac",
            logger=None,
        )
        close = getattr(audio_clip, "close", None)
        if callable(close):
            close()
        close = getattr(final_clip, "close", None)
        if callable(close):
            close()
        return target


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    cleaned = value.strip().lstrip("#")
    if len(cleaned) != 6 or any(char not in "0123456789abcdefABCDEF" for char in cleaned):
        return (5, 5, 5)
    return tuple(int(cleaned[index : index + 2], 16) for index in range(0, 6, 2))
