from typer.testing import CliRunner

import qingsong
from qingsong.cli import app


def test_version_matches_package_metadata():
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"qingsong {qingsong.__version__}"


def test_no_arguments_prints_help():
    result = CliRunner().invoke(app, [])
    assert "Usage" in result.output
