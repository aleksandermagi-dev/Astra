# Astra Coding Continuity

Continuity Layer assists coding sessions for Astra. Astra itself does not call, depend on, or display Continuity Layer. This workflow exists to keep implementation work grounded, reduce drift, and preserve reviewable coding decisions.

## Start Of Session

From `C:\Users\aleks\Desktop\Project continuity agent`, run:

```powershell
npm run continuity -- packet --path "C:\Users\aleks\Desktop\astra" --offline --mode coding-agent --budget small
```

Use the packet to confirm:

- Astra is still the LinnuteeInnovations PR and marketing operator.
- Continuity Layer is the active campaign, not Astra's whole identity.
- The current architecture and relevant source files match the requested work.
- The detected validation command is still appropriate.
- Generated folders are not being treated as source truth.

## Drift Controls

Before editing Astra, check the requested change against these boundaries:

- Do not drift back into generic short-form or TikTok-only content generation.
- Do not merge Astra with the future Interaction/Control Layer.
- Do not add Continuity Layer as an Astra runtime dependency unless explicitly requested.
- Keep public account actions approval-gated: draft, approved, queued, published, logged.
- Keep the desktop app local-first and Windows-friendly.

## End Of Session

Run the detected validation command from the Astra repo:

```powershell
python -m pytest -q
```

If GUI or packaging behavior changed, rebuild the executable:

```powershell
cmd /c build_exe.bat
```

If the Continuity API is already running, record a draft-only update:

```powershell
npm run continuity -- update --path "C:\Users\aleks\Desktop\astra" --note "<summary, tests, decision>" --source codex
```

Continuity updates are review-required drafts. They must not automatically accept memory or mutate Astra source files.
