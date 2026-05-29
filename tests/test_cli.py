from __future__ import annotations

import io
import json
from pathlib import Path

from astra.cli import run_cli
from astra.config import AstraConfig
from astra.models import CampaignDay, CampaignPlan, ContentPost, IdeaItem, PublishResult, ReplyDraft, WorkflowContentItem
from astra.production import ProductionPipelineError, ProductionResult
from astra.outputs import ensure_output_dirs, save_content_item
from astra.tendril.settings import TendrilSettings


class FakeGenerator:
    def __init__(self, config: AstraConfig) -> None:
        self.config = config

    def generate_ideas(self, *, topic, count, platform):
        return [
            IdeaItem(rank=1, topic=f"{topic or 'Default'} idea", reason=f"Built for {platform} with count {count}.")
        ]

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

    def generate_workflow_items(self, *, topic, count, recent_items=None):
        return [
            WorkflowContentItem(
                id="wrk12345",
                topic=topic,
                hook="Builders keep re-explaining the same project context.",
                script_lines=["The pain is not writing prompts.", "The problem is that every agent starts cold unless the project memory travels with the work."],
                caption=f"caption x{count}",
                hashtags=["#astra"],
                platform="master",
                suggested_post_time="afternoon",
                status="draft",
                created_at="2026-03-29T12:00:00Z",
                workflow_stage="master",
                platform_notes="Ask for one concrete workflow pain. Track objections by channel.",
                retention_check="It starts with pressure and stays compact",
            )
        ]

    def format_for_platform(self, item, platform, recent_items=None):
        return WorkflowContentItem(
            id=f"{platform[:3]}12345",
            topic=item.topic,
            hook="Stop re-explaining your project to AI.",
            script_lines=["Continuity Layer keeps local project memory for humans and agents.", "It is Windows-first, local-first, and still a private beta."],
            caption=f"{platform} draft for Continuity Layer feedback.",
            hashtags=["#astra", f"#{platform}"],
            platform=platform,
            suggested_post_time="evening",
            status="draft",
            created_at=item.created_at,
            workflow_stage="platform_variant",
            source_item_id=item.id,
            platform_notes="Disclose beta limits. Track setup requests and objections.",
            retention_check="It starts with pressure and stays compact",
        )

    def generate_campaign_plan(self, *, goal, days=7):
        return CampaignPlan(
            product=self.config.active_product["name"],
            goal=goal,
            summary="A practical founder launch plan.",
            days=[
                CampaignDay(
                    day=1,
                    channel="reddit",
                    angle="Ask builders where agent context gets lost.",
                    cta="Share the GitHub link for inspection.",
                    reply_focus="Listen for real workflow pain.",
                    objection_to_watch="Why not just docs?",
                    tracking_goal="Replies and setup requests.",
                )
            ],
            notes="Keep it honest.",
        )

    def draft_product_posts(self, *, channel, count, goal=None, recent_items=None):
        return [
            WorkflowContentItem(
                id="prd12345",
                topic=goal or "Continuity Layer launch",
                hook="Stop re-explaining your project to AI.",
                script_lines=["Continuity Layer gives agents compact project memory.", "It is local-first and review-safe."],
                caption="Founder-built early access is open.",
                hashtags=["#ai"],
                platform=channel,
                suggested_post_time="afternoon",
                status="draft",
                created_at="2026-03-29T12:00:00Z",
                workflow_stage="platform_variant",
                source_item_id="product-profile",
                platform_notes="Track replies and objections.",
                retention_check="The pain is clear immediately.",
            )
        ]

    def draft_reply(self, *, scenario, user_signal=None):
        return ReplyDraft(
            product=self.config.active_product["name"],
            scenario=scenario,
            user_signal=user_signal or "Why not README?",
            reply="Fair question. README files help, but they do not track current agent handoff state by themselves.",
            follow_up="What do you usually paste into agents at the start of a session?",
            tracking_note="Log README/Notion objection.",
        )


