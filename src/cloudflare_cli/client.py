"""Cloudflare API application client."""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import partial
from typing import Any

from cloudflare_cli.models import AccountConfig
from cloudflare_cli.parameter_resolution import (
    resolve_parameters,
)
from cloudflare_cli.ports import OperationCatalog, Transport, TransportError
from cloudflare_cli.request_url import build_url


class CloudflareError(RuntimeError):
    """An HTTP or API-level Cloudflare failure."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class CloudflareClient:
    """Call every Cloudflare API operation through one stable interface."""

    def __init__(
        self,
        account: AccountConfig,
        base_url: str = "https://api.cloudflare.com/client/v4",
        timeout: float = 30.0,
        transport: Transport | None = None,
        catalog: OperationCatalog | None = None,
    ) -> None:
        self.account = account
        self.base_url = base_url.rstrip("/")
        self.transport = (
            transport if transport is not None else _default_transport(timeout)
        )
        self.catalog = catalog if catalog is not None else _default_catalog()

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        path_params: Mapping[str, str] | None = None,
        body: Any = None,
        content_type: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Send an API request; ``path`` may be any documented Cloudflare path."""
        url = build_url(
            self.base_url, self.account.account_id, path, query, path_params
        )
        request_headers: dict[str, str] = {}
        for key, value in (headers or {}).items():
            lower_key = key.lower()
            if lower_key in {"authorization", "x-auth-key", "x-auth-email"}:
                continue
            canonical_key = {
                "accept": "Accept",
                "content-type": "Content-Type",
            }.get(lower_key, key)
            request_headers[canonical_key] = value
        request_headers.setdefault("Accept", "application/json")
        request_headers.update(self.account.headers())
        data = None
        if body is not None:
            if content_type:
                request_headers["Content-Type"] = content_type
            else:
                request_headers.setdefault("Content-Type", "application/json")
            data = _encode_body(body, content_type)
        try:
            response = self.transport.request(
                method.upper(), url, body=data, headers=request_headers
            )
            if not 200 <= response.status < 300:
                try:
                    payload = _decode_response(response.body, response.content_type)
                except CloudflareError as error:
                    raise CloudflareError(str(error), response.status) from error
                message = (
                    payload.get("errors", payload)
                    if isinstance(payload, dict)
                    else payload
                )
                raise CloudflareError(str(message), response.status)
            return _decode_response(response.body, response.content_type)
        except TransportError as error:
            raise CloudflareError(f"Cloudflare request failed: {error}") from error

    def call(
        self,
        operation_id: str,
        *,
        query: Mapping[str, Any] | None = None,
        operation_parameters: Mapping[str, Any] | None = None,
        path_params: Mapping[str, str] | None = None,
        body: Any = None,
        content_type: str | None = None,
        headers: Mapping[str, str] | None = None,
        **parameters: Any,
    ) -> Any:
        """Call a named OpenAPI operation with its documented parameters."""
        definition = self.catalog.operation(operation_id)
        operation_values = dict(operation_parameters or {})
        if (
            query is not None
            and not isinstance(query, Mapping)
            and any(parameter.name == "query" for parameter in definition.parameters)
        ):
            operation_values["query"] = query
            query = None
        operation_values.update(parameters)
        path_values, query_values, header_values = resolve_parameters(
            definition,
            self.account.account_id,
            query,
            path_params,
            headers,
            operation_values,
        )
        if definition.request_body_required and body is None:
            raise ValueError(f"Operation {operation_id!r} requires a request body")
        return self.request(
            definition.method,
            definition.path,
            query=query_values,
            path_params=path_values,
            body=body,
            content_type=content_type,
            headers=header_values,
        )

    def __getattr__(self, name: str) -> Any:
        methods = self.catalog.operation_methods()
        if name in methods:
            return partial(self.call, methods[name])
        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(self.catalog.operation_methods()))


def _decode_response(data: bytes, content_type: str | None) -> Any:
    if not data:
        return None
    if content_type and "json" not in content_type.lower():
        return data
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CloudflareError("Cloudflare returned an invalid JSON response") from error


def _encode_body(body: Any, content_type: str | None) -> bytes:
    if isinstance(body, bytes):
        return body
    if content_type and "json" not in content_type.lower():
        if isinstance(body, str):
            return body.encode("utf-8")
        raise ValueError("Non-JSON request bodies require bytes or str")
    return json.dumps(body).encode("utf-8")


def _default_transport(timeout: float) -> Transport:
    from cloudflare_cli.transport import HttpTransport

    return HttpTransport(timeout)


def _default_catalog() -> OperationCatalog:
    from cloudflare_cli.catalog import PackagedOperationCatalog

    return PackagedOperationCatalog()
