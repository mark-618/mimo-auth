"""Command line interface for mimo-auth."""

from __future__ import annotations

import argparse
import getpass
import os
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
from .models import Profile, mask_api_key, utc_now_iso, validate_profile_type
from .models import API_BASE_URL, DEFAULT_MODEL, TOKEN_PLAN_BASE_URL
from .store import DEFAULT_STORE_PATH, ProfileStore


COLORS = {
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bright_black": "\033[90m",
    "bright_red": "\033[91m",
    "bright_green": "\033[92m",
    "bright_yellow": "\033[93m",
    "bright_blue": "\033[94m",
    "bright_magenta": "\033[95m",
    "bright_cyan": "\033[96m",
}
RESET = "\033[0m"


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

    subparsers.add_parser("status", help="Show mimo-auth and Claude Code status.")

    remove_parser = subparsers.add_parser("remove", help="Remove a profile.")
    remove_parser.add_argument("alias", nargs="?")
    remove_parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Remove without confirmation.",
    )

    edit_parser = subparsers.add_parser("edit", help="Edit a profile.")
    edit_parser.add_argument("alias", nargs="?")
    edit_parser.add_argument("--name")
    edit_parser.add_argument("--type", choices=["api", "token-plan"])
    edit_parser.add_argument("--base-url")
    edit_parser.add_argument("--api-key")
    edit_parser.add_argument("--default-model")

    rename_parser = subparsers.add_parser("rename", help="Rename a profile alias.")
    rename_parser.add_argument("old_alias")
    rename_parser.add_argument("new_alias")

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
        print(style("Add MiMo profile", "bold"))
        print()
    alias = args.alias or prompt_required("Profile alias")
    profile_type = args.type or prompt_profile_type()
    base_url = args.base_url or default_base_url(profile_type)
    name = args.name or prompt_default("Display name", alias)
    api_key = args.api_key or prompt_secret("MiMo API key")
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
    api_key = args.api_key or prompt_secret("MiMo API key")
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
    api_key = args.api_key or prompt_secret("MiMo Token Plan key")
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
            print(
                style(
                    f"Profile '{original_alias}' already exists; using '{alias}' instead.",
                    "yellow",
                )
            )
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
    print(
        f"{style(action, status_color(action))} profile "
        f"{style(repr(profile.alias), 'bright_cyan')} "
        f"({style(profile.name, 'bright_magenta')})."
    )
    print_compact_profile_summary(profile)
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
        print(style("No profiles found.", "yellow"))
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
    print(
        f"{style('Claude Code now uses', 'bright_green')} "
        f"{style(repr(profile.alias), 'bright_cyan')} "
        f"({style(profile.name, 'bright_magenta')})."
    )
    if backup_path:
        print_key_value("Backup", str(backup_path), "bright_black")
    else:
        print(style("Backup: skipped because settings.json did not exist.", "dim"))
    print_key_value("ANTHROPIC_BASE_URL", profile.base_url, "green", separator="=")
    print_key_value(
        "ANTHROPIC_AUTH_TOKEN",
        mask_api_key(profile.api_key),
        "bright_yellow",
        separator="=",
    )
    return 0


def command_current(args: argparse.Namespace, store: ProfileStore) -> int:
    current = read_current_env(args.settings_path)
    matched = find_matching_profile(store.list_profiles(), current)
    if matched:
        print_profile(matched)
        return 0
    if args.show_unmatched:
        print(style("No matching profile found.", "yellow"))
        print_key_value(
            "ANTHROPIC_BASE_URL",
            current.get("ANTHROPIC_BASE_URL") or "",
            "green",
            separator="=",
        )
        token = current.get("ANTHROPIC_AUTH_TOKEN") or ""
        print_key_value(
            "ANTHROPIC_AUTH_TOKEN",
            mask_api_key(token) if token else "",
            "bright_yellow",
            separator="=",
        )
        return 0
    print(style("No matching profile found.", "yellow"))
    return 1


