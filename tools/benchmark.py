"""Time loading and checking a synthetic vault (docs/SPEC.md §13).

uv run python tools/benchmark.py [records] [workdir]
"""

import datetime
import shutil
import sys
import tempfile
import time
from pathlib import Path

from ruamel.yaml import YAML

from qingsong import checks, operations
from qingsong.hashing import normative_hash_of, stamp_of
from qingsong.vault import load, record_adapter

systems = ["AAA", "BBB", "CCC", "DDD", "EEE"]
nodes_per_system = 10


def build(root: Path, count: int) -> None:
    operations.init_vault(root, "BENCH", "Benchmark")
    (root / "people.yaml").write_text(
        "people:\n  alice:\n    name: Alice\n    languages: [en, zh]\n    approver: true\n"
    )
    for system in systems:
        children = "".join(
            f"  - node: N{index:02d}\n    names: {{en: Node {index}}}\n    kind: product\n    status: active\n"
            for index in range(nodes_per_system)
        )
        (root / "tree" / f"{system}.yaml").write_text(
            f"parent: BENCH\nnode: {system}\nnames: {{en: System {system}}}\nkind: product\n"
            f"status: active\nchildren:\n{children}"
        )
    yaml = YAML(typ="safe", pure=True)
    yaml.default_flow_style = False
    day = datetime.date(2026, 11, 1)
    for index in range(count):
        system = systems[index % len(systems)]
        node = f"N{(index // len(systems)) % nodes_per_system:02d}"
        number = index // (len(systems) * nodes_per_system) + 1
        record_id = f"{system}-{node}-REQ-{number:03d}"
        data = {
            "id": record_id,
            "type": "requirement",
            "title": {"en": f"Requirement {index}", "zh": f"需求{index}"},
            "lifecycle": "current",
            "statement": {
                "en": f"The node shall meet limit {{limit}} in case {index}.",
                "zh": f"该节点在情形{index}下应满足{{limit}}。",
            },
            "values": {
                "limit": {
                    "relation": "le",
                    "value": float(index % 97),
                    "unit": "mm",
                    "certainty": "firm",
                }
            },
            "rationale": {"en": "Benchmark.", "zh": "基准测试。"},
            "level": "subsystem",
            "allocated_to": f"{system}-{node}",
            "justified_by": None,
            "verification": {"method": "test", "criteria": {"en": "Measure.", "zh": "测量。"}},
            "maturity": "draft",
            "text_origin": "en",
            "revision": 1,
            "normative_revision": 1,
            "normative_hash": "0" * 16,
            "history": [
                {"revision": 1, "date": day, "by": "alice", "event": "created", "summary": "bench"}
            ],
            "stamp": "0" * 16,
        }
        if number > 1:
            parent = f"{system}-{node}-REQ-{number - 1:03d}"
            data["derives_from"] = []
            data["rationale"]["en"] = f"Follows [[{parent}]]."
        data = {key: value for key, value in data.items() if value is not None}
        record = record_adapter.validate_python(data)
        data["normative_hash"] = normative_hash_of(record)
        data["stamp"] = stamp_of(record_adapter.validate_python(data))
        path = root / "requirements" / system / f"{record_id}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            yaml.dump(data, handle)


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000
    work = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(tempfile.mkdtemp())
    root = work / "bench_vault"
    if root.exists():
        shutil.rmtree(root)
    started = time.perf_counter()
    build(root, count)
    built = time.perf_counter()
    vault = load(root)
    loaded = time.perf_counter()
    findings = checks.run(vault)
    checked = time.perf_counter()
    errors = [finding for finding in findings if finding.severity == "error"]
    print(
        f"records: {len(vault.records)}; build {built - started:.1f} s; load {loaded - built:.2f} s; "
        f"check {checked - loaded:.2f} s; findings {len(findings)} ({len(errors)} errors)"
    )
    for finding in errors[:5]:
        print(finding.line())


if __name__ == "__main__":
    main()
