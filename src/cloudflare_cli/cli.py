"""CLI composition root for the Cloudflare client."""

from __future__ import annotations

import json
import sys

from cloudflare_cli.cli_output import format_output, write_output
from cloudflare_cli.cli_parser import build_parser
from cloudflare_cli.cli_runtime import run
from cloudflare_cli.client import CloudflareError
from cloudflare_cli.r2 import R2Error


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run(args)
        if result is not None:
            output_file = getattr(args, "output_file", None)
            if output_file:
                write_output(result, output_file, args.format)
            else:
                print(format_output(result, args.format))
    except (
        CloudflareError,
        R2Error,
        ValueError,
        OSError,
        json.JSONDecodeError,
    ) as error:
        print(f"cloudflare: {error}", file=sys.stderr)
        return 1
    return 0
