from pathlib import Path

import pytest

from movie_planner.config_file import ConfigFileError, has_section, write_section


def test_has_section_is_false_when_the_file_does_not_exist(tmp_path: Path) -> None:
    assert has_section(tmp_path / "config.toml", "movie_planner") is False


def test_has_section_is_false_when_the_section_is_absent(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[mail_import]\nsource = "mbox"\n')

    assert has_section(config_path, "movie_planner") is False


def test_has_section_is_true_when_the_section_is_present(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[movie_planner]\ncaldav_url = "https://example.com"\n')

    assert has_section(config_path, "movie_planner") is True


def test_has_section_raises_for_invalid_toml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("not [ valid toml")

    with pytest.raises(ConfigFileError, match="not valid TOML"):
        has_section(config_path, "movie_planner")


def test_write_section_creates_a_new_file_and_its_parent_directory(tmp_path: Path) -> None:
    config_path = tmp_path / "nested" / "config.toml"

    write_section(config_path, '[movie_planner]\ncaldav_url = "https://example.com"\n')

    assert config_path.is_file()
    assert 'caldav_url = "https://example.com"' in config_path.read_text()


def test_write_section_preserves_an_existing_unrelated_section(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[mail_import]\nsource = "mbox"\n')

    write_section(config_path, '[movie_planner]\ncaldav_url = "https://example.com"\n')

    text = config_path.read_text()
    assert 'source = "mbox"' in text
    assert 'caldav_url = "https://example.com"' in text


def test_write_section_overwrites_only_its_own_section(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[movie_planner]\ncaldav_url = "https://old.example.com"\n')

    write_section(config_path, '[movie_planner]\ncaldav_url = "https://new.example.com"\n')

    text = config_path.read_text()
    assert "old.example.com" not in text
    assert "https://new.example.com" in text


def test_write_section_preserves_comments_in_the_untouched_section(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('# a note about mail import\n[mail_import]\nsource = "mbox"\n')

    write_section(config_path, '[movie_planner]\ncaldav_url = "https://example.com"\n')

    assert "# a note about mail import" in config_path.read_text()


def test_write_section_raises_for_invalid_existing_toml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("not [ valid toml")

    with pytest.raises(ConfigFileError, match="not valid TOML"):
        write_section(config_path, '[movie_planner]\ncaldav_url = "https://example.com"\n')
