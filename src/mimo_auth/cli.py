"""Command line interface for mimo-auth."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path
from typing import Iterable, Optional

from .check import check_profile
from .claude import (
    DEFAULT_CLAUDE_SETTINGS_PATH,
    SettingsError,
    apply_profile,
    read_current_env,
)
from .models import Profile, mask_api_key, validate_profile_type
from .models import API_BASE_URL, DEFAULT_MODEL, TOKEN_PLAN_BASE_URL
from .store import DEFAULT_STORE_PATH, ProfileStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mimo-auth",
        description="Switch Xiaomi MiMo API/Token Plan profiles for Claude Code.",
    )
    parser.add_argument(
        "--store-path",
        type=Path,
        default=DEFAULT_STORE_PATH,
        help="Profile store path. Defaults to ~/.mimo-auth/profiles.json.",
    )
    parser.add_argument(
        "--settings-path",
        type=Path,
        default=DEFAULT_CLAUDE_SETTINGS_PATH,
        help="Claude Code settings path. Defaults to ~/.claude/settings.json.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add or update a MiMo profile.")
    add_parser.add_argument("alias", nargs="?")
    add_parser.add_argument("--name")
    add_parser.add_argument("--type", choices=["api", "token-plan"])
    add_parser.add_argument("--base-url")
    add_parser.add_argument("--api-key")
    add_parser.add_argument("--default-model", default=DEFAULT_MODEL)
    add_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing profile with the same alias.",
    )

    add_api_parser = subparsers.add_parser(
        "add-api",
        help="Add a pay-as-you-go MiMo API profile.",
    )
    add_api_parser.add_argument("alias")
    add_api_parser.add_argument("--name")
    add_api_parser.add_argument("--api-key")
    add_api_parser.add_argument("--default-model", default=DEFAULT_MODEL)
    add_api_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing profile with the same alias.",
    )

    add_token_parser = subparsers.add_parser(
        "add-token",
        help="Add a MiMo Token Plan profile.",
    )
    add_token_parser.add_argument("alias")
    add_token_parser.add_argument("--name")
    add_token_parser.add_argument("--api-key")
    add_token_parser.add_argument("--default-model", default=DEFAULT_MODEL)
    add_token_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing profile with the same alias.",
    )

    subparsers.add_parser("list", help="List profiles with masked API keys.")

    show_parser = subparsers.add_parser("show", help="Show one profile.")
    show_parser.add_argument("alias")

    switch_parser = subparsers.add_parser(
        "switch",
        help="Switch Claude Code to a profile.",
    )
    switch_parser.add_argument("alias", nargs="?")

    use_parser = subparsers.add_parser(
        "use",
        help="Alias for switch.",
    )
    use_parser.add_argument("alias", nargs="?")

    current_parser = subparsers.add_parser(
        "current",
        help="Show the profile matching current Claude Code settings.",
    )
    current_parser.add_argument(
        "--show-unmatched",
        action="store_true",
        help="Show masked current settings even when no profile matches.",
    )

    remove_parser = subparsers.add_parser("remove", help="Remove a profile.")
    remove_parser.add_argument("alias", nargs="?")
    remove_parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Remove without confirmation.",
    )

    check_parser = subparsers.add_parser(
        "check",
        help="Test MiMo profile credentials with a minimal API call.",
    )
    check_parser.add_argument("alias", nargs="?")
    check_parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model used for the test call. Defaults to {DEFAULT_MODEL}.",
    )
    check_parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Request timeout in seconds. Defaults to 15.",
    )

    subparsers.add_parser("doctor", help="Check local paths and current settings.")
    return parser


def command_add(args: argparse.Namespace, store: ProfileStore) -> int:
    interactive = args.alias is None
    if interactive:
        print("Add MiMo profile")
        print()
    alias = args.alias or prompt_required("Profile alias")
    profile_type = args.type or prompt_profile_type()
    base_url = args.base_url or default_base_url(profile_type)
    name = args.name or prompt_default("Display name", alias)
    api_key = args.api_key or getpass.getpass("MiMo API key: ")
    saved_alias = save_profile(
        store,
        alias=alias,
        name=name,
        profile_type=profile_type,
        base_url=base_url,
        api_key=api_key,
        default_model=args.default_model or DEFAULT_MODEL,
        force=args.force,
    )
    if interactive and prompt_yes_no("Use it for Claude Code now?", default=True):
        profile = require_profile(store, saved_alias)
        return switch_to_profile(args, store, profile)
    return 0


def command_add_api(args: argparse.Namespace, store: ProfileStore) -> int:
    api_key = args.api_key or getpass.getpass("MiMo API key: ")
    save_profile(
        store,
        alias=args.alias,
        name=args.name or args.alias,
        profile_type="api",
        base_url=API_BASE_URL,
        api_key=api_key,
        default_model=args.default_model,
        force=args.force,
    )
    return 0


def command_add_token(args: argparse.Namespace, store: ProfileStore) -> int:
    api_key = args.api_key or getpass.getpass("MiMo Token Plan key: ")
    save_profile(
        store,
        alias=args.alias,
        name=args.name or args.alias,
        profile_type="token-plan",
        base_url=TOKEN_PLAN_BASE_URL,
        api_key=api_key,
        default_model=args.default_model,
        force=args.force,
    )
    return 0


def save_profile(
    store: ProfileStore,
    *,
    alias: str,
    name: str,
    profile_type: str,
    base_url: str,
    api_key: str,
    default_model: str,
    force: bool,
) -> str:
    validate_profile_type(profile_type)
    profiles = store.load()
    existing = profiles.get(alias)
    if existing:
        if not force:
            original_alias = alias
            alias = available_alias(alias, profile_type, profiles)
            existing = None
            print(f"Profile '{original_alias}' already exists; using '{alias}' instead.")
    if existing:
        profile = existing.with_updates(
            name=name,
            profile_type=profile_type,
            base_url=base_url,
            api_key=api_key,
            default_model=default_model,
        )
        action = "Updated"
    else:
        profile = Profile.create(
            alias=alias,
            name=name,
            profile_type=profile_type,
            base_url=base_url,
            api_key=api_key,
            default_model=default_model,
        )
        action = "Added"
    store.upsert(profile)
    print(f"{action} profile '{profile.alias}' ({profile.name}).")
    return profile.alias


def available_alias(
    alias: str,
    profile_type: str,
    profiles: dict[str, Profile],
) -> str:
    suffix = "plan" if profile_type == "token-plan" else "bal"
    candidate = f"{alias}-{suffix}"
    if candidate not in profiles:
        return candidate
    index = 2
    while True:
        numbered_candidate = f"{candidate}-{index}"
        if numbered_candidate not in profiles:
            return numbered_candidate
        index += 1


def command_list(args: argparse.Namespace, store: ProfileStore) -> int:
    profiles = sorted(store.list_profiles(), key=lambda profile: profile.alias)
    if not profiles:
        print("No profiles found.")
        return 0
    active_alias = active_alias_for_list(args, store)
    print_profile_table(profiles, active_alias)
    return 0


def command_show(args: argparse.Namespace, store: ProfileStore) -> int:
    profile = resolve_profile(store, args.alias)
    print_profile(profile)
    return 0


def command_switch(args: argparse.Namespace, store: ProfileStore) -> int:
    profile = pick_profile(args, store) if args.alias is None else resolve_profile(store, args.alias)
    return switch_to_profile(args, store, profile)


def switch_to_profile(
    args: argparse.Namespace,
    store: ProfileStore,
    profile: Profile,
) -> int:
    backup_path = apply_profile(args.settings_path, profile)
    store.set_active_alias(profile.alias)
    print(f"Claude Code now uses '{profile.alias}' ({profile.name}).")
    if backup_path:
        print(f"Backup: {backup_path}")
    else:
        print("Backup: skipped because settings.json did not exist.")
    print(f"ANTHROPIC_BASE_URL={profile.base_url}")
    print(f"ANTHROPIC_AUTH_TOKEN={mask_api_key(profile.api_key)}")
    return 0


def command_current(args: argparse.Namespace, store: ProfileStore) -> int:
    current = read_current_env(args.settings_path)
    matched = find_matching_profile(store.list_profiles(), current)
    if matched:
        print_profile(matched)
        return 0
    if args.show_unmatched:
        print("No matching profile found.")
        print(f"ANTHROPIC_BASE_URL={current.get('ANTHROPIC_BASE_URL') or ''}")
        token = current.get("ANTHROPIC_AUTH_TOKEN") or ""
        print(f"ANTHROPIC_AUTH_TOKEN={mask_api_key(token) if token else ''}")
        return 0
    print("No matching profile found.")
    return 1


def command_remove(args: argparse.Namespace, store: ProfileStore) -> int:
    profile = (
        pick_profile(args, store, prompt="Remove profile")
        if args.alias is None
        else resolve_profile(store, args.alias)
    )
    if not args.yes and not prompt_yes_no(
        f"Remove profile '{profile.alias}' ({profile.name})?",
        default=False,
    ):
        print("Cancelled.")
        return 1
    if store.remove(profile.alias):
        print(f"Removed profile '{profile.alias}'.")
        return 0
    print(f"Profile '{args.alias}' not found.", file=sys.stderr)
    return 1


def command_doctor(args: argparse.Namespace, store: ProfileStore) -> int:
    profile_count = len(store.load())
    print(f"Profile store: {store.path}")
    print(f"Profiles: {profile_count}")
    print(f"Claude settings: {args.settings_path}")
    try:
        current = read_current_env(args.settings_path)
    except SettingsError as exc:
        print(f"Claude settings error: {exc}", file=sys.stderr)
        return 1
    print(f"ANTHROPIC_BASE_URL: {current.get('ANTHROPIC_BASE_URL') or ''}")
    token = current.get("ANTHROPIC_AUTH_TOKEN") or ""
    print(f"ANTHROPIC_AUTH_TOKEN: {mask_api_key(token) if token else ''}")
    return 0


def command_check(args: argparse.Namespace, store: ProfileStore) -> int:
    profiles = (
        [resolve_profile(store, args.alias)]
        if args.alias
        else sorted(store.list_profiles(), key=lambda profile: profile.alias)
    )
    if not profiles:
        print("No profiles found.")
        return 1
    failures = 0
    for profile in profiles:
        print(
            f"Checking {profile.alias} ({profile.type}, {mask_api_key(profile.api_key)}) ...",
            flush=True,
        )
        result = check_profile(profile, model=args.model, timeout=args.timeout)
        if result.ok:
            print("  OK")
        else:
            failures += 1
            if result.status is None:
                print("  FAILED")
            else:
                print(f"  FAILED (HTTP {result.status})")
            print(f"  Reason: {result.message}")
    return 1 if failures else 0


def print_profile_table(profiles: list[Profile], active_alias: Optional[str]) -> None:
    rows = []
    for index, profile in enumerate(profiles, start=1):
        rows.append(
            [
                "*" if profile.alias == active_alias else "",
                str(index),
                profile.alias,
                profile.type,
                profile.name,
                compact_url(profile.base_url),
                mask_api_key(profile.api_key),
                profile.default_model,
            ]
        )
    headers = ["ACTIVE", "ID", "ALIAS", "TYPE", "NAME", "BASE_URL", "KEY", "MODEL"]
    widths = [
        max(len(row[column]) for row in [headers] + rows)
        for column in range(len(headers))
    ]
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def print_profile(profile: Profile) -> None:
    print(f"alias: {profile.alias}")
    print(f"name: {profile.name}")
    print(f"type: {profile.type}")
    print(f"base_url: {profile.base_url}")
    print(f"api_key: {mask_api_key(profile.api_key)}")
    print(f"default_model: {profile.default_model}")
    print(f"created_at: {profile.created_at}")
    print(f"updated_at: {profile.updated_at}")


def require_profile(store: ProfileStore, alias: str) -> Profile:
    profile = store.get(alias)
    if not profile:
        raise KeyError(f"Profile '{alias}' not found.")
    return profile


def resolve_profile(store: ProfileStore, selector: str) -> Profile:
    profiles = sorted(store.list_profiles(), key=lambda profile: profile.alias)
    if selector.isdigit():
        index = int(selector)
        if 1 <= index <= len(profiles):
            return profiles[index - 1]
        raise KeyError(f"Profile row '{selector}' not found.")
    exact = store.get(selector)
    if exact:
        return exact
    matches = [
        profile
        for profile in profiles
        if selector.lower() in profile.alias.lower()
        or selector.lower() in profile.name.lower()
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        aliases = ", ".join(profile.alias for profile in matches)
        raise KeyError(f"Selector '{selector}' matched multiple profiles: {aliases}")
    return require_profile(store, selector)


def find_matching_profile(
    profiles: Iterable[Profile],
    current: dict,
) -> Optional[Profile]:
    base_url = current.get("ANTHROPIC_BASE_URL")
    api_key = current.get("ANTHROPIC_AUTH_TOKEN")
    for profile in profiles:
        if profile.base_url == base_url and profile.api_key == api_key:
            return profile
    return None


def active_alias_for_list(args: argparse.Namespace, store: ProfileStore) -> Optional[str]:
    try:
        current = read_current_env(args.settings_path)
        matched = find_matching_profile(store.list_profiles(), current)
        if matched:
            return matched.alias
    except SettingsError:
        pass
    return store.get_active_alias()


def default_base_url(profile_type: str) -> str:
    if profile_type == "api":
        return API_BASE_URL
    if profile_type == "token-plan":
        return TOKEN_PLAN_BASE_URL
    raise ValueError(f"type must be one of: api, token-plan")


def prompt_required(label: str) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value:
            return value


def prompt_default(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def prompt_profile_type() -> str:
    print("Credential type:")
    print("  1. Token Plan")
    print("  2. Pay-as-you-go API")
    value = input("Choose [1]: ").strip() or "1"
    if value in {"1", "token", "token-plan"}:
        return "token-plan"
    if value in {"2", "api"}:
        return "api"
    raise ValueError("type must be one of: api, token-plan")


def compact_url(url: str) -> str:
    return (
        url.replace("https://token-plan-cn.xiaomimimo.com", "token-plan-cn...")
        .replace("https://api.xiaomimimo.com", "api.xiaomimimo...")
    )


def pick_profile(
    args: argparse.Namespace,
    store: ProfileStore,
    prompt: str = "Select profile",
) -> Profile:
    profiles = sorted(store.list_profiles(), key=lambda profile: profile.alias)
    if not profiles:
        raise KeyError("No profiles found.")
    active_alias = active_alias_for_list(args, store)
    print_profile_table(profiles, active_alias)
    print()
    while True:
        selector = input(f"{prompt} [1-{len(profiles)}, q]: ").strip()
        if selector.lower() in {"q", "quit"}:
            raise KeyboardInterrupt
        try:
            return resolve_profile(store, selector)
        except KeyError as exc:
            print(str(exc), file=sys.stderr)


def prompt_yes_no(label: str, default: bool) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    value = input(label + suffix).strip().lower()
    if not value:
        return default
    return value in {"y", "yes"}


def run(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = ProfileStore(args.store_path)
    try:
        if args.command == "add":
            return command_add(args, store)
        if args.command == "add-api":
            return command_add_api(args, store)
        if args.command == "add-token":
            return command_add_token(args, store)
        if args.command == "list":
            return command_list(args, store)
        if args.command == "show":
            return command_show(args, store)
        if args.command in {"switch", "use"}:
            return command_switch(args, store)
        if args.command == "current":
            return command_current(args, store)
        if args.command == "remove":
            return command_remove(args, store)
        if args.command == "check":
            return command_check(args, store)
        if args.command == "doctor":
            return command_doctor(args, store)
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 1
    except (KeyError, ValueError, SettingsError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    parser.error(f"unknown command: {args.command}")
    return 2


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
