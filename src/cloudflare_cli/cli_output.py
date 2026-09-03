"""CLI response formatting and file output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cloudflare_cli.toon import encode as encode_toon


def format_output(value: Any, output_format: str) -> str:
    if isinstance(value, bytes):
        raise ValueError("Binary response requires --output-file")
    if output_format == "toon":
        return encode_toon(value)
    return json.dumps(value, ensure_ascii=False, indent=2)


def write_output(value: Any, path: Path, output_format: str) -> None:
    content = (
        value
        if isinstance(value, bytes)
        else format_output(value, output_format).encode()
    )
    path.write_bytes(content)
