"""Application ports for outbound HTTP requests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from cloudflare_cli.registry import Operation


@dataclass(frozen=True, slots=True)
class TransportResponse:
    """HTTP response data needed by API adapters."""

    status: int
    body: bytes
    content_type: str | None
    headers: Mapping[str, str]


class TransportError(RuntimeError):
    """A transport-level failure before an API response was available."""


class Transport(Protocol):
    """Port used by API clients to perform HTTP requests."""

    def request(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None,
        headers: Mapping[str, str],
    ) -> TransportResponse: ...


class OperationCatalog(Protocol):
    """Port used by the client to resolve documented operations."""

    def operation(self, operation_id: str) -> Operation: ...

    def operation_methods(self) -> Mapping[str, str]: ...
