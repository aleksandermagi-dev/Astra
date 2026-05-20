from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import WorkflowContentItem


@dataclass(slots=True)
class ScriptBundle:
    script_text: str
    caption_text: str


class ScriptEngine:
    def build_bundle(self, item: WorkflowContentItem) -> ScriptBundle:
        script_lines = [item.hook, *item.script_lines]
        script_text = "\n".join(script_lines).strip() + "\n"
        hashtag_line = " ".join(item.hashtags).strip()
        caption_parts = [item.caption.strip()]
        if hashtag_line:
            caption_parts.extend(["", hashtag_line])
        caption_text = "\n".join(caption_parts).strip() + "\n"
        return ScriptBundle(script_text=script_text, caption_text=caption_text)

    def export(self, item: WorkflowContentItem, output_dir: str | Path) -> tuple[Path, Path]:
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        bundle = self.build_bundle(item)
        script_path = target_dir / "script.txt"
        caption_path = target_dir / "caption.txt"
        script_path.write_text(bundle.script_text, encoding="utf-8")
        caption_path.write_text(bundle.caption_text, encoding="utf-8")
        return script_path, caption_path