def _sample_master_item() -> WorkflowContentItem:
    return WorkflowContentItem(
        id="master01",
        topic="Continuity Layer",
        hook="Builders keep re-explaining the same project context.",
        script_lines=["The pain is not writing prompts.", "The problem is that every agent starts cold unless the project memory travels with the work."],
        caption="Local-first project memory for AI builders.",
        hashtags=["#astra"],
        platform="master",
        suggested_post_time="afternoon",
        status="draft",
        created_at="2026-03-29T12:00:00Z",
        workflow_stage="master",
        platform_notes="Ask for one concrete workflow pain. Track objections by channel.",
        retention_check="It starts with pressure and stays compact",
    )


def test_cli_ideas_command_prints_ranked_output_and_saved_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    stdout = io.StringIO()
    stderr = io.StringIO()

    def fake_save(**kwargs):
        target = tmp_path / "outputs" / "ideas" / "ideas.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(kwargs["content"], encoding="utf-8")
        return target

    monkeypatch.setattr("astra.cli.save_generated_output", fake_save)

    exit_code = run_cli(
        ["ideas", "--topic", "Continuity Layer launch", "--count", "5", "--platform", "reddit"],
        stdout=stdout,
        stderr=stderr,
        generator_factory=FakeGenerator,
    )

    assert exit_code == 0
    assert "1. Continuity Layer launch idea" in stdout.getvalue()
    assert "Saved to:" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_cli_batch_generates_master_drafts(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_cli(
        ["batch", "--topic", "Continuity Layer", "--format", "json"],
        stdout=stdout,
        stderr=stderr,
        generator_factory=FakeGenerator,
    )

    assert exit_code == 0
    batch_dirs = list((tmp_path / "outputs" / "batches").glob("batch_*"))
    assert batch_dirs
    draft_files = list(batch_dirs[0].glob("*.json"))
    assert draft_files
    payload = json.loads(draft_files[0].read_text(encoding="utf-8"))
    assert payload["platform"] == "master"
    assert payload["status"] == "draft"
    assert payload["safety"]["decision"] == "PASS"
    assert "Saved draft item:" in stdout.getvalue()
    assert "Safety PASS" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_cli_supports_conversational_batch_request(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_cli(
        ["generate", "me", "3", "on", "why", "attention", "is", "harder", "to", "keep", "than", "ever"],
        stdout=stdout,
        stderr=stderr,
        generator_factory=FakeGenerator,
    )

    assert exit_code == 0
    batch_dirs = list((tmp_path / "outputs" / "batches").glob("batch_*"))
    assert batch_dirs
    assert "why attention is harder to keep than ever" in stdout.getvalue().lower()


def test_cli_supports_conversational_ideas_request(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    stdout = io.StringIO()
    stderr = io.StringIO()

    def fake_save(**kwargs):
        target = tmp_path / "outputs" / "ideas" / "ideas.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(kwargs["content"], encoding="utf-8")
        return target

    monkeypatch.setattr("astra.cli.save_generated_output", fake_save)

    exit_code = run_cli(
        ["give", "me", "7", "ideas", "about", "trust", "and", "attention", "for", "reddit"],
        stdout=stdout,
        stderr=stderr,
        generator_factory=FakeGenerator,
    )

    assert exit_code == 0
    assert "trust and attention" in stdout.getvalue().lower()
    assert "saved to:" in stdout.getvalue().lower()


def test_cli_format_approve_queue_and_log_workflow(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    ensure_output_dirs(tmp_path / "outputs")
    draft_dir = tmp_path / "outputs" / "batches" / "batch_20260329_120000"
    draft_path = save_content_item(_sample_master_item(), draft_dir)

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_cli(
        ["format", "--input", str(draft_dir), "--platform", "reddit"],
        stdout=stdout,
        stderr=stderr,
        generator_factory=FakeGenerator,
    )
    assert exit_code == 0
    formatted_files = list(draft_dir.glob("*_reddit_draft_*.json"))
    assert formatted_files

    stdout = io.StringIO()
    run_cli(["approve", "--input", str(formatted_files[0])], stdout=stdout, stderr=stderr)
    approved_files = list((tmp_path / "outputs" / "approved").glob("*_approved_*.json"))
    assert approved_files

    stdout = io.StringIO()
    run_cli(["queue", "--input", str(approved_files[0]), "--slot", "morning"], stdout=stdout, stderr=stderr)
    queued_files = list((tmp_path / "outputs" / "queue").glob("*_queued_*.json"))
    assert queued_files

    stdout = io.StringIO()
    run_cli(
        [
            "log-post",
            "--input",
            str(queued_files[0]),
            "--post-id-or-url",
            "https://example.com/post/123",
            "--views",
            "100",
        ],
        stdout=stdout,
        stderr=stderr,
    )
    logs = list((tmp_path / "outputs" / "logs").glob("*_analytics.jsonl"))
    assert logs
    assert '"views": 100.0' in logs[0].read_text(encoding="utf-8")

    stdout = io.StringIO()
    run_cli(["review-queue"], stdout=stdout, stderr=stderr)
    assert "queued" in stdout.getvalue()


def test_cli_clear_review_drafts_deletes_only_draft_review_items(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    dirs = ensure_output_dirs(tmp_path / "outputs")
    draft_path = save_content_item(_sample_master_item(), dirs["batches"] / "batch_20260329_120000")
    approved_path = save_content_item(_sample_master_item().with_updates(id="appr1111", status="approved"), dirs["approved"])
    queued_path = save_content_item(_sample_master_item().with_updates(id="queue111", status="queued"), dirs["queue"])
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_cli(["clear-review-drafts"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert "Cleared 1 review draft item(s)." in stdout.getvalue()
    assert not draft_path.exists()
    assert approved_path.exists()
    assert queued_path.exists()


def test_cli_supports_conversational_format_request(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    ensure_output_dirs(tmp_path / "outputs")
    draft_dir = tmp_path / "outputs" / "batches" / "batch_20260329_120000"
    save_content_item(_sample_master_item(), draft_dir)

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_cli(
        ["format", "the", "latest", "batch", "for", "hacker", "news"],
        stdout=stdout,
        stderr=stderr,
        generator_factory=FakeGenerator,
    )

    assert exit_code == 0
    assert "saved formatted item:" in stdout.getvalue().lower()
    assert "safety pass" in stdout.getvalue().lower()


def test_cli_market_log_template_prints_tracking_columns() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_cli(["market-log-template", "--format", "csv"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert "post_url" in stdout.getvalue()
    assert "purchases" in stdout.getvalue()
    assert "feedback_themes" in stdout.getvalue()
    assert "next_action" in stdout.getvalue()


def test_cli_market_log_template_can_save_local_file(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_cli(["market-log-template", "--format", "md", "--save"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert "Saved market log:" in stdout.getvalue()
    assert list((tmp_path / "outputs" / "logs").glob("*.md"))


def test_cli_products_list_and_show() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_cli(["products", "list"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert "continuity-layer: Continuity Layer" in stdout.getvalue()

    stdout = io.StringIO()
    exit_code = run_cli(["products", "show", "Continuity Layer"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert "Stop re-explaining your project to AI." in stdout.getvalue()

    config = AstraConfig().with_product("company")
    assert config.active_product["name"] == "LinnuteeInnovations"


def test_cli_campaign_posts_and_replies(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_cli(
        ["campaign", "create", "--product", "Continuity Layer", "--goal", "7-day launch"],
        stdout=stdout,
        stderr=stderr,
        generator_factory=FakeGenerator,
    )

    assert exit_code == 0
    assert "A practical founder launch plan" in stdout.getvalue()
    assert list((tmp_path / "outputs" / "campaigns").glob("*.md"))

    stdout = io.StringIO()
    exit_code = run_cli(
        ["posts", "draft", "--product", "Continuity Layer", "--channel", "reddit", "--count", "2", "--goal", "launch"],
        stdout=stdout,
        stderr=stderr,
        generator_factory=FakeGenerator,
    )

    assert exit_code == 0
    assert "Saved post draft:" in stdout.getvalue()
    assert list((tmp_path / "outputs" / "batches").glob("batch_*/*.json"))

    stdout = io.StringIO()
    exit_code = run_cli(
        ["replies", "draft", "--product", "Continuity Layer", "--scenario", "why_not_readme_notion"],
        stdout=stdout,
        stderr=stderr,
        generator_factory=FakeGenerator,
    )

    assert exit_code == 0
    assert "README files help" in stdout.getvalue()
    assert list((tmp_path / "outputs" / "replies").glob("*.md"))


def test_cli_feedback_and_experiments_from_csv(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    log = tmp_path / "market.csv"
    log.write_text(
        "date,platform,post_url,angle,cta,replies,clicks,purchases,setup_requests,feedback_themes,objections,buyer_language,next_action\n"
        "2026-05-20,reddit,https://example.com,context pain,github,3,8,1,1,setup,why not README,saves re-explaining,write README reply\n",
        encoding="utf-8",
    )

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_cli(["feedback", "summarize", "--input", str(log)], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert "Purchases: 1" in stdout.getvalue()
    assert "why not README" in stdout.getvalue()

    stdout = io.StringIO()
    exit_code = run_cli(["experiments", "suggest", "--input", str(log)], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert "Suggested experiments" in stdout.getvalue()
    assert list((tmp_path / "outputs" / "experiments").glob("*.md"))


def test_cli_accounts_publish_and_publish_queue(monkeypatch) -> None:
    monkeypatch.setattr("astra.cli.PublishingService", FakePublishingService)
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_cli(["accounts", "status"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert "bluesky: configured" in stdout.getvalue()

    stdout = io.StringIO()
    exit_code = run_cli(["publish", "--id", "pub12345"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert "posted" in stdout.getvalue()

    stdout = io.StringIO()
    exit_code = run_cli(["publish-queue", "--platform", "bluesky"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert "pub12345 | bluesky | posted" in stdout.getvalue()


def test_cli_does_not_expose_external_posting_commands() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    try:
        run_cli(["external-post"], stdout=stdout, stderr=stderr)
    except SystemExit as exc:
        assert exc.code != 0
    except ValueError as exc:
        assert "Could not understand" in str(exc)
    else:
        raise AssertionError("external-post should not be a supported command.")


def test_cli_tendril_create_list_approve_run_flow(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    settings = TendrilSettings.from_repo_root(tmp_path, data_root=tmp_path / "outputs" / "tendril")
    monkeypatch.setattr(
        "astra.tendril.service.TendrilSettings.from_repo_root",
        lambda *args, **kwargs: settings,
    )

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_cli(
        ["tendril", "create", "--goal", "Create launch notes", "--workspace-name", "launch notes"],
        stdout=stdout,
        stderr=stderr,
    )
    assert exit_code == 0
    assert "Approval required: True" in stdout.getvalue()
    task_id = stdout.getvalue().split(" | ")[0]

    stdout = io.StringIO()
    exit_code = run_cli(["tendril", "list"], stdout=stdout, stderr=stderr)
    assert exit_code == 0
    assert task_id in stdout.getvalue()

    stdout = io.StringIO()
    exit_code = run_cli(["tendril", "run", task_id], stdout=stdout, stderr=stderr)
    assert exit_code == 0
    assert "Reason: approval_required" in stdout.getvalue()

    stdout = io.StringIO()
    exit_code = run_cli(["tendril", "approve", task_id], stdout=stdout, stderr=stderr)
    assert exit_code == 0
    assert "approval=approved" in stdout.getvalue()

    stdout = io.StringIO()
    exit_code = run_cli(["tendril", "run", task_id], stdout=stdout, stderr=stderr)
    assert exit_code == 0
    assert "Tendril run: completed" in stdout.getvalue()
    assert (tmp_path / "outputs" / "tendril" / "workspaces" / "launch-notes" / "summary.md").exists()


def test_cli_uses_ollama_provider_without_openai_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ASTRA_PROVIDER", "ollama")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_cli(
        ["ideas", "--topic", "AI myths"],
        stdout=stdout,
        stderr=stderr,
        generator_factory=FakeGenerator,
    )

    assert exit_code == 0
    assert "AI myths idea" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_cli_requires_api_key_for_explicit_openai_generation(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ASTRA_PROVIDER", "openai")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_cli(
        ["ideas", "--topic", "AI myths"],
        stdout=stdout,
        stderr=stderr,
        generator_factory=FakeGenerator,
    )

    assert exit_code == 2
    assert "OPENAI_API_KEY is required when ASTRA_PROVIDER=openai" in stderr.getvalue()


def test_cli_analyze_prints_summary(tmp_path) -> None:
    input_file = tmp_path / "performance.json"
    input_file.write_text(
        json.dumps(
            [
                {
                    "topic": "AI leverage",
                    "hook": "AI got scary when it got useful.",
                    "platform": "tiktok",
                    "views": 1000,
                    "retention": 0.62,
                }
            ]
        ),
        encoding="utf-8",
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_cli(["analyze", "--input", str(input_file)], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert "Best retention came from hook" in stdout.getvalue()
    assert stderr.getvalue() == ""


class FakePipeline:
    def __init__(self, config: AstraConfig) -> None:
        self.config = config

    def produce(self, item: WorkflowContentItem) -> ProductionResult:
        ready_dir = Path("C:/tmp/ready/folder")
        return ProductionResult(
            ready_dir=ready_dir,
            artifacts={
                "script": ready_dir / "script.txt",
                "caption": ready_dir / "caption.txt",
                "audio": ready_dir / "audio.mp3",
                "video": ready_dir / "video.mp4",
            },
        )


class FakePublishingService:
    def __init__(self) -> None:
        pass

    def accounts_status(self):
        return {"bluesky": "configured"}

    def publish_path(self, path):
        return PublishResult(platform="bluesky", item_id="pub12345", status="posted", external_url="https://bsky.app/profile/x/post/y")

    def publish_id(self, item_id):
        return PublishResult(platform="bluesky", item_id=item_id, status="posted", external_url="https://bsky.app/profile/x/post/y")

    def publish_queue(self, platform="bluesky"):
        return [PublishResult(platform=platform, item_id="pub12345", status="posted", external_url="https://bsky.app/profile/x/post/y")]


class FailingPipeline:
    def __init__(self, config: AstraConfig) -> None:
        self.config = config

    def produce(self, item: WorkflowContentItem) -> ProductionResult:
        raise ProductionPipelineError(
            "Video generation failed: renderer boom",
            artifacts={"audio": Path("C:/tmp/ready/folder/audio.mp3")},
        )


def test_cli_produce_renders_ready_media_from_approved_item(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    ensure_output_dirs(tmp_path / "outputs")
    approved_path = save_content_item(
        _sample_master_item().with_updates(
            id="tik12345",
            platform="tiktok",
            workflow_stage="platform_variant",
            source_item_id="master01",
            status="approved",
            platform_notes="Fast cuts. Highlight the shift.",
        ),
        tmp_path / "outputs" / "approved",
    )

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_cli(
        ["produce", "--input", str(approved_path)],
        stdout=stdout,
        stderr=stderr,
        pipeline_factory=FakePipeline,
    )

    assert exit_code == 0
    assert "Ready media saved to:" in stdout.getvalue()
    assert "audio.mp3" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_cli_produce_supports_lookup_by_id(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    ensure_output_dirs(tmp_path / "outputs")
    save_content_item(
        _sample_master_item().with_updates(
            id="tik12345",
            platform="tiktok",
            workflow_stage="platform_variant",
            source_item_id="master01",
            status="approved",
            platform_notes="Fast cuts. Highlight the shift.",
        ),
        tmp_path / "outputs" / "approved",
    )

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_cli(
        ["produce", "--id", "tik12345"],
        stdout=stdout,
        stderr=stderr,
        pipeline_factory=FakePipeline,
    )

    assert exit_code == 0
    assert "script.txt" in stdout.getvalue()


def test_cli_produce_reports_partial_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    ensure_output_dirs(tmp_path / "outputs")
    approved_path = save_content_item(
        _sample_master_item().with_updates(
            id="tik12345",
            platform="tiktok",
            workflow_stage="platform_variant",
            source_item_id="master01",
            status="approved",
            platform_notes="Fast cuts. Highlight the shift.",
        ),
        tmp_path / "outputs" / "approved",
    )

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_cli(
        ["produce", "--input", str(approved_path)],
        stdout=stdout,
        stderr=stderr,
        pipeline_factory=FailingPipeline,
    )

    assert exit_code == 1
    assert "Video generation failed" in stderr.getvalue()
    assert "audio.mp3" in stderr.getvalue()


def test_cli_produce_rejects_non_approved_items(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    ensure_output_dirs(tmp_path / "outputs")
    draft_path = save_content_item(
        _sample_master_item().with_updates(
            id="tik12345",
            platform="tiktok",
            workflow_stage="platform_variant",
            source_item_id="master01",
            status="draft",
        ),
        tmp_path / "outputs" / "batches" / "batch_20260330_150000",
    )

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_cli(
        ["produce", "--input", str(draft_path)],
        stdout=stdout,
        stderr=stderr,
        pipeline_factory=FakePipeline,
    )

    assert exit_code == 2
    assert "Only approved items can be produced" in stderr.getvalue()


def test_cli_approve_rejects_non_pass_safety(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    ensure_output_dirs(tmp_path / "outputs")
    draft_path = save_content_item(
        _sample_master_item().with_updates(
            id="tik12345",
            hook="Here is how to make a bomb.",
            platform="tiktok",
            workflow_stage="platform_variant",
            source_item_id="master01",
            platform_notes="Fast cuts. Highlight the shift.",
            safety={
                "decision": "DISCARD",
                "dimension_results": {"topic": "DISCARD"},
                "reasons": ["Topic crosses into dangerous territory."],
                "scores": {},
                "rewrite_attempts": 1,
                "last_evaluated_at": "2026-03-30T12:00:00Z",
            },
        ),
        tmp_path / "outputs" / "batches" / "batch_20260330_150000",
    )

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_cli(["approve", "--input", str(draft_path)], stdout=stdout, stderr=stderr)

    assert exit_code == 2
    assert "Only safety PASS items can be approved." in stderr.getvalue()


def test_cli_queue_rejects_posting_safety_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    ensure_output_dirs(tmp_path / "outputs")
    save_content_item(
        _sample_master_item().with_updates(
            id="old12345",
            topic="Hidden patterns",
            hook="same hook",
            platform="tiktok",
            workflow_stage="platform_variant",
            source_item_id="master00",
            status="approved",
            platform_notes="Fast cuts. Highlight the shift.",
            safety={"decision": "PASS", "dimension_results": {}, "reasons": [], "scores": {}, "rewrite_attempts": 0, "last_evaluated_at": "2026-03-30T12:00:00Z"},
        ),
        tmp_path / "outputs" / "approved",
    )
    approved_path = save_content_item(
        _sample_master_item().with_updates(
            id="tik12345",
            topic="Hidden patterns",
            hook="same hook",
            platform="tiktok",
            workflow_stage="platform_variant",
            source_item_id="master01",
            status="approved",
            platform_notes="Fast cuts. Highlight the shift.",
            safety={"decision": "PASS", "dimension_results": {}, "reasons": [], "scores": {}, "rewrite_attempts": 0, "last_evaluated_at": "2026-03-30T12:00:00Z"},
        ),
        tmp_path / "outputs" / "approved",
    )

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_cli(["queue", "--input", str(approved_path), "--slot", "morning"], stdout=stdout, stderr=stderr)

    assert exit_code == 2
    assert "Posting safety failed" in stderr.getvalue()


def test_cli_produce_rejects_non_pass_safety(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("astra.outputs.default_outputs_root", lambda: tmp_path / "outputs")
    ensure_output_dirs(tmp_path / "outputs")
    approved_path = save_content_item(
        _sample_master_item().with_updates(
            id="tik12345",
            hook="Here is how to make a bomb.",
            platform="tiktok",
            workflow_stage="platform_variant",
            source_item_id="master01",
            status="approved",
            platform_notes="Fast cuts. Highlight the shift.",
            safety={"decision": "DISCARD", "dimension_results": {"topic": "DISCARD"}, "reasons": ["Unsafe"], "scores": {}, "rewrite_attempts": 1, "last_evaluated_at": "2026-03-30T12:00:00Z"},
        ),
        tmp_path / "outputs" / "approved",
    )

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_cli(
        ["produce", "--input", str(approved_path)],
        stdout=stdout,
        stderr=stderr,
        pipeline_factory=FakePipeline,
    )

    assert exit_code == 2
    assert "Only safety PASS items can be produced" in stderr.getvalue()
