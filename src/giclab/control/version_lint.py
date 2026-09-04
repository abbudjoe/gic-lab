"""Reject literal T09 package-version feature dispatch in active runtime code."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

VERSION_LITERAL: Final = re.compile(r"^V[0-9]+$")
VERSIONED_PROVIDER_CONTRACT_SYMBOL: Final = re.compile(r"^V[1-9][0-9]*_PROVIDER_CONTRACT$")
ANNOTATION: Final = "giclab-version-lint: historical-identity"
SCAN_ROOTS: Final = (
    "src/giclab",
    "containers/sira-smoke/pragmatic",
)
CENTRAL_PROVIDER_REGISTRY: Final = "src/giclab/harness/t09_provider_contracts.py"
ACTIVE_CONTRACT_SELECTION_ROOT: Final = "src/giclab/control/"
ACTIVE_SELECTION_TEXT_PATHS: Final = ("Makefile", ".github/workflows/ci.yml")
_FIXED_SELECTOR: Final = re.compile(r"--provider-contract(?:=|\s+)[\"']?(V[0-9]+)\b")
_FIXED_RECEIPT_ROOT: Final = re.compile(r"control/receipts/packages/v[1-9][0-9]*")


@dataclass(frozen=True, slots=True)
class VersionDispatchFinding:
    path: str
    line: int
    column: int
    code: str
    message: str


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _git_identity(repository: Path) -> tuple[str, str]:
    environment = {
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    values: list[str] = []
    for revision in ("HEAD", "HEAD^{tree}"):
        completed = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", revision],
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=10,
        )
        value = completed.stdout.decode("ascii", "ignore").strip()
        values.append(value if completed.returncode == 0 and len(value) == 40 else "unknown")
    return values[0], values[1]


def _literal_versions(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (node.value,) if VERSION_LITERAL.fullmatch(node.value) else ()
    if isinstance(node, (ast.Set, ast.Tuple, ast.List)):
        values: list[str] = []
        for item in node.elts:
            values.extend(_literal_versions(item))
        return tuple(values)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"frozenset", "set", "tuple", "list"}
        and len(node.args) == 1
    ):
        return _literal_versions(node.args[0])
    return ()


def _assignment_names(node: ast.Assign | ast.AnnAssign) -> tuple[str, ...]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    names: list[str] = []
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
    return tuple(names)


class _Visitor(ast.NodeVisitor):
    def __init__(self, *, relative: str, lines: list[str]) -> None:
        self.relative = relative
        self.lines = lines
        self.findings: list[VersionDispatchFinding] = []
        self.assert_depth = 0
        self.versioned_contract_aliases: set[str] = set()

    def _scans_versioned_contract_symbols(self) -> bool:
        return self.relative.startswith(ACTIVE_CONTRACT_SELECTION_ROOT)

    def _annotated(self, node: ast.AST) -> bool:
        line = getattr(node, "lineno", 0)
        if not 1 <= line <= len(self.lines):
            return False
        return any(ANNOTATION in candidate for candidate in self.lines[max(0, line - 2) : line])

    def _add(self, node: ast.AST, *, code: str, message: str) -> None:
        self.findings.append(
            VersionDispatchFinding(
                path=self.relative,
                line=getattr(node, "lineno", 1),
                column=getattr(node, "col_offset", 0) + 1,
                code=code,
                message=message,
            )
        )

    def visit_Assert(self, node: ast.Assert) -> None:
        self.assert_depth += 1
        self.visit(node.test)
        if node.msg is not None:
            self.visit(node.msg)
        self.assert_depth -= 1

    def visit_Compare(self, node: ast.Compare) -> None:
        versions = _literal_versions(node.left)
        for comparator in node.comparators:
            versions += _literal_versions(comparator)
        if versions and self.assert_depth == 0 and not self._annotated(node):
            operators = tuple(type(operator) for operator in node.ops)
            code = (
                "T09V002"
                if any(operator in {ast.Lt, ast.LtE, ast.Gt, ast.GtE} for operator in operators)
                else "T09V001"
            )
            self._add(
                node,
                code=code,
                message=(
                    "active behavior compares a literal package version; dispatch through "
                    "T09ContractCapabilities"
                ),
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        function_name = None
        if isinstance(node.func, ast.Name):
            function_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            function_name = node.func.attr
        positional_selector = node.args[0] if node.args else None
        keyword_selector = next(
            (
                keyword.value
                for keyword in node.keywords
                if keyword.arg in {"version", "provider_contract"}
            ),
            None,
        )
        selector = positional_selector or keyword_selector
        if (
            function_name == "provider_contract"
            and selector is not None
            and _literal_versions(selector)
        ):
            self._add(
                node,
                code="T09V004",
                message=(
                    "active code selects a literal provider contract; resolve the "
                    "goal-compatible SelectedRuntimeTarget"
                ),
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self._scans_versioned_contract_symbols():
            for alias in node.names:
                if VERSIONED_PROVIDER_CONTRACT_SYMBOL.fullmatch(alias.name):
                    self.versioned_contract_aliases.add(alias.asname or alias.name)
                    if not self._annotated(node):
                        self._add(
                            node,
                            code="T09V007",
                            message=(
                                "active code imports a version-specific provider-contract "
                                "constant; resolve the goal-compatible SelectedRuntimeTarget"
                            ),
                        )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if (
            self._scans_versioned_contract_symbols()
            and isinstance(node.ctx, ast.Load)
            and (
                VERSIONED_PROVIDER_CONTRACT_SYMBOL.fullmatch(node.id)
                or node.id in self.versioned_contract_aliases
            )
            and not (self.assert_depth > 0 and self._annotated(node))
        ):
            self._add(
                node,
                code="T09V008",
                message=(
                    "active code uses a version-specific provider-contract constant; "
                    "resolve the goal-compatible SelectedRuntimeTarget"
                ),
            )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if (
            self._scans_versioned_contract_symbols()
            and isinstance(node.ctx, ast.Load)
            and VERSIONED_PROVIDER_CONTRACT_SYMBOL.fullmatch(node.attr)
            and not (self.assert_depth > 0 and self._annotated(node))
        ):
            self._add(
                node,
                code="T09V008",
                message=(
                    "active code uses a version-specific provider-contract constant; "
                    "resolve the goal-compatible SelectedRuntimeTarget"
                ),
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self._visit_assignment(node, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self._visit_assignment(node, node.value)

    def _visit_assignment(self, node: ast.Assign | ast.AnnAssign, value: ast.AST) -> None:
        names = _assignment_names(node)
        versions = _literal_versions(value)
        if (
            versions
            and any("VERSION" in name.upper() for name in names)
            and not self._annotated(node)
        ):
            self._add(
                node,
                code="T09V003",
                message="active version constants must be semantic capability declarations",
            )
        self.generic_visit(node)


def lint_source(source: str, *, relative_path: str) -> tuple[VersionDispatchFinding, ...]:
    """Lint one Python source string for prohibited package-version dispatch."""

    tree = ast.parse(source, filename=relative_path)
    visitor = _Visitor(relative=relative_path, lines=source.splitlines())
    visitor.visit(tree)
    findings = list(visitor.findings)
    for matched in _FIXED_RECEIPT_ROOT.finditer(source):
        line = source.count("\n", 0, matched.start()) + 1
        previous = source.rfind("\n", 0, matched.start())
        findings.append(
            VersionDispatchFinding(
                path=relative_path,
                line=line,
                column=matched.start() - previous,
                code="T09V009",
                message=(
                    "active shared source selects a literal package receipt root; "
                    "derive it from SelectedRuntimeTarget"
                ),
            )
        )
    return tuple(findings)


def lint_active_selection_text(
    source: str,
    *,
    relative_path: str,
) -> tuple[VersionDispatchFinding, ...]:
    """Reject a literal provider selector in aggregate Make/CI command text."""

    findings: list[VersionDispatchFinding] = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        matched = _FIXED_SELECTOR.search(line)
        if matched is not None:
            findings.append(
                VersionDispatchFinding(
                    path=relative_path,
                    line=line_number,
                    column=matched.start() + 1,
                    code="T09V005",
                    message=(
                        "aggregate command selects a literal provider contract; "
                        "use goal-compatible target resolution"
                    ),
                )
            )
        for receipt_root in _FIXED_RECEIPT_ROOT.finditer(line):
            findings.append(
                VersionDispatchFinding(
                    path=relative_path,
                    line=line_number,
                    column=receipt_root.start() + 1,
                    code="T09V009",
                    message=(
                        "active aggregate command selects a literal package receipt root; "
                        "derive it from SelectedRuntimeTarget"
                    ),
                )
            )
    return tuple(findings)


def validate_active_version_dispatch(repository: Path) -> dict[str, object]:
    """Scan the complete active Python surface and return a deterministic receipt."""

    root = repository.resolve(strict=True)
    files = sorted(
        path
        for relative_root in SCAN_ROOTS
        for path in (root / relative_root).rglob("*.py")
        if path.is_file()
    )
    findings: list[VersionDispatchFinding] = []
    scanned: list[str] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        scanned.append(relative)
        findings.extend(lint_source(path.read_text(encoding="utf-8"), relative_path=relative))
    for relative in ACTIVE_SELECTION_TEXT_PATHS:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            findings.append(
                VersionDispatchFinding(
                    path=relative,
                    line=1,
                    column=1,
                    code="T09V006",
                    message="aggregate selection surface is unavailable",
                )
            )
            continue
        scanned.append(relative)
        findings.extend(
            lint_active_selection_text(
                path.read_text(encoding="utf-8"),
                relative_path=relative,
            )
        )
    commit, tree = _git_identity(root)
    projection: dict[str, object] = {
        "schema_version": "1.0.0",
        "repository_commit": commit,
        "repository_tree": tree,
        "scan_roots": list(SCAN_ROOTS),
        "files_scanned": scanned,
        "historical_module_allowlist": [],
        "findings": [
            asdict(item) for item in sorted(findings, key=lambda item: (item.path, item.line))
        ],
        "complete": not findings,
    }
    projection["semantic_sha256"] = _canonical_sha256(projection)
    return projection
