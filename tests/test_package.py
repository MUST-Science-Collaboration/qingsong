import json

from conftest import requirement_file
from typer.testing import CliRunner

import qingsong
from qingsong.cli import app

runner = CliRunner()


def test_version_matches_package_metadata():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"qingsong {qingsong.__version__}"


def test_no_arguments_prints_help():
    result = runner.invoke(app, [])
    assert "Usage" in result.output


def test_check_json_on_clean_and_broken_vaults(demo):
    clean = runner.invoke(app, ["check", "--vault", str(demo), "--json"])
    assert clean.exit_code == 0
    assert json.loads(clean.stdout)["errors"] == 0
    requirement_file(demo, "INS-DET-REQ-001").write_text("id: [\n")
    broken = runner.invoke(app, ["check", "--vault", str(demo), "--json"])
    assert broken.exit_code == 1
    report = json.loads(broken.stdout)
    assert report["errors"] >= 1
    assert {"rule", "severity", "record", "file", "message", "fix"} <= set(report["findings"][0])


def test_new_revise_and_show_through_the_cli(demo):
    created = runner.invoke(
        app,
        [
            "new",
            "requirement",
            "--vault",
            str(demo),
            "--namespace",
            "INS-DET",
            "--title",
            "Gain",
            "--statement",
            "The gain shall be stable.",
            "--by",
            "alice",
            "--via",
            "claude",
            "--json",
        ],
    )
    assert created.exit_code == 0, created.output
    record_id = json.loads(created.stdout)["id"]
    shown = runner.invoke(app, ["show", record_id, "--vault", str(demo), "--json"])
    assert json.loads(shown.stdout)["history"][0]["via"] == "claude"
    refused = runner.invoke(
        app,
        [
            "revise",
            record_id,
            "--vault",
            str(demo),
            "--class",
            "editorial",
            "--summary",
            "x",
            "--by",
            "alice",
            "--json",
        ],
    )
    assert refused.exit_code == 2 and "nothing changed" in json.loads(refused.stdout)["error"]


def test_find_searches_both_languages_and_aliases(demo):
    by_chinese = runner.invoke(app, ["find", "读出噪声", "--vault", str(demo), "--json"])
    assert "INS-DET-REQ-001" in {hit["id"] for hit in json.loads(by_chinese.stdout)}
    by_alias = runner.invoke(app, ["find", "RD-001", "--vault", str(demo), "--json"])
    assert any("alias" in place for hit in json.loads(by_alias.stdout) for place in hit["where"])


def test_schema_and_init(tmp_path):
    schema = json.loads(runner.invoke(app, ["schema", "requirement"]).stdout)
    assert "statement" in schema["properties"]
    created = runner.invoke(
        app, ["init", str(tmp_path / "vault"), "--code", "ABC", "--name", "Test"]
    )
    assert created.exit_code == 0
    checked = runner.invoke(app, ["check", "--vault", str(tmp_path / "vault")])
    assert checked.exit_code == 0, checked.output
