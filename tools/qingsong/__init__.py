"""
Qingsong - Project Management Engine for MUST

A lightweight, file-based requirements/risk/interface management system
for the MUltiplexed Survey Telescope (MUST) project.

Named after the Chinese astronomer Yu Qingsong (余青松), a Tsinghua alumnus.
"""

__version__ = "0.1.0"
__author__ = "MUST Project Team"

from pathlib import Path
import os

# Project root detection
def get_project_root(start_path: Path | None = None) -> Path:
    """Find the project root by looking for env var, pyproject.toml, .git, or meta dir."""
    
    # 1. Check environment variable first (highest priority)
    env_root = os.environ.get("QINGSONG_ROOT")
    if env_root:
        return Path(env_root)

    current = start_path or Path.cwd()
    
    # 2. Check if the current dir is already a valid vault
    if (current / "meta").exists() and (current / "doorstop").exists():
        return current
        
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists() or ((parent / "meta").exists() and (parent / "doorstop").exists()):
            return parent
    return current

