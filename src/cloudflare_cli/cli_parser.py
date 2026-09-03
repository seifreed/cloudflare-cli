"""Argument parser for the Cloudflare command-line adapter."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from cloudflare_cli.cli_catalog import add_operation_parsers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cloudflare")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--account")
    parser.add_argument("--base-url")
    parser.add_argument("--timeout", type=float, default=30.0)
    subparsers = parser.add_subparsers(dest="command", required=True)

    accounts = subparsers.add_parser("accounts")
    accounts.set_defaults(action="accounts", format="json")
    account_commands = accounts.add_subparsers(dest="accounts_command")
    configured = account_commands.add_parser(
        "configured", help="List configured accounts"
    )
    configured.set_defaults(action="accounts", format="json")

    operation_list = subparsers.add_parser("operations")
    operation_list.add_argument("--format", choices=("json", "toon"), default="json")
    operation_list.set_defaults(action="operations")

    request = subparsers.add_parser("request")
    request.add_argument("method")
    request.add_argument("path")
    _add_request_arguments(request)
    request.set_defaults(action="request")
    groups = {"accounts": account_commands}
    groups.update(_add_r2_parser(subparsers))
    add_operation_parsers(subparsers, groups, _add_request_arguments)
    return parser


def _add_request_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--account", default=argparse.SUPPRESS)
    parser.add_argument("--base-url", default=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=float, default=argparse.SUPPRESS)
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--path-param", action="append", default=[])
    parser.add_argument("--header", action="append", default=[])
    parser.add_argument("--data")
    parser.add_argument("--data-file", type=Path)
    parser.add_argument("--raw-file", type=Path)
    parser.add_argument("--content-type")
    parser.add_argument("--format", choices=("json", "toon"), default="json")
    parser.add_argument("--output-file", type=Path)


def _add_r2_parser(
    subparsers: argparse._SubParsersAction[Any],
) -> dict[str, argparse._SubParsersAction[Any]]:
    r2 = subparsers.add_parser("r2")
    r2.set_defaults(action="r2")
    commands = r2.add_subparsers(dest="r2_command", required=True)

    request = commands.add_parser("request")
    request.add_argument("method")
    request.add_argument("path")
    _add_r2_arguments(request, body=True)

    buckets = commands.add_parser("list-buckets")
    _add_r2_arguments(buckets)

    objects = commands.add_parser("list-objects")
    objects.add_argument("bucket")
    _add_r2_arguments(objects)

    for command in ("get-object", "delete-object", "head-object"):
        object_parser = commands.add_parser(command)
        object_parser.add_argument("bucket")
        object_parser.add_argument("key")
        _add_r2_arguments(object_parser)

    put = commands.add_parser("put-object")
    put.add_argument("bucket")
    put.add_argument("key")
    put.add_argument("--raw-file", type=Path, required=True)
    _add_r2_arguments(put, content_type=True)
    return {"r2": commands}


def _add_r2_arguments(
    parser: argparse.ArgumentParser,
    *,
    body: bool = False,
    content_type: bool = False,
) -> None:
    parser.add_argument("--account", default=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=float, default=argparse.SUPPRESS)
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--header", action="append", default=[])
    if body:
        parser.add_argument("--data")
        parser.add_argument("--data-file", type=Path)
        parser.add_argument("--raw-file", type=Path)
        parser.add_argument("--content-type")
    elif content_type:
        parser.add_argument("--content-type")
    parser.add_argument("--format", choices=("json", "toon"), default="json")
    parser.add_argument("--output-file", type=Path)
