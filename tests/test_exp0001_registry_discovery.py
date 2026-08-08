from __future__ import annotations

from pathlib import Path

from giclab.validation import validate_experiment_registry


def test_descriptive_experiment_directory_is_discovered(tmp_path: Path) -> None:
    experiments = tmp_path / "experiments"
    experiment = experiments / "EXP-0001-descriptive-name"
    template = experiments / "EXP-0000-template"
    experiment.mkdir(parents=True)
    template.mkdir()
    (experiments / "registry.yaml").write_text(
        "\n".join(
            (
                "schema_version: 0.1.0",
                "registry_revision: 1",
                "template_path: experiments/EXP-0000-template",
                "experiments: []",
            )
        ),
        encoding="utf-8",
    )
    errors = validate_experiment_registry(tmp_path)
    assert any("EXP-0001-descriptive-name" in error for error in errors)
