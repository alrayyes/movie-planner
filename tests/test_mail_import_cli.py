import json
import sys
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jsonschema
import pytest
from typer.testing import CliRunner

from movie_planner.mail_import.cli import app
from movie_planner.mail_import.mbox_client import MboxMailClient

runner = CliRunner()


def _spy_fetch(
    captured: dict[str, object],
) -> object:
    original_fetch = MboxMailClient.fetch

    def spy_fetch(self: MboxMailClient, domains: list[str], **kwargs: object) -> list[str]:
        captured.update(kwargs)
        return list(original_fetch(self, domains, **kwargs))  # type: ignore[arg-type]

    return spy_fetch


def test_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0


def test_init_non_interactive_with_all_flags_writes_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        [
            "init",
            "--config",
            str(config_path),
            "--source",
            "imap",
            "--imap-host",
            "127.0.0.1",
            "--imap-port",
            "1143",
            "--imap-username",
            "me@example.com",
            "--imap-password-command",
            "printf hunter2",
        ],
    )

    assert result.exit_code == 0, result.output
    data = tomllib.loads(config_path.read_text())
    assert data["mail"]["source"] == "imap"
    assert data["mail"]["imap"]["host"] == "127.0.0.1"
    assert data["mail"]["imap"]["port"] == 1143
    assert data["mail"]["imap"]["password_command"] == "printf hunter2"
    assert "password" not in data["mail"]["imap"]
    assert data["chains"][0]["sender_domain"] == "pathe.nl"
    assert data["chains"][0]["translate"] == "pathe-translate"


