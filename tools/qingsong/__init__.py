"""
Qingsong - Project Management Engine for MUST

A lightweight, file-based requirements/risk/interface management system
for the MUltiplexed Survey Telescope (MUST) project.

Named after the Chinese astronomer Yu Qingsong (余青松), a Tsinghua alumnus.
"""

__version__ = "0.1.0"
__author__ = "MUST Project Team"

from pathlib import Path

# Project root detection
def get_project_root() -> Path:
    """Find the project root by looking for pyproject.toml or .git."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
    return current


PROJECT_ROOT = get_project_root()
META_DIR = PROJECT_ROOT / "meta"
DOORSTOP_DIR = PROJECT_ROOT / "doorstop"
INDEX_DIR = PROJECT_ROOT / "index"
ASSETS_DIR = PROJECT_ROOT / "assets"

