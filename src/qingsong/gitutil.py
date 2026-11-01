"""Read earlier versions of a vault through the git command line (docs/SPEC.md §6.1)."""

import subprocess
from pathlib import Path


def run_git(root: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *arguments], capture_output=True, text=True, check=False
    )


def is_repository(root: Path) -> bool:
    return run_git(root, "rev-parse", "--is-inside-work-tree").stdout.strip() == "true"


def ref_exists(root: Path, ref: str) -> bool:
    return run_git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode == 0


def main_ref(root: Path) -> str | None:
    if not is_repository(root):
        return None
    for candidate in ("origin/main", "main"):
        if ref_exists(root, candidate):
            return candidate
    return None


def files_at(root: Path, ref: str, folder: str) -> list[str]:
    result = run_git(root, "ls-tree", "-r", "--name-only", ref, "--", folder)
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


def read_at(root: Path, ref: str, relative_path: str) -> str | None:
    result = run_git(root, "show", f"{ref}:./{relative_path}")
    return result.stdout if result.returncode == 0 else None
