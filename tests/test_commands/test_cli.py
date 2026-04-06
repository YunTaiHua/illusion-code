"""CLI smoke tests."""

from typer.testing import CliRunner

from illusion.cli import app


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Illusion Code!" in result.output
