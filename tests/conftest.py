import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML

examples = Path(__file__).resolve().parents[1] / "examples"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_demo", examples / "build_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def built_demo(tmp_path_factory) -> Path:
    return load_builder().build(examples / "demo_source", tmp_path_factory.mktemp("built") / "demo")


@pytest.fixture
def demo(built_demo: Path, tmp_path: Path) -> Path:
    target = tmp_path / "demo"
    shutil.copytree(built_demo, target)
    return target


def git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments], capture_output=True, text=True, check=True
    )
    return result.stdout


@pytest.fixture
def demo_repository(demo: Path) -> Path:
    git(demo, "init", "-q", "-b", "main")
    git(demo, "-c", "user.name=Test", "-c", "user.email=test@example.org", "add", "-A")
    git(
        demo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.org",
        "commit",
        "-q",
        "-m",
        "demo",
    )
    return demo


def edit_yaml(path: Path, change) -> None:
    yaml = YAML(typ="rt")
    data = yaml.load(path.read_text(encoding="utf-8"))
    change(data)
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle)


def requirement_file(root: Path, record_id: str) -> Path:
    return root / "requirements" / record_id.split("-")[0] / f"{record_id}.yaml"
