import json

from mimo_auth.claude import apply_profile, read_current_env
from mimo_auth.check import CheckResult
from mimo_auth.cli import run
from mimo_auth.models import API_BASE_URL, TOKEN_PLAN_BASE_URL, Profile, mask_api_key
from mimo_auth.store import ProfileStore


def make_profile(alias="mimo"):
    return Profile.create(
        alias=alias,
        name="MiMo Test",
        profile_type="api",
        base_url="https://api.mimo.example/v1",
        api_key="sk-test-secret-abcd",
        default_model="mimo-v1",
    )


def test_mask_api_key_keeps_only_safe_shape():
    assert mask_api_key("sk-test-secret-abcd") == "sk-****abcd"
    assert mask_api_key("abcd") == "****"


def test_store_round_trip(tmp_path):
    store = ProfileStore(tmp_path / "profiles.json")
    profile = make_profile()

    store.upsert(profile)

    loaded = store.get("mimo")
    assert loaded == profile
    assert (tmp_path / "profiles.json").stat().st_mode & 0o777 == 0o600


def test_apply_profile_preserves_other_settings_and_backs_up(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "permissions": {"allow": ["Bash(ls)"]},
                "env": {"EXISTING": "keep", "ANTHROPIC_AUTH_TOKEN": "old"},
            }
        ),
        encoding="utf-8",
    )
    profile = make_profile()

    backup_path = apply_profile(settings_path, profile)

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["permissions"] == {"allow": ["Bash(ls)"]}
    assert settings["env"]["EXISTING"] == "keep"
    assert settings["env"]["ANTHROPIC_BASE_URL"] == profile.base_url
    assert settings["env"]["ANTHROPIC_AUTH_TOKEN"] == profile.api_key
    assert backup_path is not None
    assert backup_path.exists()


def test_read_current_env_returns_only_managed_fields(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "env": {
                    "ANTHROPIC_BASE_URL": "https://api.mimo.example/v1",
                    "ANTHROPIC_AUTH_TOKEN": "sk-test-secret-abcd",
                    "OTHER": "keep",
                }
            }
        ),
        encoding="utf-8",
    )

    current = read_current_env(settings_path)

    assert current == {
        "ANTHROPIC_BASE_URL": "https://api.mimo.example/v1",
        "ANTHROPIC_AUTH_TOKEN": "sk-test-secret-abcd",
    }


