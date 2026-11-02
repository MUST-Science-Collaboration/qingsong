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


def first_parent_commits(root: Path, ref: str, relative_path: str) -> list[str]:
    """Commits on the first-parent history of REF that touched the path, oldest first."""
    result = run_git(
        root, "log", "--first-parent", "--reverse", "--format=%H", ref, "--", relative_path
    )
    return result.stdout.split() if result.returncode == 0 else []


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
    process = subprocess.run(
        ["git", "-C", str(root), "cat-file", "--batch"],
        input="".join(f"{object_id}\n" for object_id, _ in entries).encode(),
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise GitError(process.stderr.decode(errors="replace").strip() or "git cat-file failed")
    output, offset = process.stdout, 0
    base = target.resolve()
    for object_id, path in entries:
        header_end = output.index(b"\n", offset)
        header = output[offset:header_end].decode().split()
        if len(header) != 3 or header[0] != object_id:
            raise GitError(f"unexpected answer from git cat-file for {path}")
        size = int(header[2])
        start = header_end + 1
        content = output[start : start + size]
        offset = start + size + 1
        destination = (base / path).resolve()
        if base not in destination.parents:
            raise GitError(f"{path} lies outside the vault folder")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)


def is_ancestor(root: Path, commit: str, ref: str) -> bool:
    return run_git(root, "merge-base", "--is-ancestor", commit, ref).returncode == 0