def command_status(args: argparse.Namespace, store: ProfileStore) -> int:
    profiles = list(store.list_profiles())
    active_alias = store.get_active_alias()
    active_profile = store.get(active_alias) if active_alias else None
    try:
        current = read_current_env(args.settings_path)
        matched = find_matching_profile(profiles, current)
        settings_error = None
    except SettingsError as exc:
        current = {}
        matched = None
        settings_error = str(exc)

    print(style("mimo-auth status", "bold"))
    print_key_value("Profile store", str(store.path), "bright_blue")
    print_key_value("Profiles", str(len(profiles)), "bright_magenta")
    print_key_value("Claude settings", str(args.settings_path), "bright_blue")
    if settings_error:
        print_key_value("Settings", settings_error, "bright_red")
        return 1

    if active_profile:
        print_key_value("Active alias", active_profile.alias, "bright_cyan")
        print_key_value("Active type", active_profile.type, profile_type_color(active_profile.type))
        print_key_value("Active model", active_profile.default_model, "bright_blue")
    elif active_alias:
        print_key_value("Active alias", f"{active_alias} (missing)", "bright_red")
    else:
        print_key_value("Active alias", "not set", "bright_yellow")

    if matched:
        print_key_value("Claude profile", matched.alias, "bright_cyan")
        state = "synced" if active_profile and matched.alias == active_profile.alias else "settings differ"
        print_key_value("State", state, "bright_green" if state == "synced" else "bright_yellow")
    else:
        print_key_value("Claude profile", "no matching profile", "bright_yellow")
        print_key_value("State", "settings differ", "bright_yellow")

    print_key_value("ANTHROPIC_BASE_URL", current.get("ANTHROPIC_BASE_URL") or "", "green")
    token = current.get("ANTHROPIC_AUTH_TOKEN") or ""
    print_key_value("ANTHROPIC_AUTH_TOKEN", mask_api_key(token) if token else "", "bright_yellow")
    return 0


def command_remove(args: argparse.Namespace, store: ProfileStore) -> int:
    profiles = (
        [resolve_profile(store, args.alias)]
        if args.alias is not None
        else pick_profiles_for_remove(args, store)
    )
    if not profiles:
        print("Cancelled.")
        return 1
    label = ", ".join(profile.alias for profile in profiles)
    if not args.yes and not prompt_yes_no(
        f"Remove {len(profiles)} profile(s): {label}?",
        default=False,
    ):
        print("Cancelled.")
        return 1
    removed = []
    for profile in profiles:
        if store.remove(profile.alias):
            removed.append(profile.alias)
    for alias in removed:
        print(f"{style('Removed', 'bright_red')} profile {style(repr(alias), 'bright_cyan')}.")
    return 0 if removed else 1


def command_edit(args: argparse.Namespace, store: ProfileStore) -> int:
    profile = pick_profile(args, store, prompt="Edit profile") if args.alias is None else resolve_profile(store, args.alias)
    interactive = not any(
        value is not None
        for value in [args.name, args.type, args.base_url, args.api_key, args.default_model]
    )
    if interactive:
        print_profile(profile)
        name = prompt_default("Display name", profile.name)
        profile_type = prompt_profile_type(default=profile.type)
        base_default = profile.base_url if profile_type == profile.type else default_base_url(profile_type)
        base_url = prompt_default("Base URL", base_default)
        default_model = prompt_default("Default model", profile.default_model)
        api_key = prompt_secret_optional("MiMo API key", profile.api_key)
    else:
        name = args.name if args.name is not None else profile.name
        profile_type = args.type if args.type is not None else profile.type
        base_url = args.base_url if args.base_url is not None else profile.base_url
        api_key = args.api_key if args.api_key is not None else profile.api_key
        default_model = args.default_model if args.default_model is not None else profile.default_model
    validate_profile_type(profile_type)
    updated = profile.with_updates(
        name=name,
        profile_type=profile_type,
        base_url=base_url,
        api_key=api_key,
        default_model=default_model,
    )
    store.upsert(updated)
    print(f"{style('Updated', 'bright_green')} profile {style(repr(updated.alias), 'bright_cyan')}.")
    print_compact_profile_summary(updated)
    return 0


def command_rename(args: argparse.Namespace, store: ProfileStore) -> int:
    old_profile = require_profile(store, args.old_alias)
    if store.get(args.new_alias):
        raise ValueError(f"Profile '{args.new_alias}' already exists.")
    profiles = store.load()
    renamed = Profile(
        alias=args.new_alias,
        name=old_profile.name,
        type=old_profile.type,
        base_url=old_profile.base_url,
        api_key=old_profile.api_key,
        default_model=old_profile.default_model,
        created_at=old_profile.created_at,
        updated_at=utc_now_iso(),
    )
    del profiles[old_profile.alias]
    profiles[renamed.alias] = renamed
    active_alias = store.get_active_alias()
    store.save(profiles, renamed.alias if active_alias == old_profile.alias else active_alias)
    print(
        f"{style('Renamed', 'bright_green')} "
        f"{style(repr(old_profile.alias), 'bright_black')} -> "
        f"{style(repr(renamed.alias), 'bright_cyan')}."
    )
    return 0


