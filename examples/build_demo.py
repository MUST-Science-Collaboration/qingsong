"""Build the stamped demo vault examples/demo from the hand-written sources in examples/demo_source.

uv run python examples/build_demo.py
"""

import datetime
import shutil
import sys
from pathlib import Path

from qingsong import operations
from qingsong.schema import record_folders

examples = Path(__file__).resolve().parent
build_date = datetime.date(2026, 11, 1)


def build(source: Path, target: Path) -> Path:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    for folder in record_folders.values():
        for path in sorted((target / folder).rglob("*.yaml")):
            operations.adopt(
                target,
                path,
                "alice",
                "written for the demo vault",
                event="created",
                translation="reviewed",
                today=build_date,
            )
    operations.approve(target, "INS-SYS-REQ-001", "agreed", "alice", "demo#1", today=build_date)
    return target


if __name__ == "__main__":
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else examples / "demo"
    print(f"built {build(examples / 'demo_source', destination)}")
