from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable, Sequence

from .cli import run_cli
from .config import AstraConfig
from .models import WorkflowContentItem
from .outputs import ensure_output_dirs, load_content_item, load_publish_log, open_outputs_directory
from .tendril.settings import TendrilSettings


CliRunner = Callable[..., int]
OpenPathFunc = Callable[[Path], None]


@dataclass(slots=True)
class GuiCommandResult:
    exit_code: int
    output: str
    error: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.error.strip()

    @property
    def display_text(self) -> str:
        parts = [part for part in (self.output.strip(), self.error.strip()) if part]
        return "\n\n".join(parts) or f"Command finished with exit code {self.exit_code}."


@dataclass(slots=True)
class DashboardItem:
    item_id: str
    topic: str
    platform: str
    status: str
    safety: str
    path: Path
    created_at: str


CONTINUITY_LAUNCH_PRODUCT = "Continuity Layer"
CONTINUITY_LAUNCH_GOAL = "Launch paid early access for Continuity Layer"


def run_cli_capture(argv: Sequence[str], *, cli_runner: CliRunner = run_cli) -> GuiCommandResult:
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        exit_code = cli_runner(list(argv), stdout=stdout, stderr=stderr)
    except SystemExit as exc:
        exit_code = int(exc.code or 0)
    except Exception as exc:
        return GuiCommandResult(exit_code=1, output="", error=str(exc))
    return GuiCommandResult(exit_code=int(exit_code or 0), output=stdout.getvalue(), error=stderr.getvalue())


def conversational_args(request: str) -> list[str]:
    text = request.strip()
    if not text:
        raise ValueError("Type a request first.")
    return [text]


def ideas_args(*, topic: str, channel: str, count: int) -> list[str]:
    args = ["ideas", "--count", str(count), "--platform", channel]
    if topic.strip():
        args.extend(["--topic", topic.strip()])
    return args


def batch_args(*, topic: str, count: int) -> list[str]:
    cleaned = topic.strip()
    if not cleaned:
        raise ValueError("Topic is required for a campaign draft batch.")
    return ["batch", "--topic", cleaned, "--count", str(count), "--format", "md"]


def product_names(*, config: AstraConfig | None = None) -> list[str]:
    loaded = config or AstraConfig.load()
    return ["company", *loaded.product_names()]


def campaign_args(*, product: str, goal: str, days: int = 7) -> list[str]:
    cleaned = goal.strip()
    if not cleaned:
        raise ValueError("Campaign goal is required.")
    args = ["campaign", "create", "--goal", cleaned, "--days", str(days)]
    if product and product != "company":
        args.extend(["--product", product])
    return args


def posts_args(*, product: str, channel: str, count: int, goal: str) -> list[str]:
    args = ["posts", "draft", "--channel", channel, "--count", str(count)]
    if product and product != "company":
        args.extend(["--product", product])
    if goal.strip():
        args.extend(["--goal", goal.strip()])
    return args


def replies_args(*, product: str, scenario: str, user_signal: str) -> list[str]:
    args = ["replies", "draft", "--scenario", scenario]
    if product and product != "company":
        args.extend(["--product", product])
    if user_signal.strip():
        args.extend(["--user-signal", user_signal.strip()])
    return args


def format_latest_args(channel: str) -> list[str]:
    return ["format", "the", "latest", "batch", "for", channel.replace("_", " ")]


def market_log_args(*, save: bool = False) -> list[str]:
    args = ["market-log-template", "--format", "md"]
    if save:
        args.append("--save")
    return args


