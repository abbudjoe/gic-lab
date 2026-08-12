from __future__ import annotations

import importlib.util
import os
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str) -> ModuleType:
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


secret_module = _load(
    "t07_pragmatic_secret_test",
    "containers/sira-smoke/pragmatic/materialize_openai_secret.py",
)
runner = _load(
    "t07_pragmatic_runner_test",
    "containers/sira-smoke/pragmatic/remote_runner.py",
)


def test_dotenv_parser_extracts_only_openai_assignment() -> None:
    raw = b"LAMBDA_API_KEY=lambda-canary\nOPENAI_API_KEY=openai-canary_123\n"
    assert secret_module.parse_openai_api_key(raw) == b"openai-canary_123"
    assert b"lambda-canary" not in secret_module.parse_openai_api_key(raw)


@pytest.mark.parametrize(
    "raw",
    [
        b"OPENAI_API_KEY=one\nOPENAI_API_KEY=two\n",
        b"LAMBDA_API_KEY=lambda-only\n",
        b"OPENAI_API_KEY=contains space\n",
        b"OPENAI_API_KEY=first\nmalformed\n",
    ],
)
def test_dotenv_parser_rejects_ambiguous_or_malformed_sources(raw: bytes) -> None:
    with pytest.raises(RuntimeError):
        secret_module.parse_openai_api_key(raw)


def test_secret_materialization_is_exclusive_and_mode_0600(tmp_path: Path) -> None:
    destination = tmp_path / "provider-key"
    secret_module.write_secret_exclusive(destination, b"dummy-canary")
    assert destination.read_bytes() == b"dummy-canary"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        secret_module.write_secret_exclusive(destination, b"replacement")


def test_remote_child_environment_scrubs_both_secret_channels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LAMBDA_API_KEY", "lambda-canary")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-canary")
    monkeypatch.setenv("SIRA_API_KEY", "sira-canary")
    environment = runner.safe_environment()
    assert "LAMBDA_API_KEY" not in environment
    assert "OPENAI_API_KEY" not in environment
    assert "SIRA_API_KEY" not in environment


def test_condition_commands_are_matched_except_declared_differences(tmp_path: Path) -> None:
    prefix = ["docker"]
    image_id = "sha256:" + "a" * 64
    reactive = runner.condition_container_argv(tmp_path, "reactive", prefix, image_id)
    simulative = runner.condition_container_argv(tmp_path, "simulative", prefix, image_id)

    assert reactive.count("--max_steps") == simulative.count("--max_steps") == 1
    assert reactive[reactive.index("--max_steps") + 1] == "1"
    assert simulative[simulative.index("--max_steps") + 1] == "1"
    assert reactive[reactive.index("--model") + 1] == runner.MODEL
    assert simulative[simulative.index("--model") + 1] == runner.MODEL
    assert reactive[reactive.index("--max_retry") + 1] == "0"
    assert simulative[simulative.index("--max_retry") + 1] == "0"
    assert reactive[reactive.index("--network") + 1] == "bridge"
    assert simulative[simulative.index("--network") + 1] == "bridge"
    assert "--pid" not in reactive
    assert "--pid" not in simulative
    assert "host" not in reactive
    assert "host" not in simulative
    assert not any(value.endswith(",rw") for value in reactive)
    assert not any(value.endswith(",rw") for value in simulative)
    assert "EXP-0001-SMOKE-REACTIVE" in reactive
    assert "EXP-0001-SMOKE-SIMULATIVE" in simulative


def test_run_root_allows_only_two_authorized_launch_ordinals() -> None:
    assert str(runner.run_root(1)).endswith("launch-0001")
    assert str(runner.run_root(2)).endswith("launch-0002")
    with pytest.raises(RuntimeError):
        runner.run_root(3)


def test_remote_runner_uses_python_310_compatible_utc_and_ephemeral_host_secret() -> None:
    assert runner.utc_now().endswith("Z")
    assert str(runner.REMOTE_SECRET).startswith("/home/ubuntu/")
    assert ".config/giclab" in str(runner.REMOTE_SECRET)


def test_pragmatic_containerfile_preserves_the_canonical_wheel_filename() -> None:
    containerfile = (ROOT / "containers/sira-smoke/pragmatic/Containerfile.amd64").read_text()
    assert "/opt/build/uv.whl" not in containerfile
    assert (
        "/opt/build/uv-0.11.7-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
    ) in containerfile


def test_browser_preflight_uses_the_frozen_virtual_environment() -> None:
    source = (ROOT / "containers/sira-smoke/pragmatic/remote_runner.py").read_text()
    assert 'create[create.index("--entrypoint") + 1] = "/opt/sira/.venv/bin/python"' in source
    assert 'stdout_path=setup_dir / "browser-inspect.json"' in source
    assert 'stdout_path=setup_dir / "browser-logs.stdout"' in source


def test_destroy_secret_zeroes_and_unlinks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "secret"
    path.write_bytes(b"dummy-canary")
    os.chmod(path, 0o600)
    monkeypatch.setattr(runner, "REMOTE_SECRET", path)
    assert runner.destroy_secret() is True
    assert not path.exists()
