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


class GitError(Exception):
    pass


def commit_of(root: Path, ref: str) -> str | None:
    result = run_git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return result.stdout.strip() if result.returncode == 0 else None


def head_commit(root: Path) -> str | None:
    return commit_of(root, "HEAD") if is_repository(root) else None


def is_dirty(root: Path) -> bool:
    """Uncommitted changes, untracked files included, inside the vault folder."""
    return bool(run_git(root, "status", "--porcelain", "--", ".").stdout.strip())


def tag_exists(root: Path, tag: str) -> bool:
    return run_git(root, "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}").returncode == 0


def create_tag(root: Path, tag: str, commit: str, message: str) -> None:
    result = run_git(root, "tag", "-a", tag, commit, "-m", message)
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"git tag {tag} failed")


def first_parent_history(root: Path, ref: str, relative_path: str) -> list[tuple[str, str]]:
    """(commit, the file's path in it) for the commits on the first-parent history of REF that
    touched the file, oldest first. Renames are followed."""
    result = run_git(
        root,
        "log",
        "--first-parent",
        "--follow",
        "--relative",
        "--name-only",
        "--format=%x01%H",
        ref,
        "--",
        relative_path,
    )
    if result.returncode != 0:
        return []
    entries = []
    for chunk in result.stdout.split("\x01"):
        lines = [line for line in chunk.splitlines() if line.strip()]
        if len(lines) >= 2:
            entries.append((lines[0], lines[-1]))
    entries.reverse()
    return entries


def export_tree(root: Path, ref: str, target: Path) -> None:
    """Write the vault folder as stored at REF into TARGET, from the raw objects: no checkout, no
    archive filters and no line-ending conversion (docs/SPEC.md §5.5)."""
    if commit_of(root, ref) is None:
        raise GitError(f"git reference {ref!r} not found")
    listing = run_git(root, "ls-tree", "-r", "-z", ref, "--", ".")
    if listing.returncode != 0:
        raise GitError(listing.stderr.strip() or f"cannot list {ref}")
    entries: list[tuple[str, str]] = []
    for item in listing.stdout.split("\0"):
        if not item:
            continue
        meta, _, path = item.partition("\t")
        mode, kind, object_id = meta.split()
        if kind != "blob" or mode == "120000":
            continue
        entries.append((object_id, path))
    if not entries:
        raise GitError(f"{ref} holds no files in this folder")
    base = target.resolve()
    process = subprocess.Popen(
        ["git", "-C", str(root), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert process.stdin is not None and process.stdout is not None
    try:
        for object_id, path in entries:
            process.stdin.write(f"{object_id}\n".encode())
            process.stdin.flush()
            header = process.stdout.readline().decode().split()
            if len(header) != 3 or header[0] != object_id:
                raise GitError(f"git cat-file could not read {path}")
            content = process.stdout.read(int(header[2]))
            process.stdout.read(1)
            destination = (base / path).resolve()
            if base not in destination.parents:
                raise GitError(f"{path} lies outside the vault folder")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
    finally:
        process.stdin.close()
        process.stdout.close()
        process.wait()


def is_ancestor(root: Path, commit: str, ref: str) -> bool:
    return run_git(root, "merge-base", "--is-ancestor", commit, ref).returncode == 0
