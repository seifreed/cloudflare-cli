"""CLI parser for the generated Cloudflare OpenAPI catalog."""

from __future__ import annotations

import argparse
import re
from collections.abc import Callable
from typing import Any

from cloudflare_cli.catalog import operations
from cloudflare_cli.registry import Operation

RequestArguments = Callable[[argparse.ArgumentParser], None]


def add_operation_parsers(
    subparsers: argparse._SubParsersAction[Any],
    groups: dict[str, argparse._SubParsersAction[Any]],
    add_request_arguments: RequestArguments,
) -> None:
    definitions = operations()
    used_commands: dict[str, set[str]] = {
        "accounts": {"configured"},
        "r2": {
            "request",
            "list-buckets",
            "list-objects",
            "get-object",
            "put-object",
            "delete-object",
            "head-object",
        },
    }
    for definition in definitions:
        group = _operation_group(definition)
        group_commands = groups.get(group)
        if group_commands is None:
            group_parser = subparsers.add_parser(
                group,
                help=f"{group.replace('-', ' ').title()} API endpoints",
            )
            group_commands = group_parser.add_subparsers(
                dest=f"{group.replace('-', '_')}_command", required=True
            )
            groups[group] = group_commands
        group_commands_used = used_commands.setdefault(group, set())
        command = _unique_command(
            _operation_command(definition), definition.method, group_commands_used
        )
        group_commands_used.add(command)
        _add_operation_parser(
            group_commands, definition, command, add_request_arguments
        )


def _add_operation_parser(
    parent: argparse._SubParsersAction[Any],
    definition: Operation,
    command: str,
    add_request_arguments: RequestArguments,
) -> None:
    operation_parser = parent.add_parser(
        command,
        help=_operation_help(definition),
    )
    add_request_arguments(operation_parser)
    parameter_specs = _add_operation_parameters(operation_parser, definition)
    operation_parser.set_defaults(
        action="operation",
        operation_id=definition.operation_id,
        operation_parameters=parameter_specs,
    )


def _operation_group(definition: Operation) -> str:
    parts = [part for part in definition.path.strip("/").split("/") if part]
    fixed_parts = [
        part for part in parts if not (part.startswith("{") and part.endswith("}"))
    ]
    if len(fixed_parts) > 1 and re.fullmatch(r"v\d+", fixed_parts[1]):
        source = fixed_parts[2] if len(fixed_parts) > 2 else fixed_parts[0]
    else:
        source = fixed_parts[1] if len(fixed_parts) > 1 else fixed_parts[0]
    return _slug(source)


def _operation_command(definition: Operation) -> str:
    command = _slug(definition.operation_id)
    prefix = f"{_operation_group(definition)}-"
    return command.removeprefix(prefix) or command


def _operation_help(definition: Operation) -> str:
    details = f"{definition.method} {definition.path}"
    return f"{details}: {definition.summary}" if definition.summary else details


def _unique_command(command: str, method: str, used: set[str]) -> str:
    if command not in used:
        return command
    candidate = f"{command}-{method.lower()}"
    suffix = 2
    while candidate in used:
        candidate = f"{command}-{method.lower()}-{suffix}"
        suffix += 1
    return candidate


def _slug(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", value)
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", value)
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "operation"


def _add_operation_parameters(
    parser: argparse.ArgumentParser, definition: Operation
) -> list[tuple[str, str]]:
    used_options = {
        "--account",
        "--base-url",
        "--timeout",
        "--query",
        "--path-param",
        "--header",
        "--data",
        "--data-file",
        "--raw-file",
        "--content-type",
        "--format",
        "--output-file",
    }
    result: list[tuple[str, str]] = []
    for index, parameter in enumerate(definition.parameters):
        slug = _slug(parameter.name)
        option = f"--{slug}"
        if option in used_options:
            option = f"--{parameter.location}-{slug}"
        while option in used_options:
            option = f"{option}-{index}"
        used_options.add(option)
        destination = f"_operation_parameter_{index}"
        action = "append" if parameter.array and not parameter.structured else None
        if action:
            parser.add_argument(option, dest=destination, action=action)
        else:
            parser.add_argument(option, dest=destination)
        result.append((parameter.name, destination))
    return result
