"""Install the common offline effect boundary before test-module collection."""

import os
import sys
import tempfile
from pathlib import Path

GUARD_ROOT = Path(__file__).resolve().parents[1] / "scripts/ci"
sys.path.insert(0, str(GUARD_ROOT))
if "GICLAB_CI_GUARD_JOURNAL" not in os.environ:
    if sys.platform == "darwin":
        raise RuntimeError("use the configured guarded launcher for external host test storage")
    os.environ["GICLAB_CI_GUARD_JOURNAL"] = tempfile.mkdtemp(prefix="giclab-test-denials-")
os.environ["PYTHONPATH"] = os.pathsep.join([str(GUARD_ROOT), os.environ.get("PYTHONPATH", "")])

import offline_guard  # noqa: E402

offline_guard.install()
pytest_sessionfinish = offline_guard.pytest_sessionfinish
