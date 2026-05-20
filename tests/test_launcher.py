from __future__ import annotations

from pathlib import Path

import launcher
from astra.config import AstraConfig
from astra.models import ContentPost, IdeaItem, WorkflowContentItem


class FakeGenerator:
    def __init__(self, config: AstraConfig) -> None:
        self.config = config

    def generate_ideas(self, *, topic, count, platform):
        return [IdeaItem(rank=1, topic=f"{topic or 'Default'} idea", reason=f"{platform}-{count}")]

    def generate_posts(self, *, topic, count):
        return [
            ContentPost(
                topic=topic,
                hook="master hook",
                script_lines=["line one", "line two"],
                caption=f"caption x{count}",
                tags=["#astra"],
                platform_notes=None,
                retention_check="It starts with pressure and stays compact",
                suggested_post_time="afternoon",
            )
        ]

    def format_for_platform(self, item, platform):
        return WorkflowContentItem(
            id=f"{platform[:3]}12345",
            topic=item.topic,
            hook=f"{platform} hook",
            script_lines=["formatted one", "formatted two"],
            caption=f"{platform} caption",
            hashtags=["#astra"],
            platform=platform,
            suggested_post_time="evening",
            status="draft",
            created_at=item.created_at,
            workflow_stage="platform_variant",
            source_item_id=item.id,
            platform_notes=None,
            retention_check="It starts with pressure and stays compact",
        )


def _config_loader() -> AstraConfig:
    return AstraConfig(api_key="test-key", default_platform="all", default_count=5)


def test_launcher_generates_ideas(monkeypatch) -> None:
    responses = iter(["1", "Continuity Layer launch", "reddit", "3", "7"])
    messages: list[str] = []

    def fake_input(prompt: str) -> str:
        return next(responses)

    def fake_output(message: str = "") -> None:
        messages.append(message)

    exit_code = launcher.run_launcher(
        input_func=fake_input,
        output_func=fake_output,
        generator_factory=FakeGenerator,
        config_loader=_config_loader,
    )

    assert exit_code == 0
    assert any("Continuity Layer launch idea" in message for message in messages)
    assert any("Ideas are displayed only" in message for message in messages)


def test_launcher_batch_saves_items(monkeypatch, tmp_path) -> None:
    responses = iter(["2", "Continuity Layer launch", "2", "7"])
    messages: list[str] = []

    def fake_input(prompt: str) -> str:
        return next(responses)

    def fake_output(message: str = "") -> None:
        messages.append(message)

    def fake_batch_dir():
        target = tmp_path / "outputs" / "batches" / "batch_20260329_120000"
        target.mkdir(parents=True, exist_ok=True)
        return target

    def fake_save_batch_items(items, batch_dir):
        target = batch_dir / "item.json"
        target.write_text("{}", encoding="utf-8")
        return [target]

    monkeypatch.setattr(launcher, "create_batch_run_dir", fake_batch_dir)
    monkeypatch.setattr(launcher, "save_batch_items", fake_save_batch_items)

    exit_code = launcher.run_launcher(
        input_func=fake_input,
        output_func=fake_output,
        generator_factory=FakeGenerator,
        config_loader=_config_loader,
    )

    assert exit_code == 0
    assert any("Saved batch folder:" in message for message in messages)
    assert any("Draft item:" in message for message in messages)


