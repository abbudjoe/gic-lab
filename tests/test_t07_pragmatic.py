from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from datetime import datetime
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
    comparison = runner.condition_command_comparison(tmp_path, prefix, image_id)
    assert comparison["matched"] is True
    assert comparison["approved_difference_fields"] == [
        "attempt_root",
        "condition_label",
        "container_name",
        "gate_mode",
        "job_name",
        "upstream_mode",
    ]
    assert len(comparison["differences"]) == 6


def test_condition_configurations_are_matched_except_declared_differences(
    tmp_path: Path,
) -> None:
    configurations = runner.condition_configurations(
        tmp_path, ["sudo", "-n", "docker"], "sha256:" + "a" * 64
    )
    comparison = runner.condition_configuration_comparison(configurations)
    assert comparison["matched"] is True
    assert comparison["approved_difference_fields"] == [
        "condition",
        "docker_argv",
        "model_call_attempt_cap",
        "order",
    ]
    assert {entry["field"] for entry in comparison["differences"]} == {
        "condition",
        "docker_argv",
        "model_call_attempt_cap",
        "order",
    }
    for field in (
        "adapter_cost_cap_usd",
        "attempts",
        "browser_steps",
        "model_token_cap",
        "retries",
        "wall_seconds",
    ):
        assert configurations["reactive"][field] == configurations["simulative"][field]


def test_run_root_allows_only_two_authorized_launch_ordinals() -> None:
    assert str(runner.run_root(1)).endswith("r2-run-launch-0001")
    assert str(runner.run_root(2)).endswith("r2-run-launch-0002")
    with pytest.raises(RuntimeError):
        runner.run_root(3)


def test_remote_runner_uses_utc_aware_timestamp_and_ephemeral_host_secret() -> None:
    timestamp = runner.utc_now()
    assert timestamp.endswith("Z")
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert parsed.utcoffset() is not None
    assert parsed.utcoffset().total_seconds() == 0
    assert str(runner.REMOTE_SECRET).startswith("/home/ubuntu/")
    assert ".config/giclab" in str(runner.REMOTE_SECRET)
    assert "r2" in str(runner.REMOTE_SECRET)


def test_pragmatic_containerfile_preserves_the_canonical_wheel_filename() -> None:
    containerfile = (ROOT / "containers/sira-smoke/pragmatic/Containerfile.amd64").read_text()
    assert "/opt/build/uv.whl" not in containerfile
    assert (
        "/opt/build/uv-0.11.7-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
    ) in containerfile
    assert "ARG PYTHON_RUNTIME_VERSION=3.11.14" in containerfile
    assert 'uv sync --frozen --extra eval --python "${PYTHON_RUNTIME_VERSION}"' in containerfile
    assert "UV_PYTHON_INSTALL_DIR=/opt/giclab-python" in containerfile
    assert 'python_version = ">=3.11"' not in containerfile
    assert "--python 3.10" not in containerfile
    assert "uv pip install" not in containerfile
    assert "/opt/giclab-python -xdev" in containerfile
    assert "COPY runtime_preflight.py /opt/giclab/runtime_preflight.py" in containerfile


def test_browser_preflight_uses_the_frozen_virtual_environment() -> None:
    source = (ROOT / "containers/sira-smoke/pragmatic/remote_runner.py").read_text()
    assert '"--entrypoint",\n        "/opt/sira/.venv/bin/python"' in source
    assert 'stdout_path=setup_dir / "browser-inspect.json"' in source
    assert 'stdout_path=setup_dir / "browser-logs.stdout"' in source


def test_all_runtime_container_entrypoints_use_exact_python311_venv(tmp_path: Path) -> None:
    command = runner.condition_container_argv(tmp_path, "reactive", ["docker"], "sha256:x")
    assert command[command.index("--entrypoint") + 1] == "/opt/sira/.venv/bin/python"
    assert command[command.index("--") + 1] == "/opt/sira/.venv/bin/python"
    assert runner.PYTHON_RUNTIME_VERSION == "3.11.14"


def test_owned_container_residue_is_exactly_prefix_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner,
        "output",
        lambda _: "aaa\tunrelated\nbbb\tgiclab-t07-pragmatic-r2-browser-0001",
    )
    assert runner.owned_container_residue(["docker"]) == [
        {
            "container_id": "bbb",
            "container_name": "giclab-t07-pragmatic-r2-browser-0001",
        }
    ]


