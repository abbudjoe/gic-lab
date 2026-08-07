"""Generate public Quarto views from canonical typed repository records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from giclab.registry import discover_repo_root, load_yaml, resolve_repo_path

ROOT = discover_repo_root()


def _front_matter(title: str) -> str:
    return f'---\ntitle: "{title}"\n---\n\n'


def _badge(value: Any) -> str:
    normalized = str(value).lower().replace("_", "-")
    return f'<span class="status status-{normalized}">{value}</span>'


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def build_status(root: Path) -> str:
    state = load_yaml(root / "docs/PROJECT_STATE.yaml")
    compute = load_yaml(root / "manifests/compute.yaml")["phase_zero_summary"]
    return (
        _front_matter("Project status")
        + f"""
This page is generated from `docs/PROJECT_STATE.yaml` and
`manifests/compute.yaml`. Do not edit it directly.

## Current gate

| Field | Value |
|---|---|
| Phase | {state["phase"]} — {state["phase_name"]} |
| Phase status | {_badge(state["phase_status"])} |
| Paid compute allowed | `{str(state["paid_compute_allowed"]).lower()}` |
| Prototype execution allowed | `{str(state["prototype_execution_allowed"]).lower()}` |
| Benchmark execution allowed | `{str(state["benchmark_execution_allowed"]).lower()}` |
| Training allowed | `{str(state["training_allowed"]).lower()}` |
| Cloud mutation allowed | `{str(state["cloud_mutation_allowed"]).lower()}` |

## Recorded Phase 0 resource use

| Measure | Value |
|---|---:|
| Cloud mutations | {compute["cloud_mutations"]} |
| Accelerator hours | {compute["accelerator_hours"]} |
| Paid compute cost (USD) | {compute["cost_usd"]} |
| Prototype runs | {compute["prototype_runs"]} |
| Benchmark runs | {compute["benchmark_runs"]} |
| Training runs | {compute["training_runs"]} |

No prototype result has been reproduced. Current work is repository and
research-control infrastructure only.
"""
    )


def build_experiments(root: Path) -> str:
    registry = load_yaml(root / "experiments/registry.yaml")
    entries = registry["experiments"]
    lines = [
        _front_matter("Experiment registry"),
        "This page is generated from `experiments/registry.yaml` and registered protocols. "
        "`EXP-0000` is a template and is never published as an experiment.\n",
    ]
    if not entries:
        lines.append(
            "## No registered experiments\n\n"
            "Phase 0 has not run or registered an empirical experiment.\n"
        )
        return "\n".join(lines)
    lines.extend(
        [
            "| ID | Title | Lifecycle | Evidence | Outcome | Study stage |",
            "|---|---|---|---|---|---|",
        ]
    )
    for entry in entries:
        protocol_path = resolve_repo_path(root, str(entry["protocol"]))
        protocol = load_yaml(protocol_path)
        lines.append(
            "| {id} | {title} | {life} | {evidence} | {outcome} | {stage} |".format(
                id=protocol["experiment_id"],
                title=protocol["title"],
                life=_badge(protocol["lifecycle_status"]),
                evidence=_badge(protocol["evidence_status"]),
                outcome=_badge(protocol["outcome_status"]),
                stage=protocol["study_stage"],
            )
        )
    return "\n".join(lines) + "\n"


def build_decisions(root: Path) -> str:
    source = (root / "docs/DECISIONS.md").read_text(encoding="utf-8")
    body = source.split("\n", maxsplit=1)[1] if "\n" in source else source
    return _front_matter("Decisions") + (
        "This page is generated from `docs/DECISIONS.md`; the repository document is canonical.\n\n"
        + body.lstrip()
    )


def build_falsification(root: Path) -> str:
    source = (root / "docs/FALSIFICATION_NOTES.md").read_text(encoding="utf-8")
    body = source.split("\n", maxsplit=1)[1] if "\n" in source else source
    return _front_matter("Falsification notes") + (
        "This page is generated from `docs/FALSIFICATION_NOTES.md`; "
        "the repository document is canonical.\n\n" + body.lstrip()
    )


def build_site_data(root: Path = ROOT) -> tuple[Path, ...]:
    output = root / "notebook/generated"
    paths = (
        output / "status.qmd",
        output / "experiments.qmd",
        output / "decisions.qmd",
        output / "falsification.qmd",
    )
    _write(paths[0], build_status(root))
    _write(paths[1], build_experiments(root))
    _write(paths[2], build_decisions(root))
    _write(paths[3], build_falsification(root))
    return paths


def main() -> None:
    paths = build_site_data()
    print(f"Generated {len(paths)} public notebook views.")


if __name__ == "__main__":
    main()
