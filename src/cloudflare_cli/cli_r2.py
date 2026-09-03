"""CLI adapter for the R2 application client."""

from __future__ import annotations

from argparse import Namespace
from typing import Any

from cloudflare_cli.cli_values import body_from_args, query_from_args
from cloudflare_cli.config import load_config
from cloudflare_cli.r2 import R2Client


def run_r2(args: Namespace) -> Any:
    valid_commands = {
        "request",
        "list-buckets",
        "list-objects",
        "get-object",
        "put-object",
        "delete-object",
        "head-object",
    }
    if args.r2_command not in valid_commands:
        raise ValueError(f"Unknown R2 command {args.r2_command!r}")
    config = load_config(args.config)
    client = R2Client.from_account(config.account(args.account), args.timeout)
    if args.r2_command == "request":
        result = client.request(
            args.method,
            args.path,
            query=query_from_args(args.query, repeat=True),
            body=body_from_args(args),
            content_type=args.content_type,
            headers=query_from_args(args.header),
        )
    elif args.r2_command == "list-buckets":
        result = client.list_buckets(
            query=query_from_args(args.query, repeat=True),
            headers=query_from_args(args.header),
        )
    elif args.r2_command == "list-objects":
        result = client.list_objects(
            args.bucket,
            headers=query_from_args(args.header),
            **query_from_args(args.query, repeat=True),
        )
    elif args.r2_command == "get-object":
        result = client.get_object(
            args.bucket,
            args.key,
            query=query_from_args(args.query, repeat=True),
            headers=query_from_args(args.header),
        )
    elif args.r2_command == "put-object":
        result = client.put_object(
            args.bucket,
            args.key,
            args.raw_file.read_bytes(),
            query=query_from_args(args.query, repeat=True),
            content_type=args.content_type,
            headers=query_from_args(args.header),
        )
    elif args.r2_command == "delete-object":
        result = client.delete_object(
            args.bucket,
            args.key,
            query=query_from_args(args.query, repeat=True),
            headers=query_from_args(args.header),
        )
    else:
        result = client.head_object(
            args.bucket,
            args.key,
            query=query_from_args(args.query, repeat=True),
            headers=query_from_args(args.header),
        )
    return result
