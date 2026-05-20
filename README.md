# Astra v1

Astra is the PR and marketing operator for LinnuteeInnovations. It maintains the company voice, plans product campaigns, drafts posts and replies, tracks market response, and helps turn buyer feedback into positioning and product experiments.

Continuity Layer is the current active campaign, but Astra is company-level: products live under the LinnuteeInnovations umbrella.

## Operating Rules

- Draft, plan, track, analyze, and help respond.
- Do not blindly spam or auto-post.
- Keep public actions as reviewed drafts until approved.
- Use a practical builder voice: plainspoken, transparent, useful, technically credible, and non-hypey.
- Disclose product constraints and trust boundaries plainly.

## Active Campaign

Continuity Layer positioning:

```text
Stop re-explaining your project to AI.
```

Continuity Layer is shared project memory for humans and AI agents. It scans a project folder, tracks current state, decisions, detected checks, drift risks, unresolved branches, and project health. It exposes compact continuity packets through CLI/MCP so tools like Codex, Claude, Cursor-style agents, or local agents can resume work without pasted context.

Offer:

- $19 paid early access
- Optional $99 setup session through the feedback/setup form

Links:

- GitHub: https://github.com/aleksandermagi-dev/ContinuityAgent
- Checkout: https://linnuteeinnovations.lemonsqueezy.com/checkout/buy/d672a3ab-665e-488d-ba78-44f59c0b0140
- Feedback/setup form: https://tally.so/r/VLbJVy

Trust points:

- local-first
- SQLite-backed
- Windows-first private beta
- no silent file mutation
- detected commands are recommended, not auto-run
- agent updates create drafts until reviewed
- installer is not code-signed yet, so Windows may warn users

## Fast Start

Install the project in editable mode once:

```powershell
python -m pip install -e .
```

Run the desktop UI:

```powershell
python astra-gui.py
```

Or generate PR ideas and campaign drafts from the CLI:

```powershell
.\astra ideas --topic "Continuity Layer launch" --platform all
.\astra products list
.\astra campaign create --product "Continuity Layer" --goal "7-day launch"
.\astra posts draft --product "Continuity Layer" --channel reddit --count 5 --goal "launch"
.\astra replies draft --product "Continuity Layer" --scenario why_not_readme_notion
.\astra batch --topic "7-day Continuity Layer launch campaign" --count 7 --format md
.\astra format --input "C:\path\to\batch_folder" --platform reddit
.\astra market-log-template --format md
```

You can also talk to Astra conversationally:

```powershell
.\astra give me 7 ideas about Continuity Layer launch for reddit
.\astra generate me 5 on skeptical replies for local-first AI tools
.\astra format the latest batch for Hacker News
.\astra review drafts
.\astra review queue
```

## Supported Channels

Astra supports PR and marketing channels:

- `reddit`
- `x_bluesky`
- `indie_hackers`
- `hacker_news`
- `devto`
- `email_update`
- `direct_reply`

Legacy short-form channels are still accepted for compatibility:

- `tiktok`
- `youtube_shorts`

## CLI Commands

```powershell
astra products list
astra products show "Continuity Layer"
astra campaign create --product "Continuity Layer" --goal "7-day launch"
astra posts draft --product "Continuity Layer" --channel hacker_news --count 3 --goal "Show HN launch"
astra replies draft --product "Continuity Layer" --scenario skeptical_user --user-signal "How is this different from docs?"
astra feedback summarize --input market-log.csv
astra experiments suggest --input market-log.csv
astra ideas --topic "Continuity Layer launch" --count 7 --platform all
astra batch --topic "7-day Continuity Layer launch campaign" --count 7 --format md
astra format --input "C:\path\to\batch_folder" --platform hacker_news
astra market-log-template --format md
astra approve --input "C:\path\to\draft.json"
astra queue --input "C:\path\to\approved.json" --slot morning
astra review-drafts
astra review-queue
astra mark-posted --input "C:\path\to\queued.json"
astra log-post --input "C:\path\to\queued.json" --post-id-or-url "https://example.com/post/123"
astra analyze --input performance.json
```

## Outputs

Astra saves workflow content into `outputs/`:

- `outputs/ideas/`
- `outputs/campaigns/`
- `outputs/batches/`
- `outputs/replies/`
- `outputs/feedback/`
- `outputs/experiments/`
- `outputs/queue/`
- `outputs/approved/`
- `outputs/posted/`
- `outputs/logs/`

Workflow items are JSON so they are easy to review manually and automate later.

## Product Profiles

Astra can work at the company level or against a product profile. Continuity Layer is the default product profile in `astra.config.json`, and future LinnuteeInnovations products can be added under `products`.

Use `company` in the GUI product selector when the draft should be about LinnuteeInnovations instead of one product.

## Configuration

Set `OPENAI_API_KEY` to enable generation.

Optional environment variables:

- `ASTRA_MODEL`
- `ASTRA_CONFIG`

`ASTRA_CONFIG` can point to a JSON file with company defaults, active product facts, channels, audience, and tone.

## Build the EXE

```powershell
build_exe.bat
```

This uses PyInstaller to package the Tkinter desktop UI into `Astra.exe`.

To build the older console launcher:

```powershell
build_console_exe.bat
```