def continuity_launch_pack_commands() -> list[list[str]]:
    return [
        campaign_args(product=CONTINUITY_LAUNCH_PRODUCT, goal=CONTINUITY_LAUNCH_GOAL),
        posts_args(product=CONTINUITY_LAUNCH_PRODUCT, channel="x_bluesky", count=3, goal=CONTINUITY_LAUNCH_GOAL),
        posts_args(product=CONTINUITY_LAUNCH_PRODUCT, channel="reddit", count=2, goal=CONTINUITY_LAUNCH_GOAL),
        posts_args(
            product=CONTINUITY_LAUNCH_PRODUCT,
            channel="hacker_news",
            count=1,
            goal="Show HN / technical launch for Continuity Layer",
        ),
        posts_args(
            product=CONTINUITY_LAUNCH_PRODUCT,
            channel="indie_hackers",
            count=1,
            goal="Founder-built early access launch",
        ),
        replies_args(product=CONTINUITY_LAUNCH_PRODUCT, scenario="skeptical_user", user_signal=""),
        replies_args(product=CONTINUITY_LAUNCH_PRODUCT, scenario="why_not_readme_notion", user_signal=""),
        market_log_args(save=True),
    ]


def describe_launch_pack_command(args: Sequence[str]) -> str:
    if args[:2] == ["campaign", "create"]:
        return "creating 7-day campaign plan"
    if args[:2] == ["posts", "draft"]:
        channel = _arg_value(args, "--channel")
        labels = {
            "x_bluesky": "drafting Bluesky posts",
            "reddit": "drafting Reddit posts",
            "hacker_news": "drafting Hacker News draft",
            "indie_hackers": "drafting Indie Hackers draft",
        }
        return labels.get(channel, f"drafting {channel or 'platform'} posts")
    if args[:2] == ["replies", "draft"]:
        scenario = _arg_value(args, "--scenario")
        labels = {
            "skeptical_user": "drafting skeptical-user reply",
            "why_not_readme_notion": "drafting README/Notion reply",
        }
        return labels.get(scenario, f"drafting {scenario or 'reply'} response")
    if args and args[0] == "market-log-template":
        return "saving market log template"
    return "running Astra command"


def launch_pack_step_label(args: Sequence[str]) -> str:
    if args[:2] == ["campaign", "create"]:
        return "campaign"
    if args[:2] == ["posts", "draft"]:
        return f"{_arg_value(args, '--channel') or 'post'} drafts"
    if args[:2] == ["replies", "draft"]:
        return f"{_arg_value(args, '--scenario') or 'reply'} reply"
    if args and args[0] == "market-log-template":
        return "market log"
    return "command"


def launch_pack_progress_messages(commands: Sequence[Sequence[str]] | None = None) -> list[str]:
    selected_commands = list(commands or continuity_launch_pack_commands())
    total = len(selected_commands)
    return [
        f"Step {index}/{total}: {describe_launch_pack_command(args)}"
        for index, args in enumerate(selected_commands, start=1)
    ]


def busy_button_state(is_busy: bool) -> str:
    return "disabled" if is_busy else "normal"


def run_launch_pack_commands(
    *,
    cli_runner: CliRunner = run_cli,
    progress_callback: Callable[[str], None] | None = None,
) -> GuiCommandResult:
    sections = ["Continuity Layer Launch Pack", ""]
    failures = 0
    commands = continuity_launch_pack_commands()
    progress_messages = launch_pack_progress_messages(commands)
    for index, args in enumerate(commands, start=1):
        if progress_callback is not None:
            progress_callback(progress_messages[index - 1])
        result = run_cli_capture(args, cli_runner=cli_runner)
        status = "OK" if result.ok else "FAILED"
        if not result.ok:
            failures += 1
        failure_detail = f" ({launch_pack_step_label(args)} failed)" if not result.ok else ""
        sections.extend([f"{index}. {status}{failure_detail}: {' '.join(args)}", result.display_text, ""])
    if failures:
        sections.append(
            f"Finished with {failures} failed step(s). Saved drafts may still exist from later successful steps. "
            "No approval, queue, or publish action was run."
        )
        return GuiCommandResult(exit_code=1, output="\n".join(sections).strip(), error="")
    sections.append("Launch pack created as drafts. Review, approve, queue, and publish manually.")
    return GuiCommandResult(exit_code=0, output="\n".join(sections).strip(), error="")


def tendril_list_args() -> list[str]:
    return ["tendril", "list"]


