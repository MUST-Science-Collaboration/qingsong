"""Read earlier versions of a vault through the git command line (docs/SPEC.md §6.1)."""

import subprocess
from pathlib import Path

main_candidates = ("origin/main", "main")


def run_git(root: Path, *arguments: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *arguments], capture_output=True, text=True, check=False
        )
    except OSError as error:
        return subprocess.CompletedProcess(["git"], 127, "", str(error))


def is_repository(root: Path) -> bool:
    return run_git(root, "rev-parse", "--is-inside-work-tree").stdout.strip() == "true"


def ref_exists(root: Path, ref: str) -> bool:
    return run_git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode == 0


def main_refs(root: Path) -> list[str]:
    """Every main reference that exists (remote and local), so that neither is overlooked."""
    if not is_repository(root):
        return []
    return [candidate for candidate in main_candidates if ref_exists(root, candidate)]


def files_at(root: Path, ref: str, folder: str) -> list[str]:
    result = run_git(root, "ls-tree", "-r", "--name-only", ref, "--", folder)
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


def read_at(root: Path, ref: str, relative_path: str) -> str | None:
    result = run_git(root, "show", f"{ref}:./{relative_path}")
    return result.stdout if result.returncode == 0 else None
