from __future__ import annotations

import io
from pathlib import Path
import sys
from typing import Callable

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from astra.config import AstraConfig
from astra.cli import run_cli
from astra.formatters import format_ideas_text, format_posts_text, format_workflow_items_text
from astra.models import VALID_IDEA_PLATFORMS, WorkflowContentItem
from astra.outputs import (
    create_batch_run_dir,
    ensure_output_dirs,
    load_content_items,
    open_outputs_directory,
    save_batch_items,
)
from astra.service import AstraGenerator

InputFunc = Callable[[str], str]
OutputFunc = Callable[[str], None]


MENU = """\nAstra Launcher
1. Generate PR ideas
2. Generate campaign draft batch
3. Format latest batch for Reddit
4. Format latest batch for Hacker News
5. Review queue folder
6. Open outputs folder
7. Exit

You can also type a request like:
- generate me 3 on Continuity Layer launch replies
- give me 10 ideas about Continuity Layer launch for reddit
- format the latest batch for hacker news
"""

MAX_COUNT = 20


def run_launcher(
    *,
    input_func: InputFunc = input,
    output_func: OutputFunc = print,
    generator_factory=AstraGenerator,
    config_loader=AstraConfig.load,
    open_outputs_func=open_outputs_directory,
    cli_runner=run_cli,
) -> int:
    while True:
        output_func(MENU)
        choice = input_func("Select an option: ").strip()

        if choice == "1":
            _handle_ideas(
                input_func=input_func,
                output_func=output_func,
                generator_factory=generator_factory,
                config_loader=config_loader,
            )
        elif choice == "2":
            _handle_batch(
                input_func=input_func,
                output_func=output_func,
                generator_factory=generator_factory,
                config_loader=config_loader,
            )
        elif choice == "3":
            _handle_format(
                platform="reddit",
                input_func=input_func,
                output_func=output_func,
                generator_factory=generator_factory,
                config_loader=config_loader,
            )
        elif choice == "4":
            _handle_format(
                platform="hacker_news",
                input_func=input_func,
                output_func=output_func,
                generator_factory=generator_factory,
                config_loader=config_loader,
            )
        elif choice == "5":
            path = open_outputs_func(kind="queue")
            output_func(f"Queue folder: {path}")
        elif choice == "6":
            path = open_outputs_func()
            output_func(f"Outputs folder: {path}")
        elif choice == "7":
            output_func("Exiting Astra launcher.")
            return 0
        else:
            if not choice:
                output_func("Choose 1, 2, 3, 4, 5, 6, or 7, or type a request.")
                continue
            _handle_conversational_request(
                request=choice,
                output_func=output_func,
                generator_factory=generator_factory,
                cli_runner=cli_runner,
            )


def _handle_ideas(*, input_func: InputFunc, output_func: OutputFunc, generator_factory, config_loader) -> None:
    config = config_loader()
    if not config.api_key:
        output_func("OPENAI_API_KEY is required for generation commands.")
        return

    topic = _normalize_optional_text(input_func("Topic (optional): "))
    platform = _prompt_idea_platform(input_func, output_func, config.default_platform)
    count = _prompt_count(input_func, output_func, config.default_count)

    generator = generator_factory(config)
    ideas = generator.generate_ideas(topic=topic, count=count, platform=platform)
    rendered = format_ideas_text(ideas)

    output_func("")
    output_func(rendered)
    output_func("")
    output_func("Ideas are displayed only. Use Generate campaign draft batch to create saved JSON drafts.")