def test_init_non_interactive_mbox_source(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    mbox_path = tmp_path / "INBOX"

    result = runner.invoke(
        app,
        ["init", "--config", str(config_path), "--source", "mbox", "--mbox-path", str(mbox_path)],
    )

    assert result.exit_code == 0, result.output
    data = tomllib.loads(config_path.read_text())
    assert data["mail"]["source"] == "mbox"
    assert data["mail"]["mbox"]["path"] == str(mbox_path)


def test_init_non_interactive_missing_required_value_fails_clearly(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    result = runner.invoke(app, ["init", "--config", str(config_path), "--source", "imap"])

    assert result.exit_code != 0
    assert "--imap-host" in result.output
    assert not config_path.exists()


def test_init_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("existing content")

    result = runner.invoke(
        app,
        [
            "init",
            "--config",
            str(config_path),
            "--source",
            "mbox",
            "--mbox-path",
            str(tmp_path / "INBOX"),
        ],
    )

    assert result.exit_code != 0
    assert config_path.read_text() == "existing content"


def test_init_force_overwrites(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("existing content")

    result = runner.invoke(
        app,
        [
            "init",
            "--config",
            str(config_path),
            "--force",
            "--source",
            "mbox",
            "--mbox-path",
            str(tmp_path / "INBOX"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "existing content" not in config_path.read_text()


def test_init_interactive_prompts_for_missing_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("movie_planner.mail_import.cli._is_interactive", lambda: True)
    monkeypatch.setattr("movie_planner.mail_import.cli.getpass.getpass", lambda prompt: "hunter2")

    result = runner.invoke(
        app,
        ["init", "--config", str(config_path)],
        # source, host, port(default), username, use-password-command?(no), sender_domain(default), translate(default)
        input="imap\n127.0.0.1\n\nme@example.com\nn\n\n\n",
    )

    assert result.exit_code == 0, result.output
    data = tomllib.loads(config_path.read_text())
    assert data["mail"]["source"] == "imap"
    assert data["mail"]["imap"]["host"] == "127.0.0.1"
    assert data["mail"]["imap"]["port"] == 993
    assert data["mail"]["imap"]["password"] == "hunter2"
    assert data["chains"][0]["sender_domain"] == "pathe.nl"


def test_init_interactive_password_command_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("movie_planner.mail_import.cli._is_interactive", lambda: True)

    result = runner.invoke(
        app,
        ["init", "--config", str(config_path)],
        input="imap\n127.0.0.1\n\nme@example.com\ny\npass show imap\n\n\n",
    )

    assert result.exit_code == 0, result.output
    data = tomllib.loads(config_path.read_text())
    assert data["mail"]["imap"]["password_command"] == "pass show imap"
    assert "password" not in data["mail"]["imap"]


# --- fetch: task groups 3-4 ---

FIXTURE_MBOX = Path(__file__).parent / "fixtures" / "sample.mbox"

_SELECTIVE_SCRIPT = """\
import json
import sys

envelope = json.load(sys.stdin)
if "confirmation" not in envelope["subject"].lower():
    print(f"not a booking: {envelope['subject']}", file=sys.stderr)
    sys.exit(1)
print(json.dumps({{"title": envelope["subject"], "date": "2026-07-04", "medium": "cinema"}}))
"""


def _mbox_config(
    tmp_path: Path, translate: str, *, sender_domain: str = "example-chain.com"
) -> Path:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""\
[mail]
source = "mbox"

[mail.mbox]
path = "{FIXTURE_MBOX}"

[[chains]]
sender_domain = "{sender_domain}"
translate = "{translate}"
"""
    )
    return config_path


def _selective_translate_script(tmp_path: Path) -> str:
    script_path = tmp_path / "fake-translate.py"
    script_path.write_text(_SELECTIVE_SCRIPT.replace("{{", "{").replace("}}", "}"))
    return f"{sys.executable} {script_path}"


def test_fetch_writes_recognized_rows_and_reports_unrecognized(tmp_path: Path) -> None:
    # Both fixture senders configured, so both get fetched; the
    # translate script itself only recognizes ones with "confirmation"
    # in the subject - the newsletter, same as a real chain sending
    # both booking confirmations and marketing mail, ends up in the
    # review table rather than being excluded from the fetch entirely.
    translate = _selective_translate_script(tmp_path)
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""\
[mail]
source = "mbox"

[mail.mbox]
path = "{FIXTURE_MBOX}"

[[chains]]
sender_domain = "example-chain.com"
translate = "{translate}"

[[chains]]
sender_domain = "unrelated-sender.com"
translate = "{translate}"
"""
    )
    output_path = tmp_path / "import.json"

    result = runner.invoke(
        app, ["fetch", "--config", str(config_path), "--output", str(output_path)]
    )

    assert result.exit_code == 0, result.output
    rows = json.loads(output_path.read_text())
    assert len(rows) == 2
    assert {row["title"] for row in rows} == {
        "Your booking confirmation",
        "A second booking confirmation",
    }
    assert all(row["source"] == "example-chain.com" for row in rows)
    assert "1 email(s) not recognized" in result.output
    assert "unrelated-sender.com" in result.output
    assert "This week in cinema" in result.output


def test_fetch_with_no_matches_writes_an_empty_array(tmp_path: Path) -> None:
    translate = _selective_translate_script(tmp_path)
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""\
[mail]
source = "mbox"

[mail.mbox]
path = "{FIXTURE_MBOX}"

[[chains]]
sender_domain = "nobody-sends-from-here.example"
translate = "{translate}"
"""
    )
    output_path = tmp_path / "import.json"

    result = runner.invoke(
        app, ["fetch", "--config", str(config_path), "--output", str(output_path)]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(output_path.read_text()) == []


def test_fetch_invalid_config_fails_clearly(tmp_path: Path) -> None:
    result = runner.invoke(app, ["fetch", "--config", str(tmp_path / "does-not-exist.toml")])

    assert result.exit_code != 0


def test_fetch_output_validates_against_movies_schema(tmp_path: Path) -> None:
    schema_path = Path(__file__).parent.parent / "examples" / "movies.schema.json"
    schema = json.loads(schema_path.read_text())

    translate = _selective_translate_script(tmp_path)
    config_path = _mbox_config(tmp_path, translate)
    output_path = tmp_path / "import.json"

    result = runner.invoke(
        app, ["fetch", "--config", str(config_path), "--output", str(output_path)]
    )

    assert result.exit_code == 0, result.output
    rows = json.loads(output_path.read_text())
    jsonschema.validate(rows, schema)


def test_fetch_run_twice_against_an_unchanged_mailbox_is_identical(tmp_path: Path) -> None:
    translate = _selective_translate_script(tmp_path)
    config_path = _mbox_config(tmp_path, translate)
    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"

    first = runner.invoke(
        app, ["fetch", "--config", str(config_path), "--output", str(first_output)]
    )
    second = runner.invoke(
        app, ["fetch", "--config", str(config_path), "--output", str(second_output)]
    )

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert first_output.read_text() == second_output.read_text()


# --- --envelopes-only / piped composition: task group 8 ---


def test_fetch_envelopes_only_prints_one_json_line_per_message_no_output_file(
    tmp_path: Path,
) -> None:
    config_path = _mbox_config(tmp_path, "irrelevant - not dispatched in this mode")
    output_path = tmp_path / "import.json"

    result = runner.invoke(
        app,
        ["fetch", "--config", str(config_path), "--output", str(output_path), "--envelopes-only"],
    )

    assert result.exit_code == 0, result.output
    assert not output_path.exists()
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 2
    envelopes = [json.loads(line) for line in lines]
    assert {e["subject"] for e in envelopes} == {
        "Your booking confirmation",
        "A second booking confirmation",
    }
    assert all({"from", "subject", "date", "body"} <= e.keys() for e in envelopes)


def test_fetch_envelopes_only_with_no_matches_prints_nothing(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""\
[mail]
source = "mbox"

[mail.mbox]
path = "{FIXTURE_MBOX}"

[[chains]]
sender_domain = "nobody-sends-from-here.example"
translate = "irrelevant"
"""
    )

    result = runner.invoke(app, ["fetch", "--config", str(config_path), "--envelopes-only"])

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == ""


# --- --since/--until: issue #159 ---


def test_fetch_since_relative_reaches_the_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_now = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
    monkeypatch.setattr("movie_planner.mail_import.cli._now", lambda: fixed_now)
    captured: dict[str, object] = {}
    monkeypatch.setattr(MboxMailClient, "fetch", _spy_fetch(captured))
    config_path = _mbox_config(tmp_path, "irrelevant")

    result = runner.invoke(app, ["fetch", "--config", str(config_path), "--since", "1 hour ago"])

    assert result.exit_code == 0, result.output
    assert captured["since"] == fixed_now - timedelta(hours=1)
    assert captured.get("until") is None


def test_fetch_until_relative_reaches_the_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_now = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
    monkeypatch.setattr("movie_planner.mail_import.cli._now", lambda: fixed_now)
    captured: dict[str, object] = {}
    monkeypatch.setattr(MboxMailClient, "fetch", _spy_fetch(captured))
    config_path = _mbox_config(tmp_path, "irrelevant")

    result = runner.invoke(app, ["fetch", "--config", str(config_path), "--until", "2 weeks ago"])

    assert result.exit_code == 0, result.output
    assert captured["until"] == fixed_now - timedelta(weeks=2)


def test_fetch_since_accepts_an_iso_date(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(MboxMailClient, "fetch", _spy_fetch(captured))
    config_path = _mbox_config(tmp_path, "irrelevant")

    result = runner.invoke(app, ["fetch", "--config", str(config_path), "--since", "2026-08-01"])

    assert result.exit_code == 0, result.output
    assert captured["since"] == datetime(2026, 8, 1, tzinfo=UTC)


def test_fetch_since_unparseable_fails_clearly(tmp_path: Path) -> None:
    config_path = _mbox_config(tmp_path, "irrelevant")

    result = runner.invoke(app, ["fetch", "--config", str(config_path), "--since", "nonsense"])

    assert result.exit_code != 0
    assert "--since" in result.output


def test_fetch_with_no_since_until_still_works(tmp_path: Path) -> None:
    config_path = _mbox_config(tmp_path, "irrelevant")

    result = runner.invoke(app, ["fetch", "--config", str(config_path), "--envelopes-only"])

    assert result.exit_code == 0, result.output
