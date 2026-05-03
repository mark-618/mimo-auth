# Security Policy

`mimo-auth` handles local API keys, so security reports are taken seriously.

## Supported Versions

The current `main` branch and the latest GitHub Release are supported for security fixes.

## Reporting a Vulnerability

Do not open a public issue that contains:

- full MiMo API keys
- Token Plan keys
- Claude Code `settings.json` with real credentials
- cookies
- account credentials
- exploit details that would put users at immediate risk

If GitHub private vulnerability reporting is enabled for this repository, use it. Otherwise, open a minimal public issue asking for maintainer contact without including secrets or exploit details.

## What mimo-auth Does Not Do

`mimo-auth` does not:

- upload API keys
- send telemetry
- proxy model traffic
- create accounts
- scrape cookies
- bypass login flows

The only command that makes a MiMo API request is `mimo-auth check`, and it only runs when the user explicitly invokes it.

## Secret Handling Rules

Maintainers and contributors should:

- never commit real API keys or Token Plan keys
- never print full keys in CLI output
- keep test keys obviously fake, such as `sk-demo-...` or `tp-test-...`
- mask keys in examples and logs
- preserve unrelated Claude Code settings when updating `settings.json`