def test_runtime_preflight_covers_every_pre_empirical_module() -> None:
    module = _load(
        "t07_pragmatic_runtime_preflight_test",
        "containers/sira-smoke/pragmatic/runtime_preflight.py",
    )
    required = {
        "giclab.harness.artifacts",
        "giclab.harness.budget",
        "giclab.harness.events",
        "giclab.harness.executor",
        "giclab.harness.models",
        "giclab.harness.plan",
        "giclab.harness.policy",
        "giclab.harness.regulation",
        "giclab.harness.safety",
        "giclab.harness.sira_container",
        "giclab.harness.sira_gate_a",
        "giclab.harness.sira_gate_a_runtime",
    }
    assert required <= set(module.RUNTIME_MODULES)
    assert module.EXPECTED_PYTHON == (3, 11, 14)
    assert module.UPSTREAM_RUNNER_SHA256 == runner.UPSTREAM_RUNNER_SHA256


def test_upstream_runner_load_probe_is_hash_bound_and_side_effect_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load(
        "t07_pragmatic_runtime_preflight_upstream_test",
        "containers/sira-smoke/pragmatic/runtime_preflight.py",
    )
    runner_fixture = tmp_path / "run_web_agent.py"
    runner_fixture.write_text(
        "def main(): pass\ndef make_agent(): pass\ndef make_llm(): pass\ndef run_episode(): pass\n",
        encoding="utf-8",
    )
    import_cwd = tmp_path / "import-cwd"
    import_cwd.mkdir()
    expected = runner.sha256_file(runner_fixture)
    monkeypatch.delenv("LAMBDA_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SIRA_API_KEY", raising=False)
    record = module.load_pinned_upstream_runner(
        runner_fixture,
        import_cwd,
        expected_sha256=expected,
    )
    assert record["sha256"] == expected
    assert record["status"] == "passed"
    assert record["browser_or_model_action"] is False
    assert list(import_cwd.iterdir()) == []
    with pytest.raises(RuntimeError, match="digest drifted"):
        module.load_pinned_upstream_runner(
            runner_fixture,
            import_cwd,
            expected_sha256="0" * 64,
        )


