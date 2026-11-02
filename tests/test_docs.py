"""The generated documentation is current, and every link in it resolves (tools/build_docs.py)."""

import importlib.util
import re
from pathlib import Path

repository = Path(__file__).resolve().parents[1]


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_docs", repository / "tools" / "build_docs.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_documentation_is_current():
    builder = load_builder()
    stale = [
        path.relative_to(repository).as_posix()
        for path, text in builder.outputs().items()
        if not path.exists() or path.read_text(encoding="utf-8") != text
    ]
    assert not stale, f"run `uv run python tools/build_docs.py`; out of date: {stale}"


def test_every_link_in_the_pages_resolves():
    builder = load_builder()
    pages = {path: text for path, text in builder.outputs().items() if path.suffix == ".html"}
    anchors = {path: set(re.findall(r'\sid="([^"]+)"', text)) for path, text in pages.items()}
    broken = []
    for path, text in pages.items():
        for target in re.findall(r'href="([^"]+)"', text):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target):
                continue
            file_part, _, anchor = target.partition("#")
            resolved = (path.parent / file_part).resolve() if file_part else path
            if not resolved.exists() and resolved not in pages:
                broken.append(f"{path.name}: {target}")
            elif anchor and resolved in anchors and anchor not in anchors[resolved]:
                broken.append(f"{path.name}: {target} (no such anchor)")
    assert not broken, broken