def test_launcher_formats_latest_batch(monkeypatch, tmp_path) -> None:
    responses = iter(["3", "", "7"])
    messages: list[str] = []
    batch_dir = tmp_path / "outputs" / "batches" / "batch_20260329_120000"
    batch_dir.mkdir(parents=True, exist_ok=True)
    draft_item = WorkflowContentItem(
        id="master01",
        topic="Hidden patterns",
        hook="master hook",
        script_lines=["line one", "line two"],
        caption="caption",
        hashtags=["#astra"],
        platform="master",
        suggested_post_time="afternoon",
        status="draft",
        created_at="2026-03-29T12:00:00Z",
        workflow_stage="master",
        retention_check="It starts with pressure and stays compact",
    )

    def fake_input(prompt: str) -> str:
        return next(responses)

    def fake_output(message: str = "") -> None:
        messages.append(message)

    def fake_load_content_items(path):
        assert Path(path) == batch_dir
        return [draft_item]

    def fake_save_batch_items(items, target_dir):
        target = target_dir / "formatted.json"
        target.write_text("{}", encoding="utf-8")
        return [target]

    monkeypatch.setattr(launcher, "_latest_batch_dir", lambda: batch_dir)
    monkeypatch.setattr(launcher, "load_content_items", fake_load_content_items)
    monkeypatch.setattr(launcher, "save_batch_items", fake_save_batch_items)

    exit_code = launcher.run_launcher(
        input_func=fake_input,
        output_func=fake_output,
        generator_factory=FakeGenerator,
        config_loader=_config_loader,
    )

    assert exit_code == 0
    assert any("hacker_news hook" not in message for message in messages)
    assert any("reddit hook" in message for message in messages)
    assert any("Saved formatted item:" in message for message in messages)


def test_launcher_opens_queue_and_outputs() -> None:
    responses = iter(["5", "6", "7"])
    messages: list[str] = []
    opened: list[tuple[str, Path]] = []

    def fake_input(prompt: str) -> str:
        return next(responses)

    def fake_output(message: str = "") -> None:
        messages.append(message)

    def fake_open_outputs(kind="root"):
        path = Path(f"C:/temp/{kind}")
        opened.append((kind, path))
        return path

    exit_code = launcher.run_launcher(
        input_func=fake_input,
        output_func=fake_output,
        generator_factory=FakeGenerator,
        config_loader=_config_loader,
        open_outputs_func=fake_open_outputs,
    )

    assert exit_code == 0
    assert opened == [("queue", Path("C:/temp/queue")), ("root", Path("C:/temp/root"))]
    assert any("Queue folder:" in message for message in messages)
    assert any("Outputs folder:" in message for message in messages)


def test_launcher_reprompts_for_invalid_platform_and_count() -> None:
    responses = iter(["1", "Continuity Layer", "instagram", "reddit", "abc", "0", "21", "3", "7"])
    messages: list[str] = []

    def fake_input(prompt: str) -> str:
        return next(responses)

    def fake_output(message: str = "") -> None:
        messages.append(message)

    exit_code = launcher.run_launcher(
        input_func=fake_input,
        output_func=fake_output,
        generator_factory=FakeGenerator,
        config_loader=_config_loader,
    )

    assert exit_code == 0
    assert any("Channel must be one of:" in message for message in messages)
    assert any("Count must be a whole number." in message for message in messages)
    assert any("Count must be between 1 and 20." in message for message in messages)
    assert any("reddit-3" in message for message in messages)


def test_launcher_accepts_conversational_request() -> None:
    responses = iter(["generate me 2 on why attention is harder to keep than ever", "7"])
    messages: list[str] = []
    captured: list[list[str]] = []

    def fake_input(prompt: str) -> str:
        return next(responses)

    def fake_output(message: str = "") -> None:
        messages.append(message)

    def fake_cli_runner(argv, **kwargs):
        captured.append(list(argv))
        kwargs["stdout"].write("Saved draft item: C:/temp/item.json\n")
        return 0

    exit_code = launcher.run_launcher(
        input_func=fake_input,
        output_func=fake_output,
        generator_factory=FakeGenerator,
        config_loader=_config_loader,
        cli_runner=fake_cli_runner,
    )

    assert exit_code == 0
    assert captured == [["generate me 2 on why attention is harder to keep than ever"]]
    assert any("Saved draft item:" in message for message in messages)


def test_launcher_batch_rejects_blank_topic_after_stripping() -> None:
    responses = iter(["2", "   ", "7"])
    messages: list[str] = []

    def fake_input(prompt: str) -> str:
        return next(responses)

    def fake_output(message: str = "") -> None:
        messages.append(message)

    exit_code = launcher.run_launcher(
        input_func=fake_input,
        output_func=fake_output,
        generator_factory=FakeGenerator,
        config_loader=_config_loader,
    )

    assert exit_code == 0
    assert "A topic is required for batch generation." in messages
