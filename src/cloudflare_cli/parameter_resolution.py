"""Pure OpenAPI parameter resolution for Cloudflare operations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from cloudflare_cli.registry import Operation, Parameter


def resolve_parameters(
    definition: Operation,
    account_id: str | None,
    query: Mapping[str, Any] | None,
    path_params: Mapping[str, str] | None,
    headers: Mapping[str, str] | None,
    provided: dict[str, Any],
) -> tuple[dict[str, str], dict[str, Any], dict[str, str]]:
    path_values = dict(path_params or {})
    query_values = dict(query or {})
    header_values = dict(headers or {})
    remaining = dict(provided)
    for parameter in definition.parameters:
        if parameter.name not in remaining:
            continue
        value = remaining.pop(parameter.name)
        if value is None:
            continue
        if parameter.location == "path":
            path_values[parameter.name] = str(value)
        elif parameter.location == "query":
            _set_query_parameter(query_values, parameter, value)
        elif parameter.location == "header":
            header_values[parameter.name] = str(value)
    for parameter in definition.parameters:
        if parameter.location == "query" and parameter.name in query_values:
            _set_query_parameter(query_values, parameter, query_values[parameter.name])
        if parameter.required and not _has_parameter(
            parameter, path_values, query_values, header_values
        ):
            if _is_account_id(parameter.name) and account_id:
                path_values[parameter.name] = account_id
            else:
                raise ValueError(
                    f"Missing required {parameter.location} parameter "
                    f"{parameter.name!r}"
                )
    if remaining:
        raise ValueError(f"Unknown parameters: {sorted(remaining)}")
    return path_values, query_values, header_values


def parameter_value(parameter: Parameter, value: Any) -> Any:
    if not isinstance(value, (list, tuple)):
        return value
    values = query_values(value)
    if not values:
        return value
    if len(values) == 1 and isinstance(values[0], str):
        return values[0]
    if parameter.explode is not False:
        return value
    return ",".join(
        str(item).lower() if isinstance(item, bool) else str(item)
        for item in values
        if item is not None
    )


def _set_query_parameter(
    query_values: dict[str, Any], parameter: Parameter, value: Any
) -> None:
    if (
        parameter.mapping
        and isinstance(value, Mapping)
        and parameter.explode is not False
    ):
        query_values.pop(parameter.name, None)
        query_values.update({str(key): item for key, item in value.items()})
    else:
        query_values[parameter.name] = parameter_value(parameter, value)


def query_values(value: Any) -> tuple[Any, ...]:
    if isinstance(value, (list, tuple)):
        if any(isinstance(item, (Mapping, list, tuple)) for item in value):
            return (json.dumps(value, separators=(",", ":")),)
        return tuple(value)
    if isinstance(value, Mapping):
        return (json.dumps(value, separators=(",", ":")),)
    return (value,)


def _has_parameter(
    parameter: Parameter,
    path_values: Mapping[str, str],
    query_values: Mapping[str, Any],
    header_values: Mapping[str, str],
) -> bool:
    values = {
        "path": path_values,
        "query": query_values,
        "header": header_values,
    }
    return (
        parameter.name in values[parameter.location]
        and values[parameter.location][parameter.name] is not None
    )


def _is_account_id(name: str) -> bool:
    return name.lower().replace("_", "") == "accountid"