def test_cli_masks_api_key_in_outputs(tmp_path, capsys):
    store_path = tmp_path / "profiles.json"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"env": {"EXISTING": "keep"}, "theme": "dark"}),
        encoding="utf-8",
    )
    common_args = [
        "--store-path",
        str(store_path),
        "--settings-path",
        str(settings_path),
    ]

    assert run(
        common_args
        + [
            "add",
            "main",
            "--name",
            "MiMo Main",
            "--type",
            "api",
            "--base-url",
            "https://api.mimo.example/v1",
            "--api-key",
            "sk-test-secret-abcd",
            "--default-model",
            "mimo-v1",
        ]
    ) == 0
    assert run(
        common_args
        + [
            "add",
            "main",
            "--name",
            "MiMo Main Updated",
            "--type",
            "api",
            "--base-url",
            "https://api.mimo.example/v1",
            "--api-key",
            "sk-test-secret-updated",
            "--default-model",
            "mimo-v1",
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "Profile 'main' already exists; using 'main-bal' instead." in output
    assert ProfileStore(store_path).get("main-bal") is not None
    assert run(
        common_args
        + [
            "add-api",
            "main",
            "--api-key",
            "sk-test-secret-third",
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "Profile 'main' already exists; using 'main-bal-2' instead." in output
    assert ProfileStore(store_path).get("main-bal-2") is not None
    assert run(
        common_args
        + [
            "add-token",
            "main",
            "--api-key",
            "tp-test-secret-plan",
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "Profile 'main' already exists; using 'main-plan' instead." in output
    assert ProfileStore(store_path).get("main-plan") is not None
    assert run(
        common_args
        + [
            "add",
            "main",
            "--name",
            "MiMo Main",
            "--type",
            "api",
            "--base-url",
            "https://api.mimo.example/v1",
            "--api-key",
            "sk-test-secret-abcd",
            "--default-model",
            "mimo-v1",
            "--force",
        ]
    ) == 0

    command_args = [
        ["list"],
        ["show", "main"],
        ["switch", "main"],
        ["current"],
        ["status"],
        ["doctor"],
    ]
    for command in command_args:
        args = common_args + command
        if command == ["current"]:
            run(common_args + ["switch", "main"])
            capsys.readouterr()
        assert run(args) == 0
        output = capsys.readouterr().out
        assert "sk-test-secret-abcd" not in output
        assert "sk-****abcd" in output

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["theme"] == "dark"
    assert settings["env"]["EXISTING"] == "keep"


def test_short_add_commands_and_numeric_use(tmp_path, capsys):
    store_path = tmp_path / "profiles.json"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"env": {}}), encoding="utf-8")
    common_args = [
        "--store-path",
        str(store_path),
        "--settings-path",
        str(settings_path),
    ]

    assert run(
        common_args
        + ["add-api", "main", "--api-key", "sk-demo-secret-abcd"]
    ) == 0
    assert run(
        common_args
        + ["add-token", "work", "--api-key", "tp-demo-secret-wxyz"]
    ) == 0

    assert run(common_args + ["list"]) == 0
    list_output = capsys.readouterr().out
    assert "ACTIVE" in list_output
    assert "ID" in list_output
    assert "main" in list_output
    assert "work" in list_output
    assert "sk-demo-secret-abcd" not in list_output
    assert "tp-demo-secret-wxyz" not in list_output

    assert run(common_args + ["use", "2"]) == 0
    switch_output = capsys.readouterr().out
    assert "Claude Code now uses 'work'" in switch_output
    assert "tp-****wxyz" in switch_output
    assert "tp-demo-secret-wxyz" not in switch_output

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["env"]["ANTHROPIC_BASE_URL"] == TOKEN_PLAN_BASE_URL
    assert settings["env"]["ANTHROPIC_AUTH_TOKEN"] == "tp-demo-secret-wxyz"

    assert run(common_args + ["use", "main"]) == 0
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["env"]["ANTHROPIC_BASE_URL"] == API_BASE_URL


def test_status_edit_and_rename(tmp_path, capsys):
    store_path = tmp_path / "profiles.json"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"env": {}}), encoding="utf-8")
    common_args = [
        "--store-path",
        str(store_path),
        "--settings-path",
        str(settings_path),
    ]
    run(common_args + ["add-api", "lab", "--api-key", "sk-demo-lab-abcd"])
    run(common_args + ["use", "lab"])
    capsys.readouterr()

    assert run(common_args + ["status"]) == 0
    output = capsys.readouterr().out
    assert "mimo-auth status" in output
    assert "State: synced" in output
    assert "sk-****abcd" in output
    assert "sk-demo-lab-abcd" not in output

    assert run(common_args + ["rename", "lab", "work"]) == 0
    output = capsys.readouterr().out
    assert "Renamed 'lab' -> 'work'." in output
    store = ProfileStore(store_path)
    assert store.get("lab") is None
    assert store.get("work") is not None
    assert store.get_active_alias() == "work"

    assert run(
        common_args
        + [
            "edit",
            "work",
            "--name",
            "MiMo Work",
            "--type",
            "token-plan",
            "--base-url",
            "https://custom.example.com/anthropic",
            "--default-model",
            "mimo-custom",
            "--api-key",
            "tp-demo-work-9999",
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "Updated profile 'work'." in output
    profile = ProfileStore(store_path).get("work")
    assert profile is not None
    assert profile.name == "MiMo Work"
    assert profile.type == "token-plan"
    assert profile.base_url == "https://custom.example.com/anthropic"
    assert profile.default_model == "mimo-custom"
    assert profile.api_key == "tp-demo-work-9999"
    assert "tp-demo-work-9999" not in output


def test_switch_picker_and_fragment_selector(tmp_path, capsys, monkeypatch):
    store_path = tmp_path / "profiles.json"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"env": {}}), encoding="utf-8")
    common_args = [
        "--store-path",
        str(store_path),
        "--settings-path",
        str(settings_path),
    ]
    run(common_args + ["add-token", "work", "--api-key", "tp-demo-work-1234"])
    run(common_args + ["add-token", "personal", "--api-key", "tp-demo-personal-5678"])
    run(common_args + ["add-api", "lab", "--api-key", "sk-demo-lab-abcd"])
    capsys.readouterr()

    monkeypatch.setattr("builtins.input", lambda _prompt: "3")
    assert run(common_args + ["switch"]) == 0
    output = capsys.readouterr().out
    assert "ACTIVE" in output
    assert "Claude Code now uses 'work'" in output
    assert "tp-demo-work-1234" not in output

    assert run(common_args + ["switch", "pers"]) == 0
    output = capsys.readouterr().out
    assert "Claude Code now uses 'personal'" in output
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["env"]["ANTHROPIC_AUTH_TOKEN"] == "tp-demo-personal-5678"


