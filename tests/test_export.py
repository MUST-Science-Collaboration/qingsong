import pytest
from tools.qingsong.core import QingsongCore
from tools.qingsong.export import (
    export_requirements_markdown, 
    export_risk_register_markdown, 
    export_interface_list_markdown, 
    export_summary_markdown
)

@pytest.fixture
def core():
    return QingsongCore.load()

def test_export_requirements(core, tmp_path):
    output = tmp_path / "reqs.md"
    export_requirements_markdown(core, output_path=output)
    assert output.exists()

def test_export_risks(core, tmp_path):
    output = tmp_path / "risks.md"
    export_risk_register_markdown(core, output_path=output)
    assert output.exists()

def test_export_interfaces(core, tmp_path):
    output = tmp_path / "ifcs.md"
    export_interface_list_markdown(core, output_path=output)
    assert output.exists()

def test_export_summary(core, tmp_path):
    output = tmp_path / "summary.md"
    export_summary_markdown(core, output_path=output)
    assert output.exists()
