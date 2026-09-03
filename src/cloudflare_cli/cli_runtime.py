"""Command execution for the Cloudflare command-line adapter."""

from __future__ import annotations

from argparse import Namespace
from typing import Any

from cloudflare_cli.catalog import operations
from cloudflare_cli.cli_r2 import run_r2
from cloudflare_cli.cli_values import body_from_args, query_from_args
from cloudflare_cli.client import CloudflareClient
from cloudflare_cli.config import load_config


def run(args: Namespace) -> Any:
    if args.action == "accounts":
        config = load_config(args.config)
        return [
            {"name": name, "account_id": account.account_id}
            for name, account in config.accounts.items()
        ]
    if args.action == "operations":
        return [
            {
                "operation_id": item.operation_id,
                "method": item.method,
                "path": item.path,
            }
            for item in operations()
        ]
    if args.action == "r2":
        return run_r2(args)
    config = load_config(args.config)
    client = CloudflareClient(
        config.account(args.account),
        args.base_url or "https://api.cloudflare.com/client/v4",
        args.timeout,
    )
    body = body_from_args(args)
    if args.action == "operation":
        parameters = {
            name: getattr(args, destination)
            for name, destination in args.operation_parameters
            if getattr(args, destination) is not None
        }
        return client.call(
            args.operation_id,
            query=query_from_args(args.query, repeat=True),
            path_params=query_from_args(args.path_param),
            body=body,
            content_type=args.content_type,
            headers=query_from_args(args.header),
            **parameters,
        )
    return client.request(
        args.method,
        args.path,
        query=query_from_args(args.query, repeat=True),
        path_params=query_from_args(args.path_param),
        body=body,
        content_type=args.content_type,
        headers=query_from_args(args.header),
    )