def test_remove_direct_and_picker(tmp_path, capsys, monkeypatch):
    store_path = tmp_path / "profiles.json"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"env": {}}), encoding="utf-8")
    common_args = [
        "--store-path",
        str(store_path),
        "--settings-path",
        str(settings_path),
    ]
    run(common_args + ["add-api", "lab", "--api-key", "sk-demo-lab-abcd"])
    run(common_args + ["add-token", "personal", "--api-key", "tp-demo-personal-5678"])
    run(common_args + ["add-token", "work", "--api-key", "tp-demo-work-1234"])
    run(common_args + ["use", "work"])
    capsys.readouterr()

    assert run(common_args + ["remove", "2", "--yes"]) == 0
    output = capsys.readouterr().out
    assert "Removed profile 'personal'." in output
    assert "tp-demo-personal-5678" not in output

    answers = iter(["2", "y"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    assert run(common_args + ["remove"]) == 0
    output = capsys.readouterr().out
    assert "ACTIVE" in output
    assert "Removed profile 'work'." in output

    store = ProfileStore(store_path)
    assert store.get("work") is None
    assert store.get_active_alias() is None


def test_remove_picker_accepts_space_separated_multi_select(tmp_path, capsys, monkeypatch):
    store_path = tmp_path / "profiles.json"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"env": {}}), encoding="utf-8")
    common_args = [
        "--store-path",
        str(store_path),
        "--settings-path",
        str(settings_path),
    ]
    run(common_args + ["add-api", "lab", "--api-key", "sk-demo-lab-abcd"])
    run(common_args + ["add-token", "personal", "--api-key", "tp-demo-personal-5678"])
    run(common_args + ["add-token", "work", "--api-key", "tp-demo-work-1234"])
    capsys.readouterr()

    answers = iter(["1 3", "y"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    assert run(common_args + ["remove"]) == 0
    output = capsys.readouterr().out
    assert "Removed profile 'lab'." in output
    assert "Removed profile 'work'." in output
    store = ProfileStore(store_path)
    assert store.get("lab") is None
    assert store.get("work") is None
    assert store.get("personal") is not None


def test_remove_cancel_keeps_profile(tmp_path, capsys, monkeypatch):
    store_path = tmp_path / "profiles.json"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"env": {}}), encoding="utf-8")
    common_args = [
        "--store-path",
        str(store_path),
        "--settings-path",
        str(settings_path),
    ]
    run(common_args + ["add-api", "lab", "--api-key", "sk-demo-lab-abcd"])
    capsys.readouterr()

    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    assert run(common_args + ["remove", "lab"]) == 1
    assert "Cancelled." in capsys.readouterr().out
    assert ProfileStore(store_path).get("lab") is not None


def test_remove_confirmation_can_quit(tmp_path, capsys, monkeypatch):
    store_path = tmp_path / "profiles.json"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"env": {}}), encoding="utf-8")
    common_args = [
        "--store-path",
        str(store_path),
        "--settings-path",
        str(settings_path),
    ]
    run(common_args + ["add-api", "lab", "--api-key", "sk-demo-lab-abcd"])
    capsys.readouterr()

    monkeypatch.setattr("builtins.input", lambda _prompt: "q")
    assert run(common_args + ["remove", "lab"]) == 1
    assert "Cancelled." in capsys.readouterr().err
    assert ProfileStore(store_path).get("lab") is not None


