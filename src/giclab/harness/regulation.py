"""Typed, source-neutral regulation-decision evidence contracts."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Any, cast

from .models import EventInputValue, EventProvenance
from .safety import contains_recognizable_secret


class RegulationSourceKind(StrEnum):
    """Evidence-backed source of a reasoning-control decision."""

    EXPERIMENT_ASSIGNMENT = "experiment_assignment"
    EXTERNAL_RULE = "external_rule"
    EXTERNAL_PROMPTED_MODEL = "external_prompted_model"
    MODEL_EXPLICIT_OUTPUT = "model_explicit_output"
    HUMAN_OVERRIDE = "human_override"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RegulationOverride:
    """Observed override state, or an all-null unavailable record."""

    applied: bool | None = None
    source: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.applied is not None and type(self.applied) is not bool:
            raise ValueError("regulation override applied must be a boolean or null")
        _validate_optional_text(self.source, "regulation override source")
        _validate_optional_text(self.reason, "regulation override reason")
        if self.applied is not True and (self.source is not None or self.reason is not None):
            raise ValueError("override details require applied=true")
        if self.applied is True and self.source is None:
            raise ValueError("an applied override requires its source")


@dataclass(frozen=True, slots=True)
class RegulationFallback:
    """Observed fallback state, or an all-null unavailable record."""

    triggered: bool | None = None
    target: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.triggered is not None and type(self.triggered) is not bool:
            raise ValueError("regulation fallback triggered must be a boolean or null")
        _validate_optional_text(self.target, "regulation fallback target")
        _validate_optional_text(self.reason, "regulation fallback reason")
        if self.triggered is not True and (self.target is not None or self.reason is not None):
            raise ValueError("fallback details require triggered=true")
        if self.triggered is True and self.target is None:
            raise ValueError("a triggered fallback requires its target")


REGULATION_FIELD_NAMES = (
    "decision_id",
    "source_kind",
    "policy_id",
    "policy_revision",
    "available_modes",
    "selected_mode",
    "confidence",
    "override",
    "fallback",
    "input_event_sequences",
    "raw_artifact_refs",
    "resolved_configuration_refs",
)


@dataclass(frozen=True, slots=True)
class RegulationDecision:
    """One explicit decision plus field-level evidence provenance."""

    decision_id: str
    source_kind: RegulationSourceKind
    selected_mode: str
    policy_id: str | None = None
    policy_revision: str | None = None
    available_modes: tuple[str, ...] | None = None
    confidence: float | None = None
    override: RegulationOverride = field(default_factory=RegulationOverride)
    fallback: RegulationFallback = field(default_factory=RegulationFallback)
    input_event_sequences: tuple[int, ...] = ()
    raw_artifact_refs: tuple[str, ...] = ()
    resolved_configuration_refs: tuple[str, ...] = ()
    field_provenance: Mapping[str, EventProvenance] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_text(self.decision_id, "regulation decision_id")
        if not isinstance(self.source_kind, RegulationSourceKind):
            raise ValueError("regulation source_kind must use the declared vocabulary")
        _validate_text(self.selected_mode, "regulation selected_mode")
        _validate_optional_text(self.policy_id, "regulation policy_id")
        _validate_optional_text(self.policy_revision, "regulation policy_revision")
        if self.available_modes is not None:
            modes = _validated_unique_texts(self.available_modes, "regulation available_modes")
            if self.selected_mode not in modes:
                raise ValueError("selected_mode must be one of the available_modes when known")
            object.__setattr__(self, "available_modes", modes)
        if self.confidence is not None:
            if isinstance(self.confidence, bool) or not isinstance(self.confidence, int | float):
                raise ValueError("regulation confidence must be a number or null")
            confidence = float(self.confidence)
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError("regulation confidence must be between zero and one")
            object.__setattr__(self, "confidence", confidence)
        if not isinstance(self.override, RegulationOverride):
            raise ValueError("regulation override must be typed")
        if not isinstance(self.fallback, RegulationFallback):
            raise ValueError("regulation fallback must be typed")
        sequences = tuple(self.input_event_sequences)
        if any(type(value) is not int or value < 1 for value in sequences):
            raise ValueError("input_event_sequences must contain positive integers")
        if len(set(sequences)) != len(sequences):
            raise ValueError("input_event_sequences must be unique")
        object.__setattr__(self, "input_event_sequences", sequences)
        raw_refs = _validated_references(self.raw_artifact_refs, "raw_artifact_refs")
        config_refs = _validated_references(
            self.resolved_configuration_refs,
            "resolved_configuration_refs",
        )
        if not raw_refs and not config_refs:
            raise ValueError(
                "regulation decision requires raw artifact or resolved configuration evidence"
            )
        object.__setattr__(self, "raw_artifact_refs", raw_refs)
        object.__setattr__(self, "resolved_configuration_refs", config_refs)
        provenance = dict(self.field_provenance)
        expected = set(REGULATION_FIELD_NAMES)
        if provenance.keys() != expected:
            raise ValueError(
                "regulation field_provenance must cover exactly "
                + ", ".join(REGULATION_FIELD_NAMES)
            )
        if any(not isinstance(value, EventProvenance) for value in provenance.values()):
            raise ValueError("regulation field_provenance values must be typed")
        _require_available(provenance, "decision_id")
        _require_available(provenance, "selected_mode")
        if self.source_kind is RegulationSourceKind.UNKNOWN:
            if provenance["source_kind"] is not EventProvenance.UNAVAILABLE:
                raise ValueError("unknown source_kind must have unavailable provenance")
        else:
            _require_available(provenance, "source_kind")
        _require_optional_provenance(provenance, "policy_id", self.policy_id)
        _require_optional_provenance(provenance, "policy_revision", self.policy_revision)
        _require_optional_provenance(provenance, "available_modes", self.available_modes)
        _require_optional_provenance(provenance, "confidence", self.confidence)
        _require_optional_provenance(provenance, "override", self.override.applied)
        _require_optional_provenance(provenance, "fallback", self.fallback.triggered)
        _require_optional_provenance(
            provenance,
            "input_event_sequences",
            sequences if sequences else None,
        )
        _require_optional_provenance(
            provenance,
            "raw_artifact_refs",
            raw_refs if raw_refs else None,
        )
        _require_optional_provenance(
            provenance,
            "resolved_configuration_refs",
            config_refs if config_refs else None,
        )
        object.__setattr__(self, "field_provenance", MappingProxyType(provenance))


def regulation_decision_payload(decision: RegulationDecision) -> dict[str, EventInputValue]:
    """Return the canonical JSON payload for a validated decision."""

    if not isinstance(decision, RegulationDecision):
        raise ValueError("regulation decision payload requires a typed decision")
    return {
        "decision_id": decision.decision_id,
        "source_kind": decision.source_kind.value,
        "policy_id": decision.policy_id,
        "policy_revision": decision.policy_revision,
        "available_modes": (
            list(decision.available_modes) if decision.available_modes is not None else None
        ),
        "selected_mode": decision.selected_mode,
        "confidence": decision.confidence,
        "override": {
            "applied": decision.override.applied,
            "source": decision.override.source,
            "reason": decision.override.reason,
        },
        "fallback": {
            "triggered": decision.fallback.triggered,
            "target": decision.fallback.target,
            "reason": decision.fallback.reason,
        },
        "input_event_sequences": list(decision.input_event_sequences),
        "raw_artifact_refs": list(decision.raw_artifact_refs),
        "resolved_configuration_refs": list(decision.resolved_configuration_refs),
        "field_provenance": {
            name: decision.field_provenance[name].value for name in REGULATION_FIELD_NAMES
        },
    }


def regulation_decision_from_mapping(value: Mapping[str, Any]) -> RegulationDecision:
    """Strictly parse a regulation payload without accepting interpretive extensions."""

    expected = {*REGULATION_FIELD_NAMES, "field_provenance"}
    if value.keys() != expected:
        unknown = sorted(value.keys() - expected)
        missing = sorted(expected - value.keys())
        raise ValueError(f"regulation decision has missing={missing} unknown={unknown}")
    source_kind_value = value["source_kind"]
    if not isinstance(source_kind_value, str):
        raise ValueError("regulation source_kind must be a string")
    try:
        source_kind = RegulationSourceKind(source_kind_value)
    except ValueError as exc:
        raise ValueError("unsupported regulation source_kind") from exc
    override = _override_from_mapping(value["override"])
    fallback = _fallback_from_mapping(value["fallback"])
    field_provenance_value = value["field_provenance"]
    if not isinstance(field_provenance_value, Mapping):
        raise ValueError("regulation field_provenance must be an object")
    field_provenance: dict[str, EventProvenance] = {}
    for name, provenance_value in field_provenance_value.items():
        if not isinstance(name, str) or not isinstance(provenance_value, str):
            raise ValueError("regulation field_provenance must map strings to strings")
        try:
            field_provenance[name] = EventProvenance(provenance_value)
        except ValueError as exc:
            raise ValueError("unsupported regulation field provenance") from exc
    return RegulationDecision(
        decision_id=_required_string(value["decision_id"], "regulation decision_id"),
        source_kind=source_kind,
        selected_mode=_required_string(value["selected_mode"], "regulation selected_mode"),
        policy_id=_optional_string(value["policy_id"], "regulation policy_id"),
        policy_revision=_optional_string(
            value["policy_revision"],
            "regulation policy_revision",
        ),
        available_modes=_optional_string_tuple(
            value["available_modes"],
            "regulation available_modes",
        ),
        confidence=_optional_number(value["confidence"], "regulation confidence"),
        override=override,
        fallback=fallback,
        input_event_sequences=_integer_tuple(
            value["input_event_sequences"],
            "input_event_sequences",
        ),
        raw_artifact_refs=_string_tuple(value["raw_artifact_refs"], "raw_artifact_refs"),
        resolved_configuration_refs=_string_tuple(
            value["resolved_configuration_refs"],
            "resolved_configuration_refs",
        ),
        field_provenance=field_provenance,
    )


def _validate_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    if "\0" in value or contains_recognizable_secret(value):
        raise ValueError(f"{label} contains unsafe material")


def _validate_optional_text(value: str | None, label: str) -> None:
    if value is not None:
        _validate_text(value, label)


def _validated_unique_texts(values: Sequence[str], label: str) -> tuple[str, ...]:
    result = tuple(values)
    if not result:
        raise ValueError(f"{label} must be nonempty when available")
    for value in result:
        _validate_text(value, label)
    if len(set(result)) != len(result):
        raise ValueError(f"{label} must contain unique values")
    return result


def _validated_references(values: Sequence[str], label: str) -> tuple[str, ...]:
    refs = tuple(values)
    for value in refs:
        _validate_text(value, label)
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError(f"{label} must contain relative traversal-free paths")
    if len(set(refs)) != len(refs):
        raise ValueError(f"{label} must contain unique paths")
    return refs


def _require_available(provenance: Mapping[str, EventProvenance], name: str) -> None:
    if provenance[name] is EventProvenance.UNAVAILABLE:
        raise ValueError(f"available regulation field {name} cannot have unavailable provenance")


def _require_optional_provenance(
    provenance: Mapping[str, EventProvenance],
    name: str,
    value: object | None,
) -> None:
    if value is None:
        if provenance[name] is not EventProvenance.UNAVAILABLE:
            raise ValueError(f"missing regulation field {name} must be unavailable")
    else:
        _require_available(provenance, name)


def _required_string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    return value


def _optional_string(value: object, label: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise ValueError(f"{label} must be a string or null")


def _optional_number(value: object, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a number or null")
    return float(value)


def _sequence(value: object, label: str) -> Sequence[object]:
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise ValueError(f"{label} must be an array")
    return value


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    items = _sequence(value, label)
    if any(not isinstance(item, str) for item in items):
        raise ValueError(f"{label} must contain strings")
    return tuple(cast(Sequence[str], items))


def _optional_string_tuple(value: object, label: str) -> tuple[str, ...] | None:
    if value is None:
        return None
    return _string_tuple(value, label)


def _integer_tuple(value: object, label: str) -> tuple[int, ...]:
    items = _sequence(value, label)
    if any(type(item) is not int for item in items):
        raise ValueError(f"{label} must contain integers")
    return tuple(cast(Sequence[int], items))


def _override_from_mapping(value: object) -> RegulationOverride:
    if not isinstance(value, Mapping):
        raise ValueError("regulation override must be an object")
    expected = {"applied", "source", "reason"}
    if value.keys() != expected:
        raise ValueError("regulation override has missing or unknown fields")
    applied = value["applied"]
    if applied is not None and type(applied) is not bool:
        raise ValueError("regulation override applied must be a boolean or null")
    return RegulationOverride(
        applied=applied,
        source=_optional_string(value["source"], "regulation override source"),
        reason=_optional_string(value["reason"], "regulation override reason"),
    )


def _fallback_from_mapping(value: object) -> RegulationFallback:
    if not isinstance(value, Mapping):
        raise ValueError("regulation fallback must be an object")
    expected = {"triggered", "target", "reason"}
    if value.keys() != expected:
        raise ValueError("regulation fallback has missing or unknown fields")
    triggered = value["triggered"]
    if triggered is not None and type(triggered) is not bool:
        raise ValueError("regulation fallback triggered must be a boolean or null")
    return RegulationFallback(
        triggered=triggered,
        target=_optional_string(value["target"], "regulation fallback target"),
        reason=_optional_string(value["reason"], "regulation fallback reason"),
    )


__all__ = [
    "REGULATION_FIELD_NAMES",
    "RegulationDecision",
    "RegulationFallback",
    "RegulationOverride",
    "RegulationSourceKind",
    "regulation_decision_from_mapping",
    "regulation_decision_payload",
]
