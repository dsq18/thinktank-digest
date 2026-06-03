from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from .staging import run_staging_workflow

LOGGER = logging.getLogger(__name__)


def _run(command: list[str], cwd: Path) -> None:
    LOGGER.info("Running self-review command: %s", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def run_self_review(
    *,
    project_root: Path,
    sources_path: Path,
    db_path: Path,
    out_dir: Path,
    skip_pytest: bool = False,
) -> dict:
    _run([sys.executable, "-m", "compileall", "thinktank_digest", "tests"], project_root)
    if not skip_pytest:
        _run([sys.executable, "-m", "pytest"], project_root)
    result = run_staging_workflow(sources_path=sources_path, db_path=db_path, out_dir=out_dir)
    LOGGER.info("Self-review complete: %s", result)
    return result
