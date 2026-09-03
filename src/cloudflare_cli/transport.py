"""Infrastructure adapter for HTTP requests."""

from __future__ import annotations

import http.client
import urllib.parse
from collections.abc import Mapping

from cloudflare_cli.ports import TransportError, TransportResponse


class HttpTransport:
    """Stdlib HTTP adapter for Windows, Linux, and macOS."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def request(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None,
        headers: Mapping[str, str],
    ) -> TransportResponse:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("HTTP URL must use http or https")
        connection_type = (
            http.client.HTTPSConnection
            if parsed.scheme == "https"
            else http.client.HTTPConnection
        )
        connection = connection_type(parsed.hostname, parsed.port, timeout=self.timeout)
        try:
            target = parsed.path or "/"
            if parsed.query:
                target = f"{target}?{parsed.query}"
            connection.request(method, target, body=body, headers=dict(headers))
            response = connection.getresponse()
            return TransportResponse(
                response.status,
                response.read(),
                response.getheader("Content-Type"),
                {key.lower(): value for key, value in response.getheaders()},
            )
        except (http.client.HTTPException, OSError) as error:
            raise TransportError(str(error)) from error
        finally:
            connection.close()