def command_doctor(args: argparse.Namespace, store: ProfileStore) -> int:
    profile_count = len(store.load())
    print(style("mimo-auth doctor", "bold"))
    print_key_value("Profile store", str(store.path), "bright_blue")
    print_key_value("Profiles", str(profile_count), "bright_magenta")
    print_key_value("Claude settings", str(args.settings_path), "bright_blue")
    try:
        current = read_current_env(args.settings_path)
    except SettingsError as exc:
        print(f"Claude settings error: {exc}", file=sys.stderr)
        return 1
    print_key_value("ANTHROPIC_BASE_URL", current.get("ANTHROPIC_BASE_URL") or "", "green")
    token = current.get("ANTHROPIC_AUTH_TOKEN") or ""
    print_key_value(
        "ANTHROPIC_AUTH_TOKEN",
        mask_api_key(token) if token else "",
        "bright_yellow",
    )
    return 0


def command_check(args: argparse.Namespace, store: ProfileStore) -> int:
    profiles = (
        [resolve_profile(store, args.alias)]
        if args.alias
        else sorted(store.list_profiles(), key=lambda profile: profile.alias)
    )
    if not profiles:
        print(style("No profiles found.", "yellow"))
        return 1
    failures = 0
    for profile in profiles:
        print(
            f"{style('Checking', 'cyan')} {style(profile.alias, 'bold')} "
            f"({style(profile.type, profile_type_color(profile.type))}, "
            f"{style(mask_api_key(profile.api_key), 'yellow')}) ...",
            flush=True,
        )
        result = check_profile(profile, model=args.model, timeout=args.timeout)
        if result.ok:
            print(f"  {style('OK', 'green')}")
        else:
            failures += 1
            if result.status is None:
                print(f"  {style('FAILED', 'red')}")
            else:
                print(f"  {style('FAILED', 'red')} (HTTP {result.status})")
            print(f"  {style('Reason:', 'yellow')} {result.message}")
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
    print(
        "  ".join(
            style(header.ljust(widths[index]), "bold") for index, header in enumerate(headers)
        )
    )
    for row in rows:
        print(
            "  ".join(
                style_table_cell(index, value.ljust(widths[index]))
                for index, value in enumerate(row)
            )
        )


def print_profile(profile: Profile) -> None:
    print(style("Profile", "bold"))
    print_field("alias", profile.alias, "bright_cyan")
    print_field("name", profile.name, "bright_magenta")
    print_field("type", profile.type, profile_type_color(profile.type))
    print_field("base_url", profile.base_url, "green")
    print_field("api_key", mask_api_key(profile.api_key), "bright_yellow")
    print_field("default_model", profile.default_model, "bright_blue")
    print_field("created_at", profile.created_at, "dim")
    print_field("updated_at", profile.updated_at, "dim")


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


def color_enabled() -> bool:
    color_mode = os.environ.get("MIMO_AUTH_COLOR", "").lower()
    if color_mode in {"always", "1", "true", "yes"}:
        return True
    if color_mode in {"never", "0", "false", "no"}:
        return False
    return "NO_COLOR" not in os.environ and sys.stdout.isatty()


def style(text: str, color: str) -> str:
    if not color_enabled():
        return text
    code = COLORS.get(color)
    if not code:
        return text
    return f"{code}{text}{RESET}"


def profile_type_color(profile_type: str) -> str:
    return "bright_magenta" if profile_type == "token-plan" else "bright_blue"


def status_color(status: str) -> str:
    if status in {"Added", "Updated"}:
        return "bright_green"
    if status == "Removed":
        return "bright_red"
    return "white"


def style_table_cell(column: int, value: str) -> str:
    if column == 0 and value.strip():
        return style(value, "green")
    if column == 2:
        return style(value, "cyan")
    if column == 3:
        return style(value, profile_type_color(value.strip()))
    if column == 6:
        return style(value, "yellow")
    return value


def print_field(label: str, value: str, value_color: Optional[str] = None) -> None:
    rendered_value = style(value, value_color) if value_color else value
    print(f"{style(label + ':', 'bright_cyan')} {rendered_value}")


def print_key_value(
    label: str,
    value: str,
    value_color: Optional[str] = None,
    *,
    separator: str = ": ",
) -> None:
    rendered_value = style(value, value_color) if value_color else value
    print(f"{style(label, 'bright_cyan')}{separator}{rendered_value}")


