"""Minimal dependency-free TOON encoder for API exports."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

_NUMERIC_STRING = re.compile(r"^[+-]?[0-9]+(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?$", re.I)
_UNQUOTED_FIELD = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def encode(value: Any) -> str:
    """Encode JSON-shaped data as deterministic TOON text."""
    lines: list[str] = []
    _encode_value(value, 0, None, lines)
    return "\n".join(lines)


def _encode_value(
    value: Any,
    depth: int,
    key: str | None,
    lines: list[str],
    allow_tabular: bool = True,
) -> None:
    prefix = "  " * depth
    if isinstance(value, Mapping):
        if not value:
            lines.append(f"{prefix}{_field(key)}: {{}}" if key else f"{prefix}{{}}")
            return
        if _uniform_object_map(value):
            _encode_keyed_object(value, depth, key, lines)
            return
        if key is not None:
            lines.append(f"{prefix}{_field(key)}:")
            depth += 1
        for child_key, child_value in value.items():
            _encode_value(child_value, depth, str(child_key), lines)
        return
    if isinstance(value, list):
        _encode_array(value, depth, key, lines, allow_tabular)
        return
    line = (
        f"{prefix}{_field(key)}: {_scalar(value)}"
        if key
        else f"{prefix}{_scalar(value)}"
    )
    lines.append(line)


def _encode_array(
    values: list[Any],
    depth: int,
    key: str | None,
    lines: list[str],
    allow_tabular: bool,
) -> None:
    prefix = "  " * depth
    name = _field(key) if key else ""
    if not values:
        lines.append(f"{prefix}{name}: []" if name else f"{prefix}[]")
    elif all(_is_scalar(item) for item in values):
        rendered = ",".join(_scalar(item) for item in values)
        lines.append(
            f"{prefix}{name}[{len(values)}]: {rendered}"
            if name
            else f"[{len(values)}]: {rendered}"
        )
    elif allow_tabular and _uniform_objects(values):
        fields = list(values[0])
        header_fields = ",".join(_field(str(field)) for field in fields)
        lines.append(
            f"{prefix}{name}[{len(values)}]{{{header_fields}}}:"
            if name
            else f"[{len(values)}]{{{header_fields}}}:"
        )
        for item in values:
            row = ",".join(_scalar(item[field]) for field in fields)
            lines.append(f"{'  ' * (depth + 1)}{row}")
    else:
        lines.append(f"{prefix}{name}[{len(values)}]:" if name else f"[{len(values)}]:")
        for item in values:
            if _is_scalar(item):
                lines.append(f"{'  ' * (depth + 1)}- {_scalar(item)}")
            elif isinstance(item, Mapping):
                _encode_object_item(item, depth + 1, lines)
            elif isinstance(item, list):
                if item:
                    nested: list[str] = []
                    _encode_value(item, depth + 1, None, nested, allow_tabular=False)
                    lines.append(f"{'  ' * (depth + 1)}- {nested.pop(0).lstrip()}")
                    lines.extend(nested)
                else:
                    lines.append(f"{'  ' * (depth + 1)}- [0]:")
            else:
                lines.append(f"{'  ' * (depth + 1)}-")
                _encode_value(item, depth + 2, None, lines)


def _uniform_objects(values: list[Any]) -> bool:
    if not values or any(not isinstance(item, Mapping) or not item for item in values):
        return False
    fields = set(values[0])
    return all(
        set(item) == fields and all(_is_scalar(item[field]) for field in fields)
        for item in values
    )


def _uniform_object_map(value: Mapping[Any, Any]) -> bool:
    return len(value) >= 2 and _uniform_objects(list(value.values()))


def _encode_keyed_object(
    value: Mapping[Any, Any], depth: int, key: str | None, lines: list[str]
) -> None:
    entries = list(value.items())
    fields = list(entries[0][1])
    prefix = "  " * depth
    name = _field(key) if key else ""
    field_names = ",".join(_field(str(field)) for field in fields)
    header = f"{name}[{len(entries)}:]{{{field_names}}}:"
    lines.append(f"{prefix}{header}")
    for entry_key, entry_value in entries:
        row = ",".join(_scalar(entry_value[field]) for field in fields)
        lines.append(f"{'  ' * (depth + 1)}{_field(str(entry_key))}: {row}")


def _encode_object_item(value: Mapping[Any, Any], depth: int, lines: list[str]) -> None:
    prefix = "  " * depth
    if not value:
        lines.append(f"{prefix}-")
        return
    nested: list[str] = []
    first_key, first_value = next(iter(value.items()))
    tabular_first = _is_tabular_value(first_value)
    _encode_value(first_value, depth, str(first_key), nested)
    lines.append(f"{prefix}- {nested.pop(0).lstrip()}")
    if tabular_first:
        lines.extend(f"  {line}" for line in nested)
    else:
        lines.extend(nested)
    for child_key, child_value in list(value.items())[1:]:
        _encode_value(child_value, depth + 1, str(child_key), lines)


def _is_tabular_value(value: Any) -> bool:
    return (isinstance(value, list) and _uniform_objects(value)) or (
        isinstance(value, Mapping) and _uniform_object_map(value)
    )


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return _number(value)
    text = str(value)
    _validate_text(text)
    return (
        text
        if text
        and text not in {"true", "false", "null"}
        and not _NUMERIC_STRING.fullmatch(text)
        and not text.startswith(("-", "#"))
        and text == text.strip(" \t")
        and not any(char in ',:"\\[]{}' or ord(char) < 0x20 for char in text)
        else _quote(text)
    )


def _field(value: str | None) -> str:
    if value is None:
        return ""
    return value if _UNQUOTED_FIELD.fullmatch(value) else _quote(value)


def _number(value: int | float) -> str:
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return "null"
        if value == 0:
            return "0"
        decimal = Decimal(repr(value))
        if 1e-6 <= abs(value) < 1e21:
            rendered = format(decimal, "f")
            return rendered.rstrip("0").rstrip(".")
        mantissa, exponent = repr(value).lower().split("e")
        return f"{mantissa}e{int(exponent):+d}"
    return str(value)


def _quote(value: str) -> str:
    _validate_text(value)
    escaped = ['"']
    for char in value:
        code = ord(char)
        if char == "\\":
            escaped.append("\\\\")
        elif char == '"':
            escaped.append('\\"')
        elif char == "\n":
            escaped.append("\\n")
        elif char == "\r":
            escaped.append("\\r")
        elif char == "\t":
            escaped.append("\\t")
        elif code < 0x20:
            escaped.append(f"\\u{code:04x}")
        else:
            escaped.append(char)
    escaped.append('"')
    return "".join(escaped)


def _validate_text(value: str) -> None:
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError("TOON cannot encode a lone surrogate")
