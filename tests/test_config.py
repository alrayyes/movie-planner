from pathlib import Path

import pytest

from movie_planner.config import ConfigError, load_config

VALID_CONFIG = """
[caldav]
url = "https://baikal.example.com/dav.php/calendars/moviewatcher/movies/"
username = "moviewatcher"
password = "hunter2"

[omdb]
api_key = "abc123"

[storage]
db_path = "~/.local/share/movie-planner/movies.db"
"""


def test_load_config_reads_all_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(VALID_CONFIG)

    config = load_config(config_path)

    assert config.caldav_url == "https://baikal.example.com/dav.php/calendars/moviewatcher/movies/"
    assert config.caldav_username == "moviewatcher"
    assert config.caldav_password == "hunter2"
    assert config.omdb_api_key == "abc123"
    assert config.db_path == Path("~/.local/share/movie-planner/movies.db").expanduser()


def test_load_config_missing_file_raises_clear_error(tmp_path: Path) -> None:
    missing_path = tmp_path / "does-not-exist.toml"

    with pytest.raises(ConfigError, match=str(missing_path)):
        load_config(missing_path)


def test_load_config_invalid_toml_raises_clear_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("this is not [valid toml")

    with pytest.raises(ConfigError, match="not valid TOML"):
        load_config(config_path)


@pytest.mark.parametrize(
    ("removed_section", "missing_key"),
    [
        ("[caldav]", "caldav"),
        ("[omdb]", "omdb"),
        ("[storage]", "storage"),
    ],
)
def test_load_config_missing_section_names_it(
    tmp_path: Path, removed_section: str, missing_key: str
) -> None:
    # Drop the named section header and every key/value line under it.
    filtered = []
    in_removed_section = False
    for line in VALID_CONFIG.splitlines():
        if line.strip() == removed_section:
            in_removed_section = True
            continue
        if line.strip().startswith("[") and line.strip() != removed_section:
            in_removed_section = False
        if in_removed_section and "=" in line:
            continue
        filtered.append(line)
    config_path = tmp_path / "config.toml"
    config_path.write_text("\n".join(filtered))

    with pytest.raises(ConfigError, match=missing_key):
        load_config(config_path)


def test_load_config_section_not_a_table_raises_clear_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        caldav = "oops, not a table"

        [omdb]
        api_key = "abc123"

        [storage]
        db_path = "~/.local/share/movie-planner/movies.db"
        """
    )

    with pytest.raises(ConfigError, match="caldav"):
        load_config(config_path)


def test_load_config_missing_key_within_section_names_dotted_path(tmp_path: Path) -> None:
    filtered = "\n".join(
        line for line in VALID_CONFIG.splitlines() if not line.startswith("url = ")
    )
    config_path = tmp_path / "config.toml"
    config_path.write_text(filtered)

    with pytest.raises(ConfigError, match="caldav.url"):
        load_config(config_path)


def test_load_config_default_path_uses_xdg_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    xdg_config_home = tmp_path / "xdg-config"
    config_dir = xdg_config_home / "movie-planner"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(VALID_CONFIG)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config_home))

    config = load_config()

    assert config.omdb_api_key == "abc123"


PASSWORD_COMMAND_CONFIG = """
[caldav]
url = "https://baikal.example.com/dav.php/calendars/moviewatcher/movies/"
username = "moviewatcher"
password_command = "printf hunter2"

[omdb]
api_key = "abc123"

[storage]
db_path = "~/.local/share/movie-planner/movies.db"
"""


def test_load_config_runs_password_command(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(PASSWORD_COMMAND_CONFIG)

    config = load_config(config_path)

    assert config.caldav_password == "hunter2"


def test_load_config_password_command_strips_one_trailing_newline(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(PASSWORD_COMMAND_CONFIG.replace('"printf hunter2"', '"echo hunter2"'))

    config = load_config(config_path)

    assert config.caldav_password == "hunter2"


def test_load_config_rejects_both_password_and_password_command(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        PASSWORD_COMMAND_CONFIG.replace(
            'password_command = "printf hunter2"',
            'password_command = "printf hunter2"\npassword = "hunter2"',
        )
    )

    with pytest.raises(ConfigError, match="password.*password_command"):
        load_config(config_path)


def test_load_config_missing_password_names_both_options(tmp_path: Path) -> None:
    filtered = "\n".join(
        line for line in VALID_CONFIG.splitlines() if not line.startswith("password = ")
    )
    config_path = tmp_path / "config.toml"
    config_path.write_text(filtered)

    with pytest.raises(ConfigError, match="password.*password_command"):
        load_config(config_path)


def test_load_config_password_command_failure_raises_clear_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(PASSWORD_COMMAND_CONFIG.replace('"printf hunter2"', '"false"'))

    with pytest.raises(ConfigError, match="password_command"):
        load_config(config_path)
