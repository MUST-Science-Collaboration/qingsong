import pytest
import os
import shutil
from pathlib import Path
from typer.testing import CliRunner
from tools.qingsong.cli import app
from tools.qingsong.core import QingsongCore

runner = CliRunner()

def test_multi_vault_workflow(tmp_path):
    # 1. Initialize a new vault
    vault_path = tmp_path / "my_demo_vault"
    result = runner.invoke(app, ["init", str(vault_path), "--name", "Demo Project"])
    assert result.exit_code == 0
    assert "Initialized new Qingsong project" in result.stdout
    
    # Verify structure
    assert (vault_path / "meta" / "hierarchy.yaml").exists()
    assert (vault_path / "doorstop").exists()
    
    # 2. Create an item in the NEW vault using the global --root option
    result = runner.invoke(app, [
        "--root", str(vault_path), 
        "new", "req", 
        "--title", "Demo Requirement", 
        "--system", "SYS/SUB", 
        "--owner", "eng001",
        "--category", "functional"
    ])
    if result.exit_code != 0:
        print(result.stdout)
    assert result.exit_code == 0
    assert "Created item" in result.stdout
    assert "MUST-SYS-SUB-REQ" in result.stdout
    assert "001" in result.stdout
    
    # Verify the item exists on disk in the new vault
    item_file = vault_path / "doorstop" / "REQ" / "SYS" / "SUB" / "001.yml"
    assert item_file.exists()
    
    # 4. Verify we can list items from the new vault
    result = runner.invoke(app, ["--root", str(vault_path), "list"])
    assert result.exit_code == 0
    assert "Demo Requirement" in result.stdout
    
    # 5. Build cache for the new vault
    result = runner.invoke(app, ["--root", str(vault_path), "cache", "build"])
    assert result.exit_code == 0
    assert (vault_path / "index" / "qingsong.sqlite").exists()
