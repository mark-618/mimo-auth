# mimo-auth

`mimo-auth` is a local Xiaomi MiMo auth profile switcher for Claude Code.

It is inspired by `codex-auth`, but intentionally smaller in scope: it manages multiple local MiMo API / Token Plan profiles and switches the MiMo credentials used by Claude Code with one command.

## What It Is

`mimo-auth` is:

- a local profile manager for Xiaomi MiMo credentials
- a Claude Code `settings.json` switcher
- a small Python CLI with no runtime dependencies

`mimo-auth` is not:

- a generic multi-client exporter
- a chat UI
- a proxy server
- a telemetry client
- an account registration tool
- a cookie scraper
- a login bypass tool

Version `0.1.0` only supports Claude Code. It does not export settings for Cursor, Zed, Continue, Cherry Studio, or other clients.

## Official MiMo Docs

Create and manage your MiMo API / Token Plan credentials from the official Xiaomi MiMo API Open Platform:

[https://platform.xiaomimimo.com/docs/en-US/welcome](https://platform.xiaomimimo.com/docs/en-US/welcome)

`mimo-auth` only stores and switches credentials locally. It does not create accounts, fetch cookies, or bypass any login flow.

## What It Changes

Claude Code usually stores local settings at:

```text
~/.claude/settings.json
```

When you switch profiles, `mimo-auth` preserves the rest of the file and only updates:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "<profile.base_url>",
    "ANTHROPIC_AUTH_TOKEN": "<profile.api_key>"
  }
}
```

Before changing `settings.json`, it creates a backup under:

```text
~/.claude/mimo-auth-backups/
```

Profiles are stored locally at:

```text
~/.mimo-auth/profiles.json
```

The profile store is written with file mode `0600`.

## Install From Source

```bash
git clone <your-fork-or-repo-url>
cd mimo-auth
python -m pip install -e .
```

Verify the CLI:

```bash
mimo-auth doctor
```

## Quick Start

Add a Token Plan profile:

```bash
mimo-auth add-token me
```

Add a pay-as-you-go API profile:

```bash
mimo-auth add-api me
```

If the alias already exists, `mimo-auth` automatically keeps the new profile instead of overwriting the old one:

```text
Profile 'me' already exists; using 'me-plan' instead.
Profile 'me' already exists; using 'me-bal' instead.
Profile 'me' already exists; using 'me-bal-2' instead.
```

Suffix rules:

- `token-plan` profiles use `-plan`
- pay-as-you-go API profiles use `-bal`
- additional conflicts use `-2`, `-3`, and so on

List profiles:

```bash
mimo-auth list
```

Switch Claude Code to a profile:

```bash
mimo-auth switch
```

Or switch directly:

```bash
mimo-auth switch me-plan
mimo-auth switch 2
mimo-auth use me-bal
```

Show the currently active profile:

```bash
mimo-auth current
```

Test whether stored credentials can call MiMo:

```bash
mimo-auth check
mimo-auth check me-plan
```

`check` sends a minimal real API request only when you run it. It may consume a tiny amount of quota. Failed checks include a short explanation:

```text
Checking me-plan (token-plan, tp-****abcd) ...
  FAILED (HTTP 401)
  Reason: Authentication failed. Check whether the API key/token is correct and still active.

Checking me-bal (api, sk-****wxyz) ...
  FAILED (HTTP 402)
  Reason: Payment or quota required. Check account balance, billing status, or Token Plan quota.
```

Remove a profile:

```bash
mimo-auth remove
mimo-auth remove me-plan
mimo-auth remove 2 --yes
```

## Interactive Add

You can also use the interactive wizard:

```bash
mimo-auth add
```

It asks for:

- profile alias
- credential type
- display name
- API key
- whether to use the profile for Claude Code immediately

If the API key is omitted in shortcut commands, `mimo-auth` prompts for it without echoing input.

## Default MiMo Endpoints

For pay-as-you-go API profiles:

```text
https://api.xiaomimimo.com/anthropic
```

For Token Plan profiles:

```text
https://token-plan-cn.xiaomimimo.com/anthropic
```

For custom or advanced profiles, use:

```bash
mimo-auth add custom \
  --type api \
  --base-url "https://custom.example.com/anthropic"
```

## Command Reference

```text
mimo-auth add [alias]
mimo-auth add-api <alias>
mimo-auth add-token <alias>
mimo-auth list
mimo-auth show <alias|number|fragment>
mimo-auth switch [alias|number|fragment]
mimo-auth use [alias|number|fragment]
mimo-auth current
mimo-auth check [alias|number|fragment]
mimo-auth remove [alias|number|fragment]
mimo-auth doctor
```

Global options:

```text
--store-path <path>      Defaults to ~/.mimo-auth/profiles.json
--settings-path <path>   Defaults to ~/.claude/settings.json
```

Use `--force` with `add`, `add-api`, or `add-token` only when you intentionally want to overwrite an exact alias.

## Profile Fields

Each profile contains:

- `alias`
- `name`
- `type`: `api` or `token-plan`
- `base_url`
- `api_key`
- `default_model`
- `created_at`
- `updated_at`

## Security Notes

- API keys are masked in `list`, `show`, `current`, `doctor`, `check`, and `switch` output.
- Masked output looks like `sk-****abcd`.
- `mimo-auth` does not upload keys.
- `mimo-auth` does not send telemetry.
- `mimo-auth` does not proxy traffic.
- `mimo-auth` only edits local files.
- `mimo-auth check` is the only command that sends a MiMo API request.
- `mimo-auth check` never prints the full API key, even when the request fails.

## Development

Install with test dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Build package artifacts:

```bash
python -m pip install build
python -m build
```

## License

MIT
