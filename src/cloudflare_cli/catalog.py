"""Packaged Cloudflare API operation catalog."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

from cloudflare_cli.registry import Operation, Parameter, method_name


class PackagedOperationCatalog:
    """Operation catalog backed by the packaged registry document."""

    def operation(self, operation_id: str) -> Operation:
        return operation(operation_id)

    def operation_methods(self) -> MappingProxyType[str, str]:
        return operation_methods()


@lru_cache(maxsize=1)
def operations() -> tuple[Operation, ...]:
    path = Path(__file__).with_name("registry.json")
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        Operation(
            operation_id=item["operation_id"],
            method=item["method"],
            path=item["path"],
            summary=item["summary"],
            parameters=_complete_parameters(item),
            request_body=item["request_body"],
            request_body_required=item["request_body_required"],
        )
        for item in document["operations"]
    )


def _complete_parameters(item: dict[str, Any]) -> tuple[Parameter, ...]:
    parameters = tuple(
        Parameter(
            parameter["name"],
            parameter["in"],
            parameter["required"],
            parameter.get("explode"),
            parameter.get("array", False),
            parameter.get("structured", False),
            parameter.get("mapping", False),
        )
        for parameter in item["parameters"]
    )
    known_path_parameters = {
        parameter.name for parameter in parameters if parameter.location == "path"
    }
    return parameters + tuple(
        Parameter(name, "path", True)
        for name in dict.fromkeys(re.findall(r"{([^}]+)}", item["path"]))
        if name not in known_path_parameters
    )


def operation(operation_id: str) -> Operation:
    try:
        return _operation_index()[operation_id]
    except KeyError as error:
        raise ValueError(f"Unknown Cloudflare operation {operation_id!r}") from error


@lru_cache(maxsize=1)
def _operation_index() -> MappingProxyType[str, Operation]:
    return MappingProxyType({item.operation_id: item for item in operations()})


@lru_cache(maxsize=1)
def operation_methods() -> MappingProxyType[str, str]:
    return MappingProxyType(
        {method_name(item.operation_id): item.operation_id for item in operations()}
    )
