"""Reject deterministic fixture assumptions from effect-neutral production source."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from giclab.control.category3 import repository_identity

ANTI_SHADOW_LINT_SCHEMA_VERSION: Final = "1.0.0"
AUDITED_BASE_COMMIT: Final = "f1d872d59c4952eb98467c2506850af7772f4454"
AUDITED_BASE_TREE: Final = "eb70e20024559d65b3fadd240f72d3522895ef04"
SHARED_EFFECT_NEUTRAL_SOURCES: Final = (
    "src/giclab/control/adapters.py",
    "src/giclab/control/category3.py",
    "src/giclab/control/consumers.py",
    "src/giclab/control/contracts.py",
    "src/giclab/control/effects.py",
    "src/giclab/control/production.py",
)
INVENTORY_ROOTS: Final = (
    "src/giclab/control",
    "tests/control",
    "docs",
    "control/incidents",
)
INVENTORY_SUFFIXES: Final = frozenset({".json", ".md", ".py", ".yaml", ".yml"})
LINT_DEFINITION_PATH: Final = "src/giclab/control/anti_shadow_lint.py"

_FORBIDDEN_TEXT: Final = (
    ("T09S001", re.compile(r"_FAKE_OPENAI_VALUE"), "fake OpenAI credential constant"),
    ("T09S002", re.compile(r"_FAKE_LAMBDA_VALUE"), "fake provider credential constant"),
    ("T09S003", re.compile(r"CALL-SHADOW"), "shadow call identity"),
    ("T09S004", re.compile(r"shadow-response"), "shadow response identity"),
    ("T09S005", re.compile(r"shadow-finalized"), "shadow finalizer path"),
    ("T09S006", re.compile(r"_TASK_A_ANSWER"), "canned Task A answer"),
    ("T09S007", re.compile(r"_TASK_B_ANSWER"), "canned Task B answer"),
    ("T09S008", re.compile(r"\bFakeScenario\b"), "scenario-driven production branch"),
    (
        "T09S009",
        re.compile(r"(?<![0-9])1_?700_?000_?000(?:\.0)?(?![0-9])"),
        "fixed fake epoch",
    ),
    ("T09S010", re.compile(r"production-shadow"), "production-shadow identity"),
)
_INVENTORY_TEXT: Final = (
    re.compile(r"_FAKE_(?:OPENAI|LAMBDA)_VALUE"),
    re.compile(r"CALL-SHADOW"),
    re.compile(r"shadow-response"),
    re.compile(r"shadow-finalized"),
    re.compile(r"production-shadow"),
    re.compile(r"_TASK_[AB]_ANSWER"),
    re.compile(r"\bFakeScenario\b"),
    re.compile(r"(?<![0-9])1_?700_?000_?000(?:\.0)?(?![0-9])"),
    re.compile(r"max_model_call_attempts\s*[=:]\s*1\b"),
    re.compile(r"max_model_calls\s*[=:]\s*1\b"),
)


@dataclass(frozen=True, slots=True)
class AntiShadowFinding:
    path: str
    line: int
    column: int
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ShadowAssumptionOccurrence:
    path: str
    line: int
    token: str
    classification: str


@dataclass(frozen=True, slots=True)
class BaseShadowAssumption:
    assumption_id: str
    path: str
    source_lines: str
    classification: str
    defect: str
    repair_boundary: str


BASE_SHADOW_ASSUMPTION_INVENTORY: Final = (
    BaseShadowAssumption(
        "SA-01",
        "src/giclab/control/production.py",
        "73-74, 105, 160-163, 415-417",
        "shared production-wrapper defect",
        "module fake credentials and equality checks controlled metadata transport",
        "exact mutable parser credential reaches the injected one-send metadata channel",
    ),
    BaseShadowAssumption(
        "SA-02",
        "src/giclab/control/production.py",
        "568-580, 1305-1314, 1670",
        "shared production-wrapper defect",
        "advancing synthetic time, synthetic sleep, and fixed freeze/checkpoint epochs",
        "validated injected monotonic, wall-time, and sleep domains",
    ),
    BaseShadowAssumption(
        "SA-03",
        "src/giclab/control/production.py",
        "1027-1076",
        "shared production-wrapper defect",
        "staging wrote a three-field synthetic fixture instead of the tracked package closure",
        "typed tracked-only archive, acknowledgement, and host-side rehash receipt",
    ),
    BaseShadowAssumption(
        "SA-04",
        "src/giclab/control/production.py",
        "1238-1272",
        "shared production-wrapper defect",
        "host preflight reconstructed a reduced provider-entry document",
        "typed preflight consumes the exact retained launch receipt",
    ),
    BaseShadowAssumption(
        "SA-05",
        "src/giclab/control/production.py",
        "1274-1314",
        "shared production-wrapper defect",
        "qualification and freeze returned synthetic identities without actual effect receipts",
        "request-bound host qualification and dynamic freeze manifests are validated",
    ),
    BaseShadowAssumption(
        "SA-06",
        "src/giclab/control/production.py",
        "1404-1503",
        "shared production-wrapper defect",
        "fixed caps and one hardcoded CRITIC request modeled every condition",
        "package-derived caps and a multi-call/multi-role/multi-action event session",
    ),
    BaseShadowAssumption(
        "SA-07",
        "src/giclab/control/production.py",
        "1505-1543",
        "shared production-wrapper defect",
        "raw manifest and completion identities were synthesized from in-memory accounting",
        "file-backed raw seal, ledgers, process/completion evidence, export, and acknowledgement",
    ),
    BaseShadowAssumption(
        "SA-08",
        "src/giclab/control/production.py",
        "1545-1591",
        "shared production-wrapper defect",
        "finalization used synthetic paths, interpreter, dependency, and completion identities",
        "qualified-local offline finalizer consumes immutable exact raw evidence and receipts",
    ),
    BaseShadowAssumption(
        "SA-09",
        "src/giclab/control/production.py",
        "82-89, 1593-1651",
        "shared production-wrapper defect",
        "the evaluator replaced condition output with canned Task A and Task B answers",
        "the evaluator consumes the effect-produced finalized session",
    ),
    BaseShadowAssumption(
        "SA-10",
        "src/giclab/control/production.py",
        "38, 148-286, 568, 979-1025, 1743-1785",
        "shared production-wrapper defect",
        "the production object required FakeScenario and branched on scenario names",
        "fault injection and deterministic values live only in shadow_effects",
    ),
    BaseShadowAssumption(
        "SA-11",
        "src/giclab/control/adapters.py",
        "25-74",
        "shared production-wrapper defect",
        "effect authority bound no exact package, proof, effect source, root, or external grant",
        "one full EffectAuthorizationContext is validated before assembly and invocation",
    ),
    BaseShadowAssumption(
        "SA-12",
        "src/giclab/control/production.py",
        "75-76, 249, 286-382, 614",
        "shared production-wrapper defect",
        "synthetic network, response, browser, image, and provider fixtures lived in shared source",
        "all deterministic fixture data is confined below the effect boundary",
    ),
)


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _line_column(source: str, offset: int) -> tuple[int, int]:
    line = source.count("\n", 0, offset) + 1
    previous = source.rfind("\n", 0, offset)
    return line, offset - previous


def _literal_cap_findings(source: str, *, relative_path: str) -> list[AntiShadowFinding]:
    findings: list[AntiShadowFinding] = []
    tree = ast.parse(source, filename=relative_path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        name = (
            function.id
            if isinstance(function, ast.Name)
            else function.attr
            if isinstance(function, ast.Attribute)
            else None
        )
        if name != "ProviderBudgetCaps":
            continue
        literal_keywords = [
            keyword.arg
            for keyword in node.keywords
            if keyword.arg is not None and isinstance(keyword.value, ast.Constant)
        ]
        if literal_keywords:
            findings.append(
                AntiShadowFinding(
                    path=relative_path,
                    line=node.lineno,
                    column=node.col_offset + 1,
                    code="T09S011",
                    message=(
                        "shared production constructs literal budget caps instead of loading "
                        "the selected package: " + ", ".join(sorted(literal_keywords))
                    ),
                )
            )
    return findings


def lint_effect_neutral_source(
    source: str,
    *,
    relative_path: str,
) -> tuple[AntiShadowFinding, ...]:
    """Lint one shared module for fixture literals and hard-coded budget caps."""

    findings: list[AntiShadowFinding] = []
    for code, pattern, message in _FORBIDDEN_TEXT:
        for match in pattern.finditer(source):
            line, column = _line_column(source, match.start())
            findings.append(
                AntiShadowFinding(
                    path=relative_path,
                    line=line,
                    column=column,
                    code=code,
                    message=message,
                )
            )
    findings.extend(_literal_cap_findings(source, relative_path=relative_path))
    return tuple(sorted(findings, key=lambda item: (item.line, item.column, item.code)))


def _classification(relative: str) -> str:
    if relative.startswith("tests/"):
        return "historical test fixture"
    if relative in {
        "src/giclab/control/shadow.py",
        "src/giclab/control/shadow_effects.py",
    }:
        return "legitimate deterministic effect fixture"
    if relative.startswith("docs/") or relative.startswith("control/incidents/"):
        return "documentation"
    if relative in SHARED_EFFECT_NEUTRAL_SOURCES:
        return "shared production-wrapper defect"
    return "historical test fixture"


def _inventory(repository: Path) -> tuple[ShadowAssumptionOccurrence, ...]:
    occurrences: list[ShadowAssumptionOccurrence] = []
    paths = sorted(
        {
            path
            for relative_root in INVENTORY_ROOTS
            for path in (repository / relative_root).rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and path.suffix.casefold() in INVENTORY_SUFFIXES
        }
    )
    for path in paths:
        relative = path.relative_to(repository).as_posix()
        if relative == LINT_DEFINITION_PATH:
            continue
        source = path.read_text(encoding="utf-8")
        for pattern in _INVENTORY_TEXT:
            for match in pattern.finditer(source):
                line, _column = _line_column(source, match.start())
                occurrences.append(
                    ShadowAssumptionOccurrence(
                        relative,
                        line,
                        match.group(0),
                        _classification(relative),
                    )
                )
    return tuple(
        sorted(
            occurrences,
            key=lambda item: (item.path, item.line, item.token),
        )
    )


def validate_anti_shadow_lint(repository: Path) -> dict[str, object]:
    """Return a deterministic receipt for the exact effect-neutral source set."""

    root = repository.resolve(strict=True)
    findings: list[AntiShadowFinding] = []
    scanned: list[str] = []
    for relative in SHARED_EFFECT_NEUTRAL_SOURCES:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            findings.append(
                AntiShadowFinding(
                    path=relative,
                    line=1,
                    column=1,
                    code="T09S000",
                    message="effect-neutral source is unavailable",
                )
            )
            continue
        scanned.append(relative)
        findings.extend(
            lint_effect_neutral_source(
                path.read_text(encoding="utf-8"),
                relative_path=relative,
            )
        )
    inventory = _inventory(root)
    counts = Counter(item.classification for item in inventory)
    commit, tree = repository_identity(root)
    document: dict[str, object] = {
        "schema_version": ANTI_SHADOW_LINT_SCHEMA_VERSION,
        "repository_commit": commit,
        "repository_tree": tree,
        "audited_base": {
            "commit": AUDITED_BASE_COMMIT,
            "tree": AUDITED_BASE_TREE,
        },
        "base_assumption_inventory": [asdict(item) for item in BASE_SHADOW_ASSUMPTION_INVENTORY],
        "shared_effect_neutral_sources": scanned,
        "lint_definition_path": LINT_DEFINITION_PATH,
        "forbidden_rule_codes": [code for code, _pattern, _message in _FORBIDDEN_TEXT]
        + ["T09S011"],
        "findings": [asdict(item) for item in findings],
        "assumption_inventory": [asdict(item) for item in inventory],
        "classification_counts": {
            classification: counts.get(classification, 0)
            for classification in (
                "legitimate deterministic effect fixture",
                "shared production-wrapper defect",
                "historical test fixture",
                "documentation",
            )
        },
        "complete": not findings,
    }
    document["semantic_sha256"] = _canonical_sha256(document)
    return document


__all__ = [
    "ANTI_SHADOW_LINT_SCHEMA_VERSION",
    "BASE_SHADOW_ASSUMPTION_INVENTORY",
    "SHARED_EFFECT_NEUTRAL_SOURCES",
    "lint_effect_neutral_source",
    "validate_anti_shadow_lint",
]
