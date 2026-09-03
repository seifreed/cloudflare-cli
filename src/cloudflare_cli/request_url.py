"""Pure URL construction for Cloudflare API requests."""

from __future__ import annotations

import urllib.parse
from collections.abc import Mapping
from typing import Any

from cloudflare_cli.parameter_resolution import query_values


def build_url(
    base_url: str,
    account_id: str | None,
    path: str,
    query: Mapping[str, Any] | None,
    path_params: Mapping[str, str] | None,
) -> str:
    parsed_path = urllib.parse.urlsplit(path)
    if parsed_path.scheme or parsed_path.netloc:
        raise ValueError("Cloudflare path must be relative")
    resolved_path = parsed_path.path
    parameters = {"account_id": account_id, **(path_params or {})}
    for key, value in parameters.items():
        if value is not None:
            resolved_path = resolved_path.replace(
                f"{{{key}}}", urllib.parse.quote(value, safe="")
            )
    if "{" in resolved_path or "}" in resolved_path:
        raise ValueError(f"Missing path parameter in {resolved_path!r}")
    if not resolved_path.startswith("/"):
        resolved_path = f"/{resolved_path}"
    url = f"{base_url}{resolved_path}"
    query_values_list = urllib.parse.parse_qsl(
        parsed_path.query, keep_blank_values=True
    )
    for key, value in (query or {}).items():
        query_values_list.extend(
            (key, str(item).lower() if isinstance(item, bool) else str(item))
            for item in query_values(value)
            if item is not None
        )
    encoded_query = urllib.parse.urlencode(query_values_list)
    return f"{url}?{encoded_query}" if encoded_query else url
