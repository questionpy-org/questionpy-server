import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal, Protocol, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from questionpy_common.constants import RE_SEMVER

type _Operator = Literal["==", "!=", ">=", "<=", ">", "<", "^="]
_OPERATORS: tuple[_Operator, ...] = ("==", "!=", ">=", "<=", ">", "<", "^=")

_SEMVER_PATTERN = re.compile(RE_SEMVER)


class VersionProtocol(Protocol):
    """Partial protocol for SemVer version objects.

    We don't want `questionpy_common` to depend on the `semver` package, so we define this protocol instead of using
    `semver.Version` directly.
    """

    @staticmethod
    def parse(string: str) -> "VersionProtocol": ...

    def is_compatible(self, other: Self) -> bool: ...

    def __gt__(self, other: Self) -> bool: ...

    def __ge__(self, other: Self) -> bool: ...

    def __lt__(self, other: Self) -> bool: ...

    def __le__(self, other: Self) -> bool: ...


@dataclass(frozen=True)
class QPyDependencyVersionSpecifier:
    """One or more clauses restricting allowed versions for a QPy package dependency."""

    @dataclass(frozen=True)
    class Clause:
        """A single comparison clause such as `>= 1.2.2`."""

        operator: _Operator
        operand: str

        def __post_init__(self) -> None:
            if self.operator == "^=" and "-" in self.operand:
                # Prereleases are never compatible with different prereleases, so this would make little sense.
                msg = "The '^=' operator cannot be used with prereleases."
                raise ValueError(msg)

        def allows(self, version: VersionProtocol) -> bool:
            """Check if this clause is fulfilled by the given version."""
            # Note: The semver package we use does already implement a `match` method, but we would like to validate
            # each clause early, before the matching needs to be done.
            parsed_operand = type(version).parse(self.operand)
            match self.operator:
                case "<":
                    return version < parsed_operand
                case "<=":
                    return version <= parsed_operand
                case "==":
                    return version == parsed_operand
                case ">=":
                    return version >= parsed_operand
                case ">":
                    return version > parsed_operand
                case "^=":
                    return parsed_operand.is_compatible(version)
                case _:
                    # Shouldn't be reachable.
                    msg = f"Invalid operator: {self.operator}"
                    raise ValueError(msg)

        @classmethod
        def from_string(cls, string: str) -> Self:
            string = string.strip()

            operator = next(filter(string.startswith, _OPERATORS), None)
            if operator:
                version_string = string.removeprefix(operator).lstrip()
                if not _SEMVER_PATTERN.match(version_string):
                    msg = f"Comparison version '{version_string}' of clause '{string}' does not conform to SemVer."
                    raise ValueError(msg)

                operand = version_string
            else:
                # No operator. Check if string is a version, since we allow "==" to be omitted.
                if not _SEMVER_PATTERN.match(string):
                    msg = (
                        f"Version specifier clause '{string}' does not start with a valid operator and isn't a "
                        f"version itself. Valid operators are {', '.join(_OPERATORS)}."
                    )
                    raise ValueError(msg)

                operator = "=="
                operand = string

            return cls(operator, operand)

        def __str__(self) -> str:
            return f"{self.operator} {self.operand}"

    # Dict because we want to preserve order (for readability) but not compare order or allow dupes.
    _clauses: dict[Clause, None]

    def __init__(self, clauses: Iterable[Clause]) -> None:
        super().__setattr__("_clauses", dict.fromkeys(clauses))

    @property
    def clauses(self) -> tuple[Clause, ...]:
        return tuple(self._clauses)

    def __str__(self) -> str:
        return ", ".join(map(str, self._clauses))

    @classmethod
    def from_string(cls, string: str) -> Self:
        return cls(
            tuple(cls.Clause.from_string(clause) for clause in string.split(",") if string and not string.isspace())
        )

    def allows(self, version: VersionProtocol) -> bool:
        """Checks if _all_ clauses allow the given version."""
        return all(clause.allows(version) for clause in self._clauses)

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.json_or_python_schema(
            core_schema.no_info_after_validator_function(cls.from_string, handler(str)),
            core_schema.is_instance_schema(cls),
            serialization=core_schema.to_string_ser_schema(),
        )
