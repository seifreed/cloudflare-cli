"""Pure AWS Signature Version 4 primitives for the R2 adapter."""

from __future__ import annotations

import hashlib
import hmac
import re
import urllib.parse
from collections.abc import Mapping
from datetime import datetime

_PERCENT_ESCAPE = re.compile(r"%[0-9A-Fa-f]{2}")


def canonical_uri(path: str) -> str:
    parts = re.split(f"({_PERCENT_ESCAPE.pattern})", path)
    return "".join(
        (
            part.upper()
            if _PERCENT_ESCAPE.fullmatch(part)
            else urllib.parse.quote(part, safe="/-_.~")
        )
        for part in parts
    )


def canonical_query(
    existing: str,
    values: Mapping[str, object] | None,
) -> str:
    pairs = urllib.parse.parse_qsl(existing, keep_blank_values=True)
    for key, value in (values or {}).items():
        items = value if isinstance(value, (list, tuple)) else (value,)
        pairs.extend(
            (
                key,
                str(item).lower() if isinstance(item, bool) else str(item),
            )
            for item in items
            if item is not None
        )
    encoded = [
        (
            urllib.parse.quote(str(key), safe="-_.~"),
            urllib.parse.quote(str(value), safe="-_.~"),
        )
        for key, value in pairs
    ]
    return "&".join(f"{key}={value}" for key, value in sorted(encoded))


def signed_headers(
    host: str,
    payload: bytes,
    headers: Mapping[str, str] | None,
    content_type: str | None,
    session_token: str | None,
    timestamp: datetime,
) -> dict[str, str]:
    result = {
        key.lower(): " ".join(value.strip().split())
        for key, value in (headers or {}).items()
        if key.lower() != "authorization"
    }
    result["host"] = host
    result["x-amz-content-sha256"] = hashlib.sha256(payload).hexdigest()
    result["x-amz-date"] = timestamp.strftime("%Y%m%dT%H%M%SZ")
    if content_type:
        result["content-type"] = content_type
    if session_token:
        result["x-amz-security-token"] = session_token
    return result


def authorization(
    method: str,
    uri: str,
    query: str,
    headers: Mapping[str, str],
    access_key_id: str,
    secret_access_key: str,
    region: str,
    timestamp: datetime,
) -> str:
    canonical_headers = "".join(
        f"{key}:{' '.join(headers[key].strip().split())}\n" for key in sorted(headers)
    )
    signed_names = ";".join(sorted(headers))
    canonical_request = "\n".join(
        (
            method,
            uri,
            query,
            canonical_headers,
            signed_names,
            headers["x-amz-content-sha256"],
        )
    )
    date = timestamp.strftime("%Y%m%d")
    scope = f"{date}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(
        (
            "AWS4-HMAC-SHA256",
            timestamp.strftime("%Y%m%dT%H%M%SZ"),
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        )
    )
    signature = hmac.new(
        signing_key(secret_access_key, date, region),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return (
        f"AWS4-HMAC-SHA256 Credential={access_key_id}/{scope}, "
        f"SignedHeaders={signed_names}, Signature={signature}"
    )


def signing_key(secret: str, date: str, region: str) -> bytes:
    date_key = hmac.new(
        f"AWS4{secret}".encode(), date.encode(), hashlib.sha256
    ).digest()
    region_key = hmac.new(date_key, region.encode(), hashlib.sha256).digest()
    service_key = hmac.new(region_key, b"s3", hashlib.sha256).digest()
    return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()