def review_drafts_args() -> list[str]:
    return ["review-drafts"]


def review_queue_args() -> list[str]:
    return ["review-queue"]


def approve_item_args(path: str | Path) -> list[str]:
    return ["approve", "--input", str(path)]


def queue_item_args(path: str | Path, slot: str = "afternoon") -> list[str]:
    return ["queue", "--input", str(path), "--slot", slot]


def mark_posted_args(path_or_id: str | Path) -> list[str]:
    value = str(path_or_id).strip()
    if any(separator in value for separator in ("\\", "/", ":")):
        return ["mark-posted", "--input", value]
    return ["mark-posted", "--id", value]


def accounts_status_args() -> list[str]:
    return ["accounts", "status"]


def publish_queue_args(platform: str = "bluesky") -> list[str]:
    return ["publish-queue", "--platform", platform]


def publish_item_args(value: str) -> list[str]:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Type an item id or queued item path first.")
    if any(separator in cleaned for separator in ("\\", "/", ":")):
        return ["publish", "--input", cleaned]
    return ["publish", "--id", cleaned]


def publish_log_args() -> list[str]:
    return ["publish-log"]


def default_open_path(path: Path) -> None:
    startfile = getattr(__import__("os"), "startfile", None)
    if startfile is not None:
        startfile(str(path))


