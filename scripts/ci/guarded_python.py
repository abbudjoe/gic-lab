"""Run local Python with the pre-collection/child environmental guard installed."""

import argparse
import os
import sys
import uuid
from pathlib import Path

from local_container import LocalCIError, ProjectStorage

parser = argparse.ArgumentParser()
parser.add_argument("--journal", type=Path)
parser.add_argument(
    "--storage-config",
    type=Path,
    default=(Path(__file__).resolve().parents[2] / ".tools/local-ci-storage.json"),
)
parser.add_argument("arguments", nargs=argparse.REMAINDER)
args = parser.parse_args()
storage = ProjectStorage.load(args.storage_config)
name = "p15-" + uuid.uuid4().hex[:10]
run = storage.fresh("tmp", name)
results = storage.fresh("ci/results", name)
selected_environment = storage.environment(run)
journal = args.journal or results / "guard"
storage.destination(journal, missing_leaf=True)
journal.mkdir(mode=0o700, parents=False, exist_ok=False)
environment = dict(os.environ)
environment.update(selected_environment)
environment["COVERAGE_FILE"] = str(results / "coverage")
environment["QUARTO_LOG"] = str(results / "quarto.log")
environment["GICLAB_CI_GUARD_JOURNAL"] = str(journal)
environment["GICLAB_CI_GIT_FIXTURE_ROOT"] = str(run / "pytest")
environment["PYTHONPATH"] = os.pathsep.join(
    [str(Path(__file__).resolve().parent), environment.get("PYTHONPATH", "")]
)
environment["PYTHONDONTWRITEBYTECODE"] = "1"
arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
if arguments[:2] == ["-m", "pytest"]:
    if any(arg.startswith("--basetemp") or "cache_dir=" in arg for arg in arguments):
        raise LocalCIError("pytest scratch/cache are selected by the bound storage launcher")
    for index, arg in enumerate(arguments):
        if arg.split("=")[0] in {"--junitxml", "--junit-xml"}:
            value = arg.split("=", 1)[1] if "=" in arg else arguments[index + 1]
            storage.destination(Path(value), missing_leaf=True)
            if Path(value).exists():
                raise LocalCIError("pytest result destination must be fresh")
    junit = (
        []
        if any(arg.startswith(("--junitxml", "--junit-xml")) for arg in arguments)
        else ["--junitxml=" + str(results / "junit.xml")]
    )
    arguments = [
        *arguments[:2],
        "-p",
        "offline_guard",
        *arguments[2:],
        "--basetemp=" + str(run / "pytest"),
        "-o",
        "cache_dir=" + str(run / "pytest-cache"),
        *junit,
    ]
storage.recheck()
print("Guarded result root: " + str(results), flush=True)
os.execve(sys.executable, [sys.executable, *arguments], environment)
