"""S3-compatible Cloudflare R2 application client."""

from __future__ import annotations

import urllib.parse
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from cloudflare_cli.models import AccountConfig
from cloudflare_cli.ports import Transport, TransportError
from cloudflare_cli.r2_codec import R2DecodeError, decode, payload
from cloudflare_cli.r2_signing import (
    authorization,
    canonical_query,
    canonical_uri,
    signed_headers,
)


class R2Error(RuntimeError):
    """An R2 transport or S3 API failure."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class R2Client:
    """Call the R2 S3-compatible API using AWS Signature Version 4."""

    def __init__(
        self,
        access_key_id: str,
        secret_access_key: str,
        endpoint: str,
        region: str = "auto",
        session_token: str | None = None,
        timeout: float = 30.0,
        transport: Transport | None = None,
    ) -> None:
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.endpoint = endpoint.rstrip("/")
        self.region = region or "auto"
        self.session_token = session_token
        self.transport = (
            transport if transport is not None else _default_transport(timeout)
        )

    @classmethod
    def from_account(cls, account: AccountConfig, timeout: float = 30.0) -> R2Client:
        if not account.s3_access_key_id or not account.s3_secret_access_key:
            raise ValueError(f"Account {account.name!r} has no R2 S3 credentials")
        endpoint = account.s3_endpoint
        if endpoint is None and account.account_id:
            endpoint = f"https://{account.account_id}.r2.cloudflarestorage.com"
        if endpoint is None:
            raise ValueError("R2 S3 endpoint is required")
        return cls(
            account.s3_access_key_id,
            account.s3_secret_access_key,
            endpoint,
            account.s3_region,
            account.s3_session_token,
            timeout,
        )

    def request(
        self,
        method: str,
        path: str = "/",
        *,
        query: Mapping[str, Any] | None = None,
        body: bytes | str | Any = b"",
        content_type: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        request_body = payload(body)
        request_method = method.upper()
        parsed = self._parse_url(path)
        request_uri = canonical_uri(parsed.path or "/")
        request_query = canonical_query(parsed.query, query)
        timestamp = datetime.now(UTC)
        request_headers = signed_headers(
            parsed.netloc,
            request_body,
            headers,
            content_type,
            self.session_token,
            timestamp,
        )
        request_headers["Authorization"] = authorization(
            request_method,
            request_uri,
            request_query,
            request_headers,
            self.access_key_id,
            self.secret_access_key,
            self.region,
            timestamp,
        )
        request_url = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, request_uri, request_query, "")
        )
        try:
            response = self.transport.request(
                request_method, request_url, body=request_body, headers=request_headers
            )
            if not 200 <= response.status < 300:
                try:
                    message = decode(response.body, response.content_type)
                except R2DecodeError as error:
                    raise R2Error(str(error), response.status) from error
                raise R2Error(str(message), response.status)
            if request_method == "HEAD":
                return dict(response.headers)
            return decode(response.body, response.content_type)
        except R2Error:
            raise
        except R2DecodeError as error:
            raise R2Error(str(error)) from error
        except TransportError as error:
            raise R2Error(f"R2 request failed: {error}") from error

    def list_buckets(
        self,
        *,
        query: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        return self.request("GET", "/", query=query, headers=headers)

    def list_objects(
        self,
        bucket: str,
        *,
        headers: Mapping[str, str] | None = None,
        **query: Any,
    ) -> Any:
        return self.request("GET", _bucket_path(bucket), query=query, headers=headers)

    def get_object(
        self,
        bucket: str,
        key: str,
        *,
        query: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        return self.request(
            "GET", _object_path(bucket, key), query=query, headers=headers
        )

    def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes,
        *,
        query: Mapping[str, Any] | None = None,
        content_type: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        return self.request(
            "PUT",
            _object_path(bucket, key),
            query=query,
            body=body,
            content_type=content_type,
            headers=headers,
        )

    def delete_object(
        self,
        bucket: str,
        key: str,
        *,
        query: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        return self.request(
            "DELETE", _object_path(bucket, key), query=query, headers=headers
        )

    def head_object(
        self,
        bucket: str,
        key: str,
        *,
        query: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        return self.request(
            "HEAD", _object_path(bucket, key), query=query, headers=headers
        )

    def _parse_url(self, path: str) -> urllib.parse.SplitResult:
        if not path.startswith("/"):
            path = f"/{path}"
        parsed = urllib.parse.urlsplit(f"{self.endpoint}{path}")
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("R2 endpoint must use http or https")
        return parsed


def _bucket_path(bucket: str) -> str:
    return f"/{urllib.parse.quote(bucket, safe='-_.~')}"


def _object_path(bucket: str, key: str) -> str:
    return f"{_bucket_path(bucket)}/{urllib.parse.quote(key, safe='/-_.~')}"


def _default_transport(timeout: float) -> Transport:
    from cloudflare_cli.transport import HttpTransport

    return HttpTransport(timeout)
