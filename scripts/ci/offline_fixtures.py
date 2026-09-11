"""Exact source-bound environmental inputs shared by base/head offline pytest.

The retained pre-entry negative already supplies empty owned-container inventory,
but omitted its second exact-name inventory query. Supply that same low-level
environmental fact; the actual fatal-exit, accounting, evidence and cleanup logic
and the original assertions still run. No Docker process is dispatched.
"""

import ast
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

PREENTRY_NODE = (
    "tests/test_t09_retry5.py::test_retry5_preentry_core_incident_is_a_permanent_nonretryable_stop"
)
PREENTRY_SOURCE_SHA256 = "a7931148a37ab1e06e1fc73b7d84975a1601afd8afcbe11b799bc148ee37db9e"
INVENTORY_ARGV = [
    "docker",
    "ps",
    "--all",
    "--filter",
    "name=^/giclab-t09-pilot-v7-preentry$",
    "--format",
    "{{.ID}}",
]


class BoundContainerInventory:
    """One declared empty inventory response; all other operations stay guarded."""

    def __init__(self, native):
        self.native = native
        self.calls = 0

    def __getattr__(self, name):
        return getattr(self.native, name)

    def run(self, argv, **kwargs):
        if list(argv) != INVENTORY_ARGV:
            return self.native.run(argv, **kwargs)
        if self.calls:
            raise AssertionError("bound container inventory consumed twice")
        self.calls += 1
        text = bool(kwargs.get("text") or kwargs.get("encoding"))
        return subprocess.CompletedProcess(argv, 0, "" if text else b"", "" if text else b"")


@pytest.fixture(autouse=True)
def source_bound_preentry_inventory(request, monkeypatch):
    if request.node.nodeid != PREENTRY_NODE:
        yield
        return
    source = Path(request.module.__file__).read_bytes()
    function_name = PREENTRY_NODE.split("::")[1]
    function = next(
        n
        for n in ast.parse(source).body
        if isinstance(n, ast.FunctionDef) and n.name == function_name
    )
    encoded = b"".join(source.splitlines(keepends=True)[function.lineno - 1 : function.end_lineno])
    assert hashlib.sha256(encoded).hexdigest() == PREENTRY_SOURCE_SHA256, (
        "offline fixture source drift"
    )
    original = request.module._host
    observers = []

    def load_host(name):
        host = original(name)
        observer = BoundContainerInventory(host.subprocess)
        host.subprocess = observer
        observers.append(observer)
        return host

    monkeypatch.setattr(request.module, "_host", load_host)
    yield
    assert len(observers) == 1 and observers[0].calls == 1
    record = (
        json.dumps(
            {
                "fixture": "preentry-exact-name-empty-container-inventory",
                "source_sha256": PREENTRY_SOURCE_SHA256,
                "queries": 1,
                "native_dispatches": 0,
                "classification": "explicit low-level offline input; no phase receipt",
            },
            sort_keys=True,
        ).encode()
        + b"\n"
    )
    target = Path(os.environ["GICLAB_CI_GUARD_JOURNAL"]) / "preentry.fixture-jsonl"
    fd = os.open(target, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        assert os.fstat(fd).st_size + len(record) <= 8192
        assert os.write(fd, record) == len(record)
    finally:
        os.close(fd)
