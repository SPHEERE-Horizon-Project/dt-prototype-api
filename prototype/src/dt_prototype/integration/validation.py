"""Reusable, non-destructive validation helpers for canonical records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence, TypeVar


@dataclass(frozen=True)
class ValidationIssue:
    """One machine-readable contract violation."""

    code: str
    field: str
    message: str
    record_key: str = ""


class ContractValidationError(ValueError):
    """Raised when one or more canonical contract violations are present."""

    def __init__(self, issues: Sequence[ValidationIssue]):
        self.issues = tuple(issues)
        summary = "; ".join(
            f"{issue.code}:{issue.field}:{issue.message}" for issue in self.issues
        )
        super().__init__(summary)


class Validatable(Protocol):
    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        """Return all validation issues without mutating the record."""


T = TypeVar("T", bound=Validatable)


def require_valid(record: T) -> T:
    """Return *record* when valid; otherwise raise with all discovered issues."""

    issues = record.validation_issues()
    if issues:
        raise ContractValidationError(issues)
    return record


def validate_all(records: Iterable[Validatable]) -> tuple[ValidationIssue, ...]:
    """Collect issues from a record sequence without failing at the first row."""

    return tuple(issue for record in records for issue in record.validation_issues())


def uniqueness_issues(
    records: Iterable[object], key_fields: Sequence[str], entity_name: str
) -> tuple[ValidationIssue, ...]:
    """Validate compound-key uniqueness before indexing or dictionary creation."""

    seen: dict[tuple[object, ...], int] = {}
    issues: list[ValidationIssue] = []
    for position, record in enumerate(records):
        key = tuple(getattr(record, field) for field in key_fields)
        if key in seen:
            rendered = "|".join("" if value is None else str(value) for value in key)
            issues.append(
                ValidationIssue(
                    code="DUPLICATE_KEY",
                    field=",".join(key_fields),
                    message=(
                        f"duplicate {entity_name} key at positions "
                        f"{seen[key]} and {position}"
                    ),
                    record_key=rendered,
                )
            )
        else:
            seen[key] = position
    return tuple(issues)


def require_valid_collection(
    records: Sequence[Validatable], key_fields: Sequence[str], entity_name: str
) -> Sequence[Validatable]:
    """Validate row contracts and uniqueness as one auditable operation."""

    issues = validate_all(records) + uniqueness_issues(records, key_fields, entity_name)
    if issues:
        raise ContractValidationError(issues)
    return records