def test_runtime_preflight_executes_artifact_budget_command_and_cleanup_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load(
        "t07_pragmatic_runtime_preflight_execution_test",
        "containers/sira-smoke/pragmatic/runtime_preflight.py",
    )
    (tmp_path / "condition-commands-input.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "commands": {
                    "reactive": [sys.executable, "-c", "reactive"],
                    "simulative": [sys.executable, "-c", "simulative"],
                },
            }
        ),
        encoding="utf-8",
    )
    fixture_runner = tmp_path / "pinned-runner.py"
    fixture_runner.write_text(
        "def main(): pass\ndef make_agent(): pass\ndef make_llm(): pass\ndef run_episode(): pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "UPSTREAM_RUNNER", fixture_runner)
    monkeypatch.setattr(module, "UPSTREAM_RUNNER_SHA256", runner.sha256_file(fixture_runner))
    monkeypatch.delenv("LAMBDA_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SIRA_API_KEY", raising=False)
    document = module.run(tmp_path)
    assert document["python_version"] == "3.11.14"
    assert len(document["python_executable_sha256"]) == 64
    assert document["utc_offset_seconds"] == 0
    assert document["artifact_writer"] == "passed"
    assert document["budget_ledger"] == "passed"
    assert document["condition_command_renderer"] == "passed"
    assert set(document["rendered_condition_command_sha256"]) == {
        "reactive",
        "simulative",
    }
    assert document["owned_cleanup"] == "passed"
    assert document["upstream_runner_import"]["status"] == "passed"
    assert (tmp_path / "runtime-preflight.json").is_file()


def test_exact_python310_compile_and_import_smoke() -> None:
    python310 = Path(
        "/Users/joseph/.local/share/uv/python/cpython-3.10-macos-aarch64-none/bin/python3.10"
    )
    if not python310.is_file():
        pytest.skip("exact local Python 3.10 interpreter is unavailable")
    runtime = ROOT / "containers/sira-smoke/pragmatic"
    compiled = subprocess.run(
        [
            str(python310),
            "-m",
            "compileall",
            "-q",
            str(ROOT / "src/giclab"),
            str(runtime),
            str(ROOT / "containers/sira-smoke/container_entrypoint.py"),
            str(ROOT / "containers/sira-smoke/bounded/model_preflight.py"),
            str(ROOT / "containers/sira-smoke/bounded/browser_preflight.py"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert compiled.returncode == 0, compiled.stderr
    smoke = subprocess.run(
        [str(python310), str(runtime / "python310_import_smoke.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert smoke.returncode == 0, smoke.stderr
    assert "python=3.10." in smoke.stdout
    assert "modules=5" in smoke.stdout
    assert "utc=" in smoke.stdout


def test_python311_runtime_choice_is_bound_to_repository_contract() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    lockfile = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.11"' in pyproject
    assert 'requires-python = ">=3.11"' in lockfile
    assert runner.PYTHON_RUNTIME_VERSION == "3.11.14"


def test_setup_does_not_complete_when_upstream_import_preflight_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "remote-root"
    context = tmp_path / "build-context"
    context.mkdir()
    (context / "runtime_preflight.py").write_text("fixture\n", encoding="utf-8")
    monkeypatch.setattr(runner, "run_root", lambda _: root)
    monkeypatch.setattr(runner, "validate_secret_metadata", lambda: None)
    monkeypatch.setattr(runner, "docker_prefix", lambda *_args, **_kwargs: ["docker"])
    monkeypatch.setattr(runner, "prepare_build_context", lambda *_args: context)
    monkeypatch.setattr(runner, "run_capture", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runner, "output", lambda *_args, **_kwargs: "sha256:" + "a" * 64)
    monkeypatch.setattr(
        runner,
        "runtime_preflight",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("upstream import failed")),
    )
    with pytest.raises(RuntimeError, match="upstream import failed"):
        runner.setup(1)
    assert not (root / "setup-complete.json").exists()


def test_retry2_manifest_identity_and_runtime_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "launch-0001"
    root.mkdir()
    (root / "setup-complete.json").write_text(
        json.dumps(
            {
                "image_id": "sha256:" + "a" * 64,
                "python_version": "3.11.14",
                "upstream_runner_sha256": runner.UPSTREAM_RUNNER_SHA256,
                "python_executable_sha256": "d" * 64,
                "uv_lock_sha256": runner.UV_LOCK_SHA256,
                "installed_package_manifest_sha256": "e" * 64,
                "playwright_version": "1.39.0",
                "chromium_revision": "1084",
                "chromium_executable_sha256": "f" * 64,
                "runtime_preflight_sha256": "b" * 64,
            }
        )
    )
    (root / "docker-prefix.json").write_text(json.dumps({"argv_prefix": ["docker"]}))
    monkeypatch.setattr(runner, "run_root", lambda _: root)
    runner.render_manifest(1, "c" * 40, "instance", "us-east-1", "image")
    manifest = json.loads((root / "run-manifest.json").read_text())
    assert manifest["manifest_id"] == "T07-PRAGMATIC-SMOKE-RUN-0002"
    assert manifest["run_identities"] == {
        "host": "RUN-T07-PRAGMATIC-HOST-0002",
        "reactive": "RUN-T07-PRAGMATIC-SIRA-REACTIVE-0002",
        "simulative": "RUN-T07-PRAGMATIC-SIRA-SIMULATIVE-0002",
    }
    assert manifest["runtime"]["python_version"] == "3.11.14"
    assert manifest["runtime"]["python_contract"] == ">=3.11"
    assert manifest["runtime"]["python_executable_sha256"] == "d" * 64
    assert manifest["runtime"]["uv_lock_sha256"] == runner.UV_LOCK_SHA256
    assert manifest["runtime"]["upstream_runner_sha256"] == runner.UPSTREAM_RUNNER_SHA256
    assert manifest["runtime"]["installed_package_manifest_sha256"] == "e" * 64
    assert manifest["runtime"]["playwright_version"] == "1.39.0"
    assert manifest["runtime"]["chromium_revision"] == "1084"
    assert "condition_identity" in manifest["permitted_condition_differences"]
    assert "condition_order" in manifest["permitted_condition_differences"]
    assert "source-derived model-call-attempt cap" in manifest["permitted_condition_differences"]
    assert (root / "condition-command-diff.json").is_file()
    assert (root / "condition-configuration-diff.json").is_file()


def test_empirical_boundary_requires_condition_model_or_browser_action(tmp_path: Path) -> None:
    empty = runner.condition_usage(tmp_path)
    assert empty["empirical_boundary_crossed"] is False
    assert empty["model_call_attempts"] == 0
    assert empty["browser_actions"] == 0

    (tmp_path / "provider-budget.json").write_text(
        json.dumps(
            {
                "model_call_attempts": 1,
                "input_tokens": 50,
                "cached_input_tokens": 0,
                "output_tokens": 10,
                "total_tokens": 60,
                "browser_actions": 0,
                "unreconciled_provider_attempts": 0,
                "cost_usd": 0.000225,
            }
        )
    )
    observed = runner.condition_usage(tmp_path)
    assert observed["empirical_boundary_crossed"] is True
    assert observed["model_call_attempts"] == 1


def test_empirical_boundary_detects_session_history_without_budget_increment(
    tmp_path: Path,
) -> None:
    output = tmp_path / "sira-output"
    output.mkdir()
    (output / "session.json").write_text(json.dumps({"history": [{"action": "one"}]}))
    observed = runner.condition_usage(tmp_path)
    assert observed["empirical_boundary_crossed"] is True
    assert observed["browser_actions"] == 1


def test_destroy_secret_zeroes_and_unlinks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "secret"
    path.write_bytes(b"dummy-canary")
    os.chmod(path, 0o600)
    monkeypatch.setattr(runner, "REMOTE_SECRET", path)
    assert runner.destroy_secret() is True
    assert not path.exists()
