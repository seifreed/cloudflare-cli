"""R2 payload and S3 XML response codecs."""

from __future__ import annotations

import json
from typing import Any

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException


class R2DecodeError(ValueError):
    """A response body cannot be decoded as the declared format."""


def payload(body: bytes | str | Any) -> bytes:
    if body is None:
        return b""
    if isinstance(body, bytes):
        return body
    if isinstance(body, str):
        return body.encode("utf-8")
    return json.dumps(body).encode("utf-8")


def decode(data: bytes, content_type: str | None) -> Any:
    if not data:
        return None
    try:
        if content_type and "json" in content_type.lower():
            return json.loads(data.decode("utf-8"))
        if data.lstrip().startswith(b"<") or (
            content_type and "xml" in content_type.lower()
        ):
            return _xml_to_data(data)
        return data
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ET.ParseError,
        DefusedXmlException,
    ) as error:
        raise R2DecodeError("R2 returned an invalid response") from error


def _xml_to_data(data: bytes) -> dict[str, Any]:
    root = ET.fromstring(data)
    return {_tag(root.tag): _xml_element(root)}


def _xml_element(element: Any) -> Any:
    if not list(element):
        return element.text or ""
    result: dict[str, Any] = {}
    for child in element:
        key = _tag(child.tag)
        value = _xml_element(child)
        if key in result:
            result[key] = (
                result[key] if isinstance(result[key], list) else [result[key]]
            )
            result[key].append(value)
        else:
            result[key] = value
    return result


def _tag(value: str) -> str:
    return value.rsplit("}", 1)[-1]
