# Contributing to mimo-auth

Thanks for helping improve `mimo-auth`.

`mimo-auth` is intentionally small: it is a local Xiaomi MiMo profile switcher for Claude Code. Please keep changes aligned with that scope.

## Scope

Good fits:

- Claude Code `settings.json` profile switching
- local MiMo API / Token Plan profile management
- safer local file handling
- better CLI usability
- clearer diagnostics and docs

Out of scope for now:

- chat UI
- proxy server
- telemetry
- account registration automation
- cookie scraping
- login bypass
- exports for Cursor, Zed, Continue, Cherry Studio, or other clients

## Local Development

```bash
git clone https://github.com/mark-618/mimo-auth.git
cd mimo-auth
python -m pip install -e ".[dev]"
pytest
```

Run the CLI locally:

```bash
mimo-auth help
mimo-auth doctor
```

Build package artifacts:

```bash
python -m pip install build
python -m build
```

## Pull Requests

Before opening a PR:

- run `pytest`
- avoid printing full API keys in output, logs, tests, or docs
- preserve existing Claude Code settings outside the managed `env` fields
- keep behavior local-only unless the command explicitly documents a network call
- update README or help text when user-facing commands change
- add or update tests for behavior changes

`mimo-auth check` is allowed to make a MiMo API request. Other commands should not call remote services.

## Bug Reports

Please include:

- OS
- Python version
- `mimo-auth` version or commit
- install method
- command run
- expected result
- actual result
- sanitized output with API keys masked

Never paste full API keys, Token Plan keys, cookies, or account credentials.

## Security Reports

If you find a security issue, do not open a public issue with secrets or exploit details. Open a minimal issue asking for maintainer contact, or use GitHub private vulnerability reporting if it is enabled for the repository.