def _handle_batch(*, input_func: InputFunc, output_func: OutputFunc, generator_factory, config_loader) -> None:
    config = config_loader()
    if not config.api_key:
        output_func("OPENAI_API_KEY is required for generation commands.")
        return

    topic = _normalize_required_text(input_func("Topic: "))
    if not topic:
        output_func("A topic is required for batch generation.")
        return

    count = _prompt_count(input_func, output_func, config.default_count)

    generator = generator_factory(config)
    posts = generator.generate_posts(topic=topic, count=count)
    items = [
        WorkflowContentItem.from_post(
            post,
            platform="master",
            workflow_stage="master",
        )
        for post in posts
    ]
    batch_dir = create_batch_run_dir()
    saved_paths = save_batch_items(items, batch_dir)

    output_func("")
    output_func(format_posts_text(posts))
    output_func("")
    output_func(f"Saved batch folder: {batch_dir}")
    for path in saved_paths:
        output_func(f"Draft item: {path}")


def _handle_format(
    *,
    platform: str,
    input_func: InputFunc,
    output_func: OutputFunc,
    generator_factory,
    config_loader,
) -> None:
    config = config_loader()
    if not config.api_key:
        output_func("OPENAI_API_KEY is required for generation commands.")
        return

    source_text = input_func("Batch folder or item path (blank = latest batch): ").strip()
    source_path = Path(source_text) if source_text else _latest_batch_dir()
    if source_path is None or not source_path.exists():
        output_func("No batch source found. Generate a batch first or provide a valid path.")
        return

    generator = generator_factory(config)
    formatted_items = []
    saved_paths = []
    for item in load_content_items(source_path):
        if item.workflow_stage != "master":
            continue
        formatted = generator.format_for_platform(item, platform)
        formatted_items.append(formatted)
        target_dir = source_path if source_path.is_dir() else source_path.parent
        saved_paths.extend(save_batch_items([formatted], target_dir))

    if not formatted_items:
        output_func("No master drafts found to format in that location.")
        return

    output_func("")
    output_func(format_workflow_items_text(formatted_items))
    output_func("")
    for path in saved_paths:
        output_func(f"Saved formatted item: {path}")


def _prompt_idea_platform(input_func: InputFunc, output_func: OutputFunc, default_platform: str) -> str:
    valid_platforms = ", ".join(sorted(VALID_IDEA_PLATFORMS))
    while True:
        raw = input_func(f"Idea target (optional, default: {default_platform}): ").strip().lower()
        if not raw:
            return default_platform
        if raw in VALID_IDEA_PLATFORMS:
            return raw
        output_func(f"Channel must be one of: {valid_platforms}.")


def _prompt_count(input_func: InputFunc, output_func: OutputFunc, default_count: int) -> int:
    while True:
        raw = input_func(f"Count (optional, default: {default_count}, range: 1-{MAX_COUNT}): ").strip()
        if not raw:
            return default_count
        try:
            count = int(raw)
        except ValueError:
            output_func("Count must be a whole number.")
            continue
        if 1 <= count <= MAX_COUNT:
            return count
        output_func(f"Count must be between 1 and {MAX_COUNT}.")


def _handle_conversational_request(*, request: str, output_func: OutputFunc, generator_factory, cli_runner) -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        exit_code = cli_runner(
            [request],
            stdout=stdout,
            stderr=stderr,
            generator_factory=generator_factory,
        )
    except ValueError as exc:
        output_func(str(exc))
        return

    output = stdout.getvalue().strip()
    error = stderr.getvalue().strip()
    if output:
        for line in output.splitlines():
            output_func(line)
    if error:
        for line in error.splitlines():
            output_func(line)
    if exit_code not in (0, None) and not output and not error:
        output_func(f"Request failed with exit code {exit_code}.")


def _latest_batch_dir() -> Path | None:
    batches_root = ensure_output_dirs()["batches"]
    candidates = [path for path in batches_root.glob("*") if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _normalize_optional_text(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def _normalize_required_text(value: str) -> str:
    return value.strip()


def _configure_console_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(errors="replace")
            except (TypeError, ValueError):
                pass


def main() -> int:
    _configure_console_streams()
    return run_launcher()


if __name__ == "__main__":
    raise SystemExit(main())
