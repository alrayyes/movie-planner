from typer.testing import CliRunner

from movie_planner.cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "movie-planner" in result.stdout
