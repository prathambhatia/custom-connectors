# Custom connectors for Claude Code

Six Claude Code skills that replace the **Slack, Fathom, ClickUp, Vercel and AWS** MCPs, and the
reading side of the **Figma** MCP. Claude calls each app's API directly with `curl` (or the `aws`
CLI), using your own login saved in your Mac's Keychain.

## Install (2 commands, inside Claude Code)

```
/plugin marketplace add prathambhatia/custom-connectors
/plugin install custom-connectors@custom-connectors
```

Start a new session and you're done. Nothing runs at install time: the skills are just
instructions Claude reads when you ask for that app. The files live in
`~/.claude/plugins/` on your Mac, not in any of your project repos.

**Then turn off the MCPs these replace**, otherwise they keep loading their tools every session.
Type `/mcp`, pick each of Slack, Fathom, ClickUp, Vercel and AWS, and disable it. Connectors added
through claude.ai are under claude.ai, Settings, Connectors. **Keep the Figma MCP** if you edit
designs or use design-to-code; the Figma connector only reads.

Update later with `/plugin marketplace update custom-connectors`.

## Optional: make Claude always pick the connectors

If you keep any of these MCPs switched on, Claude might occasionally use an MCP tool instead of the
connector. To rule that out, add this line to your global `~/.claude/CLAUDE.md`:

```
For Slack, Fathom, ClickUp, Vercel and AWS, use the custom-connectors skills instead of the MCPs.
For Figma, use figma-connector for reading, and the Figma MCP only for editing or design-to-code.
```

You don't need this if you've disabled the MCPs with `/mcp`.

## What each one does

| Connector | What Claude can do |
|---|---|
| **slack-connector** | Send, reply in threads, DM, edit, delete, upload files, read channels and threads, search messages, find channels and people, react, read profiles |
| **fathom-connector** | List your meetings, find one by title, person, company or date, get the summary, transcript and action items, search what was said across calls |
| **clickup-connector** | Create, update, search and delete tasks, comments, tags, checklists, attachments, custom fields, subtasks and time entries |
| **vercel-connector** | Deploy, redeploy, check status, read build and live runtime logs, manage env vars, promote or roll back, list domains. No Vercel CLI needed |
| **aws-connector** | SSO login, SSM tunnels to private databases, Run Command, Parameter Store, logs and Logs Insights, ECS, RDS, Secrets Manager, S3, CloudFront, Lambda, costs, and anything else the aws CLI can do |
| **figma-connector** | Read pages, frames and node details, render frames to PNG/SVG, version history, read and post comments. **Read-only** |

## Why this beats the MCPs

**An MCP loads every one of its tools into every session**, whether you use them or not:

| MCP | Tools it loads | Before: MCP tokens | **Before** (share of 1M) | After: connector tokens | **After** (share of 1M) |
|---|---|---|---|---|---|
| Vercel | 244 | ~145k (measured) | **14.5%** | ~140 | **0.014%** |
| ClickUp | 65 | ~30k | **3.0%** | ~130 | **0.013%** |
| Figma | 45 | ~20k | **2.0%** | ~150 | **0.015%** |
| Slack | 19 | ~10k | **1.0%** | ~90 | **0.009%** |
| Fathom | 9 | ~3k | **0.3%** | ~140 | **0.014%** |
| **Total (5 MCPs)** | **382** | **~208k** | **~21%** | **~650** | **~0.07%** |

**Before ~21% → after ~0.07% of a 1M context**, so about a fifth of the window comes back in every
session. The AWS connector adds another ~150 tokens (it has no MCP to compare against), for ~800 total.

"After" is what loads in every session, measured by Claude Code itself with `claude plugin details`.
When you actually use a connector, that one adds 1k–2k tokens for that session only. Vercel's "before"
was measured by fetching its full tool list; the other "before" numbers are estimated from their tool
counts. Run `/context` before and after to see your own numbers.

- **Faster:** no MCP server in between, Claude calls the app's API directly.
- **Acts as you:** your own token, so messages and comments show your name.
- **Works on any Claude account:** your logins live in your Mac's Keychain.

## First use

Just ask Claude to do something on that app. The first time, it asks for one thing:

| App | What it asks for |
|---|---|
| Slack | Open https://app.slack.com in Chrome and sign in. Claude reads your session from Chrome (click **Allow** when macOS asks about "Chrome Safe Storage") |
| Fathom | API key from https://fathom.video/customize#api-access-header |
| ClickUp | Personal token from https://app.clickup.com/settings/apps |
| Vercel | Token from https://vercel.com/account/settings/tokens |
| Figma | Personal access token from Figma, Settings, Security |
| AWS | Nothing if you already use the `aws` CLI with SSO; otherwise your SSO start URL |

Tokens go into your Keychain and never leave your Mac. This repo contains no credentials.

## Without the plugin system

```bash
curl -fsSL https://raw.githubusercontent.com/prathambhatia/custom-connectors/main/install.sh | bash
```

Copies the six skills into `~/.claude/skills/`. Read the script first if you prefer. Use one way or
the other, not both, or every skill shows up twice.

## Limits

- **Mac only.** Logins live in the macOS Keychain, and Slack setup reads from Google Chrome.
- **Slack can't schedule messages** with a browser session token. Schedule from the Slack app.
- **Vercel runtime logs are live only.** Old logs are in the Vercel dashboard.
- **Figma is read-only.** No editing or design-to-code.
- **AWS writes to production always ask twice** before running.
- Needs `curl`, `jq` and `python3` (`brew install jq` if `jq` is missing), plus the `aws` CLI for AWS.
