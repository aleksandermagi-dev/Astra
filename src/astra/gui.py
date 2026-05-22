from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from typing import Callable, Sequence

from .cli import run_cli
from .config import AstraConfig
from .outputs import ensure_output_dirs, open_outputs_directory
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


def tendril_list_args() -> list[str]:
    return ["tendril", "list"]


def review_drafts_args() -> list[str]:
    return ["review-drafts"]


def review_queue_args() -> list[str]:
    return ["review-queue"]


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

        self._build_ui()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        header = ttk.Frame(self.root, padding=(14, 12, 14, 4))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Astra", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="PR and marketing operator for LinnuteeInnovations",
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w")

        controls = ttk.Frame(self.root, padding=(14, 6))
        controls.grid(row=1, column=0, sticky="ew")
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

        quick = ttk.Frame(self.root, padding=(14, 0, 14, 6))
        quick.grid(row=3, column=0, sticky="ew")
        for index in range(11):
            quick.columnconfigure(index, weight=1)
        buttons = [
            ("Accounts", lambda: self.run_command(accounts_status_args())),
            ("Publish Bluesky", lambda: self.run_command(publish_queue_args("bluesky"))),
            ("Publish Log", lambda: self.run_command(publish_log_args())),
            ("Publish Item", self.run_publish_item),
            ("Review Drafts", lambda: self.run_command(review_drafts_args())),
            ("Review Queue", lambda: self.run_command(review_queue_args())),
            ("Market Log", lambda: self.run_command(market_log_args(save=True))),
            ("Tendril Tasks", lambda: self.run_command(tendril_list_args())),
            ("Open Outputs", self.open_outputs),
            ("Open Feedback", lambda: self.open_output_kind("feedback")),
            ("Open Experiments", lambda: self.open_output_kind("experiments")),
        ]
        for column, (label, command) in enumerate(buttons):
            ttk.Button(quick, text=label, command=command).grid(row=0, column=column, sticky="ew", padx=2)

        output_frame = ttk.Frame(self.root, padding=(14, 0, 14, 6))
        output_frame.grid(row=2, column=0, sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        self.output_text = tk.Text(output_frame, wrap="word", font=("Consolas", 10))
        self.output_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.output_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.output_text.configure(yscrollcommand=scrollbar.set)

        status = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=(8, 4))
        status.grid(row=4, column=0, sticky="ew")

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

    def run_command(self, args: Sequence[str]) -> None:
        self.status_var.set("Running...")
        self.root.update_idletasks()
        result = run_cli_capture(args, cli_runner=self.cli_runner)
        self.show_message(result.display_text, ok=result.ok)

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


def main() -> int:
    root = tk.Tk()
    AstraGuiApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
