# Changelog

All notable changes to `mimo-auth` will be documented in this file.

The project follows semantic versioning while it is pre-1.0: patch releases fix bugs, minor releases may add or adjust CLI behavior.

## 0.1.0 - 2026-05-03

Initial MVP.

- Add local MiMo profile store with masked key output
- Support `api` and `token-plan` profile types
- Switch Claude Code by updating only `env.ANTHROPIC_BASE_URL` and `env.ANTHROPIC_AUTH_TOKEN`
- Preserve other Claude Code `settings.json` fields
- Back up `settings.json` before switching
- Add `add`, `add-api`, `add-token`, `list`, `show`, `switch`, `use`, `current`, `status`, `check`, `remove`, `edit`, `rename`, `doctor`, and `help`
- Add interactive model picker using official MiMo model IDs
- Add credential checks with HTTP status explanations
- Add colored CLI output with `NO_COLOR` and `MIMO_AUTH_COLOR` support