def print_compact_profile_summary(profile: Profile) -> None:
    print(
        "  "
        + "  ".join(
            [
                f"{style('type', 'bright_black')}={style(profile.type, profile_type_color(profile.type))}",
                f"{style('model', 'bright_black')}={style(profile.default_model, 'bright_blue')}",
                f"{style('key', 'bright_black')}={style(mask_api_key(profile.api_key), 'bright_yellow')}",
            ]
        )
    )


def default_base_url(profile_type: str) -> str:
    if profile_type == "api":
        return API_BASE_URL
    if profile_type == "token-plan":
        return TOKEN_PLAN_BASE_URL
    raise ValueError(f"type must be one of: api, token-plan")


def prompt_required(label: str) -> str:
    while True:
        value = input(f"{style(label, 'bright_cyan')} {style('[q]', 'bright_black')}: ").strip()
        if is_quit(value):
            raise KeyboardInterrupt
        if value:
            return value


def prompt_default(label: str, default: str) -> str:
    value = input(
        f"{style(label, 'bright_cyan')} "
        f"{style('[' + default + ', q]', 'bright_black')}: "
    ).strip()
    if is_quit(value):
        raise KeyboardInterrupt
    return value or default


def prompt_profile_type(default: str = "token-plan") -> str:
    print(style("Credential type:", "bold"))
    print(f"  {style('1', 'bright_magenta')}. {style('Token Plan', 'bright_magenta')}")
    print(f"  {style('2', 'bright_blue')}. {style('Pay-as-you-go API', 'bright_blue')}")
    default_choice = "2" if default == "api" else "1"
    value = input(
        f"{style('Choose', 'bright_cyan')} "
        f"{style('[' + default_choice + ', q]', 'bright_black')}: "
    ).strip()
    if is_quit(value):
        raise KeyboardInterrupt
    value = value or default_choice
    if value in {"1", "token", "token-plan"}:
        return "token-plan"
    if value in {"2", "api"}:
        return "api"
    raise ValueError("type must be one of: api, token-plan")


def prompt_secret(label: str) -> str:
    value = getpass.getpass(f"{label} [q]: ").strip()
    if is_quit(value):
        raise KeyboardInterrupt
    return value


def prompt_secret_optional(label: str, current: str) -> str:
    value = getpass.getpass(f"{label} [keep/q]: ").strip()
    if is_quit(value):
        raise KeyboardInterrupt
    return value or current


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
        selector = input(
            f"{style(prompt, 'bright_cyan')} "
            f"{style('[' + '1-' + str(len(profiles)) + ', q]', 'bright_black')}: "
        ).strip()
        if selector.lower() in {"q", "quit"}:
            raise KeyboardInterrupt
        try:
            return resolve_profile(store, selector)
        except KeyError as exc:
            print(str(exc), file=sys.stderr)


def pick_profiles_for_remove(args: argparse.Namespace, store: ProfileStore) -> list[Profile]:
    profiles = sorted(store.list_profiles(), key=lambda profile: profile.alias)
    if not profiles:
        raise KeyError("No profiles found.")
    active_alias = active_alias_for_list(args, store)
    print_profile_table(profiles, active_alias)
    print()
    while True:
        selector = input(
            f"{style('Remove profiles', 'bright_cyan')} "
            f"{style('[1 3, all, q]', 'bright_black')}: "
        ).strip()
        if is_quit(selector):
            raise KeyboardInterrupt
        if selector.lower() == "all":
            return profiles
        try:
            indexes = [int(item) for item in selector.replace(",", " ").split()]
        except ValueError:
            print("Use row numbers separated by spaces, 'all', or 'q'.", file=sys.stderr)
            continue
        selected = []
        invalid = []
        seen = set()
        for index in indexes:
            if 1 <= index <= len(profiles):
                if index not in seen:
                    selected.append(profiles[index - 1])
                    seen.add(index)
            else:
                invalid.append(str(index))
        if invalid:
            print(f"Profile row(s) not found: {', '.join(invalid)}", file=sys.stderr)
            continue
        if selected:
            return selected


def prompt_yes_no(label: str, default: bool) -> bool:
    suffix = " [Y/n/q]: " if default else " [y/N/q]: "
    value = input(style(label, "bright_cyan") + style(suffix, "bright_black")).strip().lower()
    if is_quit(value):
        raise KeyboardInterrupt
    if not value:
        return default
    return value in {"y", "yes"}


def is_quit(value: str) -> bool:
    return value.lower() in {"q", "quit"}


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
        if args.command == "status":
            return command_status(args, store)
        if args.command == "remove":
            return command_remove(args, store)
        if args.command == "edit":
            return command_edit(args, store)
        if args.command == "rename":
            return command_rename(args, store)
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
