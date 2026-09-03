"""CLI input conversion helpers."""

from __future__ import annotations

import json
from argparse import Namespace
from typing import Any


def body_from_args(args: Namespace) -> Any:
    inputs = (args.data, args.data_file, args.raw_file)
    if sum(value is not None for value in inputs) > 1:
        raise ValueError("Use only one of --data, --data-file, or --raw-file")
    if args.raw_file:
        return args.raw_file.read_bytes()
    if args.data_file:
        return json.loads(args.data_file.read_text(encoding="utf-8"))
    return json.loads(args.data) if args.data else None


def query_from_args(values: list[str], *, repeat: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for value in values:
        key, separator, item = value.partition("=")
        if not separator or not key:
            raise ValueError(f"Invalid --query value {value!r}; expected key=value")
        if repeat and key in result:
            previous = result[key]
            result[key] = (
                [*previous, item] if isinstance(previous, list) else [previous, item]
            )
        else:
            result[key] = item
    return result
