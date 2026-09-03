"""Packaged Cloudflare API operation registry."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    location: str
    required: bool
    explode: bool | None = None
    array: bool = False
    structured: bool = False
    mapping: bool = False


@dataclass(frozen=True, slots=True)
class Operation:
    operation_id: str
    method: str
    path: str
    summary: str
    parameters: tuple[Parameter, ...]
    request_body: bool
    request_body_required: bool


def method_name(operation_id: str) -> str:
    name = re.sub(r"[^0-9A-Za-z_]", "_", operation_id)
    return f"_{name}" if name[:1].isdigit() else name