def test_interactive_add_can_quit_mid_flow(tmp_path, capsys, monkeypatch):
    store_path = tmp_path / "profiles.json"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"env": {}}), encoding="utf-8")
    common_args = [
        "--store-path",
        str(store_path),
        "--settings-path",
        str(settings_path),
    ]
    answers = iter(["lab", "q"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    assert run(common_args + ["add"]) == 1
    output = capsys.readouterr()
    assert "Add MiMo profile" in output.out
    assert "Cancelled." in output.err
    assert list(ProfileStore(store_path).list_profiles()) == []


def test_check_all_profiles_masks_keys_and_reports_failures(
    tmp_path,
    capsys,
    monkeypatch,
):
    store_path = tmp_path / "profiles.json"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"env": {}}), encoding="utf-8")
    common_args = [
        "--store-path",
        str(store_path),
        "--settings-path",
        str(settings_path),
    ]
    run(common_args + ["add-api", "lab", "--api-key", "sk-demo-lab-abcd"])
    run(common_args + ["add-token", "work", "--api-key", "tp-demo-work-1234"])
    capsys.readouterr()

    def fake_check(profile, *, model, timeout):
        assert model == "mimo-v2.5-pro"
        assert timeout == 15.0
        if profile.alias == "lab":
            return CheckResult(True, 200, "OK")
        return CheckResult(
            False,
            401,
            "Authentication failed. Check whether the API key/token is correct and still active.",
        )

    monkeypatch.setattr("mimo_auth.cli.check_profile", fake_check)

    assert run(common_args + ["check"]) == 1
    output = capsys.readouterr().out
    assert "Checking lab" in output
    assert "Checking work" in output
    assert "OK" in output
    assert "FAILED (HTTP 401)" in output
    assert "Reason: Authentication failed" in output
    assert "sk-demo-lab-abcd" not in output
    assert "tp-demo-work-1234" not in output


def test_check_explains_payment_or_quota_failures(tmp_path, capsys, monkeypatch):
    store_path = tmp_path / "profiles.json"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"env": {}}), encoding="utf-8")
    common_args = [
        "--store-path",
        str(store_path),
        "--settings-path",
        str(settings_path),
    ]
    run(common_args + ["add-api", "lab", "--api-key", "sk-demo-lab-abcd"])
    capsys.readouterr()
    monkeypatch.setattr(
        "mimo_auth.cli.check_profile",
        lambda profile, *, model, timeout: CheckResult(
            False,
            402,
            "Payment or quota required. Check account balance, billing status, or Token Plan quota.",
        ),
    )

    assert run(common_args + ["check", "lab"]) == 1
    output = capsys.readouterr().out
    assert "FAILED (HTTP 402)" in output
    assert "Reason: Payment or quota required" in output
    assert "sk-demo-lab-abcd" not in output


def test_check_single_profile_success(tmp_path, capsys, monkeypatch):
    store_path = tmp_path / "profiles.json"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"env": {}}), encoding="utf-8")
    common_args = [
        "--store-path",
        str(store_path),
        "--settings-path",
        str(settings_path),
    ]
    run(common_args + ["add-api", "lab", "--api-key", "sk-demo-lab-abcd"])
    capsys.readouterr()
    monkeypatch.setattr(
        "mimo_auth.cli.check_profile",
        lambda profile, *, model, timeout: CheckResult(True, 200, "OK"),
    )

    assert run(common_args + ["check", "lab", "--timeout", "3"]) == 0
    output = capsys.readouterr().out
    assert "Checking lab" in output
    assert "OK" in output
    assert "sk-demo-lab-abcd" not in output


def test_color_output_can_be_forced_or_disabled(tmp_path, capsys, monkeypatch):
    store_path = tmp_path / "profiles.json"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"env": {}}), encoding="utf-8")
    common_args = [
        "--store-path",
        str(store_path),
        "--settings-path",
        str(settings_path),
    ]
    run(common_args + ["add-api", "lab", "--api-key", "sk-demo-lab-abcd"])
    capsys.readouterr()

    monkeypatch.setenv("MIMO_AUTH_COLOR", "always")
    assert run(common_args + ["list"]) == 0
    assert "\033[" in capsys.readouterr().out

    monkeypatch.setenv("MIMO_AUTH_COLOR", "never")
    assert run(common_args + ["list"]) == 0
    assert "\033[" not in capsys.readouterr().out