def latest_batch_dir() -> Path | None:
    batches_root = ensure_output_dirs()["batches"]
    candidates = [path for path in batches_root.glob("*") if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def load_dashboard_items(kind: str = "drafts", *, base_dir: Path | None = None) -> list[DashboardItem]:
    directories = ensure_output_dirs(base_dir)
    paths: list[Path] = []
    if kind in {"drafts", "review"}:
        paths = sorted(directories["batches"].rglob("*.json"))
    elif kind == "approved":
        paths = sorted(directories["approved"].glob("*.json"))
    elif kind in {"queue", "queued"}:
        paths = sorted(directories["queue"].glob("*.json"))
    elif kind == "posted":
        paths = sorted(directories["posted"].glob("*.json"))
    elif kind == "all":
        paths = [
            *sorted(directories["batches"].rglob("*.json")),
            *sorted(directories["approved"].glob("*.json")),
            *sorted(directories["queue"].glob("*.json")),
            *sorted(directories["posted"].glob("*.json")),
        ]
    else:
        raise ValueError(f"Unknown dashboard item kind: {kind}")
    items: list[DashboardItem] = []
    for path in paths:
        try:
            item = load_content_item(path)
        except (OSError, ValueError):
            continue
        if kind in {"drafts", "review"} and item.status != "draft":
            continue
        if item.safety.decision == "DISCARD":
            continue
        items.append(_dashboard_item_from_workflow_item(item, path))
    return items


def item_summary_rows(kind: str = "drafts", *, base_dir: Path | None = None) -> list[tuple[str, str, str, str, str, str]]:
    return [
        (item.item_id, item.platform, item.status, item.safety, item.topic, str(item.path))
        for item in load_dashboard_items(kind, base_dir=base_dir)
    ]


def format_item_inspector(path: str | Path) -> str:
    item = load_content_item(path)
    hashtags = " ".join(item.hashtags) if item.hashtags else "None"
    script = "\n".join(item.script_lines)
    reasons = "; ".join(item.safety.reasons) if item.safety.reasons else "Aligned"
    return "\n".join(
        [
            f"ID: {item.id}",
            f"Topic: {item.topic}",
            f"Platform: {item.platform}",
            f"Status: {item.status}",
            f"Safety: {item.safety.decision}",
            f"Created: {item.created_at}",
            f"Source: {item.source_item_id or 'None'}",
            "",
            "Hook:",
            item.hook,
            "",
            "Body:",
            script,
            "",
            "Caption:",
            item.caption,
            "",
            f"Hashtags: {hashtags}",
            f"Suggested time: {item.suggested_post_time}",
            "",
            "Platform notes:",
            item.platform_notes or "None",
            "",
            "Safety reasons:",
            reasons,
            "",
            f"File: {Path(path)}",
        ]
    )


def item_action_state(path: str | Path) -> dict[str, bool]:
    item = load_content_item(path)
    safety_pass = item.safety.decision == "PASS"
    return {
        "approve": item.status == "draft" and safety_pass,
        "queue": item.status == "approved" and safety_pass,
        "publish": item.status == "queued" and item.platform in {"x_bluesky", "bluesky"} and safety_pass,
        "mark_posted": item.status == "queued",
        "open_file": True,
    }


def settings_status_lines(config: AstraConfig | None = None) -> list[str]:
    loaded = config or AstraConfig.load()
    lines = [
        f"Generation provider: {loaded.active_provider} ({loaded.provider})",
        f"Generation model: {loaded.active_generation_model}",
        f"Ollama URL: {loaded.ollama_url}",
        f"OpenAI API key: {'configured' if bool(loaded.api_key) else 'missing'}",
        f"Bluesky handle: {'configured' if bool(loaded.bluesky_posting.handle) else 'missing'}",
        f"Bluesky app password: {'configured' if bool(loaded.bluesky_posting.app_password) else 'missing'}",
        f"Bluesky service URL: {loaded.bluesky_posting.service_url}",
        "Secrets are read from environment variables and are not displayed.",
    ]
    if not loaded.bluesky_posting.handle or not loaded.bluesky_posting.app_password:
        lines.append("If you just configured Bluesky credentials, restart Astra so the app can read them.")
    return lines


def _arg_value(args: Sequence[str], flag: str) -> str | None:
    try:
        index = list(args).index(flag)
    except ValueError:
        return None
    next_index = index + 1
    if next_index >= len(args):
        return None
    return args[next_index]


def _dashboard_item_from_workflow_item(item: WorkflowContentItem, path: Path) -> DashboardItem:
    return DashboardItem(
        item_id=item.id,
        topic=item.topic,
        platform=item.platform,
        status=item.status,
        safety=item.safety.decision,
        path=path,
        created_at=item.created_at,
    )


class AstraGuiApp:
    def __init__(
        self,
        root: tk.Tk,
        *,
        cli_runner: CliRunner = run_cli,
        open_path: OpenPathFunc = default_open_path,
    ) -> None:
        self.root = root
        self.cli_runner = cli_runner
        self.open_path = open_path
        self.root.title("Astra")
        self.root.geometry("980x680")
        self.root.minsize(820, 560)

        self.channel_var = tk.StringVar(value="reddit")
        self.product_var = tk.StringVar(value="Continuity Layer")
        self.reply_scenario_var = tk.StringVar(value="skeptical_user")
        self.count_var = tk.IntVar(value=5)
        self.status_var = tk.StringVar(value="Ready.")
        self.account_status_var = tk.StringVar(value="Accounts: checking...")
        self.queue_status_var = tk.StringVar(value="Queue: 0")
        self.current_item_path: Path | None = None
        self.current_tree_kind = "drafts"
        self.is_busy = False

        self._build_ui()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, padding=(14, 12, 14, 6))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Astra", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="PR and marketing operator for LinnuteeInnovations",
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w")
        ttk.Label(header, textvariable=self.account_status_var, font=("Segoe UI", 9)).grid(row=0, column=1, sticky="e")
        ttk.Label(header, textvariable=self.queue_status_var, font=("Segoe UI", 9)).grid(row=1, column=1, sticky="e")

        dashboard = ttk.Frame(self.root, padding=(12, 0, 12, 6))
        dashboard.grid(row=1, column=0, sticky="nsew")
        dashboard.columnconfigure(1, weight=1)
        dashboard.rowconfigure(0, weight=1)

        self.nav_frame = ttk.Frame(dashboard, padding=(0, 6, 10, 0))
        self.nav_frame.grid(row=0, column=0, sticky="nsw")

        self.notebook = ttk.Notebook(dashboard)
        self.notebook.grid(row=0, column=1, sticky="nsew")

        self._build_create_tab()
        self._build_workflow_tab("Review", "drafts")
        self._build_workflow_tab("Queue", "queue")
        self._build_publish_tab()
        self._build_logs_tab()
        self._build_settings_tab()
        self._build_left_navigation()

        status = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=(8, 4))
        status.grid(row=2, column=0, sticky="ew")
        self.refresh_dashboard()

    def _build_left_navigation(self) -> None:
        for index, label in enumerate(("Create", "Review", "Queue", "Publish", "Logs", "Settings")):
            button = ttk.Button(self.nav_frame, text=label, command=lambda tab=index: self.notebook.select(tab))
            button.grid(row=index, column=0, sticky="ew", pady=(0, 6))

    def _build_create_tab(self) -> None:
        controls = ttk.Frame(self.notebook, padding=(14, 12))
        self.notebook.add(controls, text="Create")
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(5, weight=0)

        self.request_text = tk.Text(controls, height=4, wrap="word", font=("Segoe UI", 10))
        self.request_text.grid(row=0, column=0, columnspan=6, sticky="ew", pady=(0, 8))
        self.request_text.insert("1.0", "draft 5 Reddit posts for Continuity Layer launch")

        ttk.Label(controls, text="Product").grid(row=1, column=0, sticky="w")
        products = ttk.Combobox(
            controls,
            textvariable=self.product_var,
            values=tuple(product_names()),
            state="readonly",
            width=22,
        )
        products.grid(row=2, column=0, sticky="w", padx=(0, 12))

        ttk.Label(controls, text="Channel").grid(row=1, column=1, sticky="w")
        channel = ttk.Combobox(
            controls,
            textvariable=self.channel_var,
            values=("reddit", "x_bluesky", "indie_hackers", "hacker_news", "devto", "email_update", "direct_reply"),
            state="readonly",
            width=18,
        )
        channel.grid(row=2, column=1, sticky="w", padx=(0, 12))

        ttk.Label(controls, text="Count").grid(row=1, column=2, sticky="w")
        ttk.Spinbox(controls, from_=1, to=20, textvariable=self.count_var, width=8).grid(row=2, column=2, sticky="w", padx=(0, 12))

        ttk.Button(controls, text="Run Request", command=self.run_request).grid(row=2, column=3, sticky="w", padx=(0, 8))
        ttk.Button(controls, text="Campaign", command=self.run_campaign).grid(row=2, column=4, sticky="w", padx=(0, 8))
        ttk.Button(controls, text="Draft Posts", command=self.run_posts).grid(row=2, column=5, sticky="e")
        ttk.Button(controls, text="Continuity Launch Pack", command=self.run_continuity_launch_pack).grid(
            row=3,
            column=0,
            sticky="w",
            pady=(10, 0),
        )

        output_frame = ttk.Frame(controls, padding=(0, 12, 0, 0))
        output_frame.grid(row=4, column=0, columnspan=6, sticky="nsew")
        controls.rowconfigure(4, weight=1)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        self.output_text = tk.Text(output_frame, wrap="word", font=("Consolas", 10))
        self.output_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.output_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.output_text.configure(yscrollcommand=scrollbar.set)

    def _build_workflow_tab(self, label: str, kind: str) -> None:
        frame = ttk.Frame(self.notebook, padding=(8, 8))
        self.notebook.add(frame, text=label)
        frame.columnconfigure(0, weight=2)
        frame.columnconfigure(1, weight=3)
        frame.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(frame)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Button(toolbar, text="Refresh", command=lambda k=kind: self.refresh_items(k)).pack(side="left", padx=(0, 6))
        if kind == "queue":
            ttk.Button(toolbar, text="Publish Bluesky Queue", command=lambda: self.run_command(publish_queue_args("bluesky"))).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Open Outputs", command=self.open_outputs).pack(side="right")

        tree = ttk.Treeview(frame, columns=("platform", "status", "safety", "topic", "path"), show="headings", height=14)
        tree.heading("platform", text="Platform")
        tree.heading("status", text="Status")
        tree.heading("safety", text="Safety")
        tree.heading("topic", text="Topic")
        tree.heading("path", text="Path")
        tree.column("platform", width=110, stretch=False)
        tree.column("status", width=90, stretch=False)
        tree.column("safety", width=80, stretch=False)
        tree.column("topic", width=320, stretch=True)
        tree.column("path", width=0, stretch=False)
        tree.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        tree.bind("<<TreeviewSelect>>", lambda _event, k=kind: self.on_item_selected(k))
        setattr(self, f"{kind}_tree", tree)

        inspector = self._make_inspector(frame)
        inspector["frame"].grid(row=1, column=1, sticky="nsew")
        setattr(self, f"{kind}_inspector", inspector)

    def _build_publish_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=(12, 12))
        self.notebook.add(frame, text="Publish")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        controls = ttk.Frame(frame)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(controls, text="Account Status", command=lambda: self.run_command(accounts_status_args())).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Publish Bluesky Queue", command=lambda: self.run_command(publish_queue_args("bluesky"))).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Refresh Log", command=self.refresh_publish_log).pack(side="left")
        self.publish_log_text = tk.Text(frame, wrap="word", font=("Consolas", 10))
        self.publish_log_text.grid(row=1, column=0, sticky="nsew")

    def _build_logs_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=(12, 12))
        self.notebook.add(frame, text="Logs")
        for index in range(5):
            frame.columnconfigure(index, weight=1)
        ttk.Button(frame, text="Create Market Log", command=lambda: self.run_command(market_log_args(save=True))).grid(row=0, column=0, sticky="ew", padx=3)
        ttk.Button(frame, text="Open Logs", command=lambda: self.open_output_kind("logs")).grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Button(frame, text="Open Feedback", command=lambda: self.open_output_kind("feedback")).grid(row=0, column=2, sticky="ew", padx=3)
        ttk.Button(frame, text="Open Experiments", command=lambda: self.open_output_kind("experiments")).grid(row=0, column=3, sticky="ew", padx=3)
        ttk.Button(frame, text="Tendril Tasks", command=lambda: self.run_command(tendril_list_args())).grid(row=0, column=4, sticky="ew", padx=3)

    def _build_settings_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=(12, 12))
        self.notebook.add(frame, text="Settings")
        frame.columnconfigure(0, weight=1)
        self.settings_text = tk.Text(frame, wrap="word", font=("Consolas", 10), height=12)
        self.settings_text.grid(row=0, column=0, sticky="nsew")
        ttk.Button(frame, text="Refresh Settings", command=self.refresh_settings).grid(row=1, column=0, sticky="w", pady=(8, 0))

    def _make_inspector(self, parent: ttk.Frame) -> dict[str, object]:
        frame = ttk.Frame(parent)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        text = tk.Text(frame, wrap="word", font=("Consolas", 10), height=18)
        text.grid(row=0, column=0, sticky="nsew")
        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        actions = {
            "approve": ttk.Button(buttons, text="Approve", command=self.approve_selected_item),
            "queue": ttk.Button(buttons, text="Queue", command=self.queue_selected_item),
            "publish": ttk.Button(buttons, text="Publish", command=self.publish_selected_item),
            "mark_posted": ttk.Button(buttons, text="Mark Posted", command=self.mark_selected_posted),
            "open_file": ttk.Button(buttons, text="Open File", command=self.open_selected_file),
        }
        for button in actions.values():
            button.pack(side="left", padx=(0, 4))
        return {"frame": frame, "text": text, "actions": actions}

    def run_request(self) -> None:
        request = self.request_text.get("1.0", "end").strip()
        try:
            args = conversational_args(request)
        except ValueError as exc:
            self.show_message(str(exc), ok=False)
            return
        self.run_command(args)

    def run_ideas(self) -> None:
        request = self.request_text.get("1.0", "end").strip()
        self.run_command(ideas_args(topic=request, channel=self.channel_var.get(), count=int(self.count_var.get())))

    def run_batch(self) -> None:
        request = self.request_text.get("1.0", "end").strip()
        try:
            args = batch_args(topic=request, count=int(self.count_var.get()))
        except ValueError as exc:
            self.show_message(str(exc), ok=False)
            return
        self.run_command(args)

    def run_campaign(self) -> None:
        request = self.request_text.get("1.0", "end").strip()
        try:
            args = campaign_args(product=self.product_var.get(), goal=request)
        except ValueError as exc:
            self.show_message(str(exc), ok=False)
            return
        self.run_command(args)

    def run_posts(self) -> None:
        request = self.request_text.get("1.0", "end").strip()
        self.run_command(
            posts_args(
                product=self.product_var.get(),
                channel=self.channel_var.get(),
                count=int(self.count_var.get()),
                goal=request,
            )
        )

    def run_reply(self) -> None:
        request = self.request_text.get("1.0", "end").strip()
        self.run_command(
            replies_args(
                product=self.product_var.get(),
                scenario=self.reply_scenario_var.get(),
                user_signal=request,
            )
        )

    def run_publish_item(self) -> None:
        request = self.request_text.get("1.0", "end").strip()
        try:
            args = publish_item_args(request)
        except ValueError as exc:
            self.show_message(str(exc), ok=False)
            return
        self.run_command(args)

    def run_continuity_launch_pack(self) -> None:
        self.run_background_job(
            "Creating launch pack... local model is working and may take a minute.",
            lambda progress: run_launch_pack_commands(cli_runner=self.cli_runner, progress_callback=progress),
        )

    def run_command(self, args: Sequence[str]) -> None:
        self.run_background_job(
            "Running... local model is working and may take a minute.",
            lambda _progress: run_cli_capture(args, cli_runner=self.cli_runner),
        )

    def run_background_job(
        self,
        initial_status: str,
        worker: Callable[[Callable[[str], None]], GuiCommandResult],
    ) -> None:
        if self.is_busy:
            self.show_message("Astra is already running a task. Wait for it to finish before starting another.", ok=False)
            return
        self.is_busy = True
        self.status_var.set(initial_status)
        self._set_action_buttons_busy(True)

        def progress(message: str) -> None:
            self.root.after(0, lambda: self.status_var.set(f"{message} - local model is working."))

        def target() -> None:
            try:
                result = worker(progress)
            except Exception as exc:
                result = GuiCommandResult(exit_code=1, output="", error=str(exc))
            self.root.after(0, lambda: self.finish_background_job(result))

        threading.Thread(target=target, daemon=True).start()

    def finish_background_job(self, result: GuiCommandResult) -> None:
        self.show_message(result.display_text, ok=result.ok)
        self.is_busy = False
        self._set_action_buttons_busy(False)
        self.refresh_dashboard()

    def show_message(self, message: str, *, ok: bool = True) -> None:
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", message)
        self.status_var.set("Ready." if ok else "Needs attention.")

    def open_outputs(self) -> None:
        path = open_outputs_directory()
        self.show_message(f"Outputs folder: {path}")

    def open_latest_batch(self) -> None:
        path = latest_batch_dir()
        if path is None:
            self.show_message("No batch folder found yet.", ok=False)
            return
        self.open_path(path)
        self.show_message(f"Latest batch folder: {path}")

    def open_queue(self) -> None:
        path = ensure_output_dirs()["queue"]
        self.open_path(path)
        self.show_message(f"Queue folder: {path}")

    def open_output_kind(self, kind: str) -> None:
        path = ensure_output_dirs()[kind]
        self.open_path(path)
        self.show_message(f"{kind.title()} folder: {path}")

    def open_tendril(self) -> None:
        path = TendrilSettings.from_repo_root().data_root
        path.mkdir(parents=True, exist_ok=True)
        self.open_path(path)
        self.show_message(f"Tendril folder: {path}")

    def refresh_dashboard(self) -> None:
        self.refresh_items("drafts")
        self.refresh_items("queue")
        self.refresh_publish_log()
        self.refresh_settings()
        queue_count = len(load_dashboard_items("queue"))
        self.queue_status_var.set(f"Queue: {queue_count}")
        status = run_cli_capture(accounts_status_args(), cli_runner=self.cli_runner)
        summary = status.display_text.splitlines()[0] if status.display_text.splitlines() else "unknown"
        self.account_status_var.set(f"Accounts: {summary}")

    def refresh_items(self, kind: str) -> None:
        tree = getattr(self, f"{kind}_tree")
        for row in tree.get_children():
            tree.delete(row)
        for row in item_summary_rows(kind):
            item_id, platform, status, safety, topic, path = row
            tree.insert("", "end", iid=path, values=(platform, status, safety, topic, path))
        inspector = getattr(self, f"{kind}_inspector")
        text: tk.Text = inspector["text"]
        text.delete("1.0", "end")
        text.insert("1.0", "Select an item to inspect it.")
        self._set_inspector_actions(inspector, {})

    def on_item_selected(self, kind: str) -> None:
        tree = getattr(self, f"{kind}_tree")
        selection = tree.selection()
        if not selection:
            return
        path = Path(selection[0])
        self.current_item_path = path
        self.current_tree_kind = kind
        inspector = getattr(self, f"{kind}_inspector")
        text: tk.Text = inspector["text"]
        text.delete("1.0", "end")
        try:
            text.insert("1.0", format_item_inspector(path))
            self._set_inspector_actions(inspector, item_action_state(path))
        except (OSError, ValueError) as exc:
            text.insert("1.0", str(exc))
            self._set_inspector_actions(inspector, {})

    def approve_selected_item(self) -> None:
        if self.current_item_path:
            self.run_command(approve_item_args(self.current_item_path))

    def queue_selected_item(self) -> None:
        if self.current_item_path:
            self.run_command(queue_item_args(self.current_item_path))

    def publish_selected_item(self) -> None:
        if self.current_item_path:
            self.run_command(publish_item_args(str(self.current_item_path)))

    def mark_selected_posted(self) -> None:
        if self.current_item_path:
            self.run_command(mark_posted_args(self.current_item_path))

    def open_selected_file(self) -> None:
        if self.current_item_path:
            self.open_path(self.current_item_path)
            self.show_message(f"Opened: {self.current_item_path}")

    def refresh_publish_log(self) -> None:
        if not hasattr(self, "publish_log_text"):
            return
        results = load_publish_log()
        text = self.publish_log_text
        text.delete("1.0", "end")
        if not results:
            text.insert("1.0", "Publish log is empty.")
            return
        lines = []
        for result in results:
            target = result.external_url or result.external_id or result.error or "no target"
            lines.append(f"{result.published_at} | {result.platform} | {result.status} | {result.item_id} | {target}")
        text.insert("1.0", "\n".join(lines))

    def refresh_settings(self) -> None:
        if not hasattr(self, "settings_text"):
            return
        self.settings_text.delete("1.0", "end")
        self.settings_text.insert("1.0", "\n".join(settings_status_lines()))

    def _set_inspector_actions(self, inspector: dict[str, object], states: dict[str, bool]) -> None:
        actions: dict[str, ttk.Button] = inspector["actions"]
        for name, button in actions.items():
            button.configure(state="normal" if states.get(name, False) else "disabled")

    def _set_action_buttons_busy(self, is_busy: bool) -> None:
        for button in self._iter_buttons(self.root):
            button.configure(state=busy_button_state(is_busy))

    def _iter_buttons(self, widget: tk.Widget) -> list[ttk.Button]:
        buttons: list[ttk.Button] = []
        for child in widget.winfo_children():
            if isinstance(child, ttk.Button):
                buttons.append(child)
            buttons.extend(self._iter_buttons(child))
        return buttons


def main() -> int:
    root = tk.Tk()
    AstraGuiApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
