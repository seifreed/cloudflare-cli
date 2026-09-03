from __future__ import annotations

import re
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from cloudflare_cli import AccountConfig, R2Client, R2Error
from cloudflare_cli.cli import main
from cloudflare_cli.r2_codec import decode, payload
from cloudflare_cli.r2_signing import (
    authorization,
    canonical_query,
    canonical_uri,
    signed_headers,
)


class R2Handler(BaseHTTPRequestHandler):
    request_body = b""
    request_path = ""
    request_headers: dict[str, str] = {}

    def _capture(self) -> None:
        type(self).request_path = self.path
        type(self).request_headers = {key: value for key, value in self.headers.items()}

    def do_GET(self) -> None:
        self._capture()
        if self.path == "/error":
            self._send(
                403, "application/xml", b"<Error><Code>AccessDenied</Code></Error>"
            )
        elif self.path == "/invalid-error":
            self._send(403, "application/json", b"{")
        elif self.path == "/invalid-json":
            self._send(200, "application/json", b"{")
        elif self.path == "/redirect":
            self._send(302, "application/json", b"")
        elif self.path == "/":
            self._send(
                200,
                "application/xml",
                b"<ListAllMyBucketsResult xmlns='urn:test'><Buckets>"
                b"<Bucket><Name>one</Name></Bucket>"
                b"<Bucket><Name>two</Name></Bucket>"
                b"</Buckets></ListAllMyBucketsResult>",
            )
        elif "prefix=" in self.path or "list-type=2" in self.path:
            self._send(
                200,
                "application/xml",
                b"<ListBucketResult><KeyCount>0</KeyCount></ListBucketResult>",
            )
        else:
            self._send(200, "application/octet-stream", b"object-data")

    def do_PUT(self) -> None:
        self._capture()
        self.__class__.request_body = self.rfile.read(
            int(self.headers["Content-Length"])
        )
        self._send(200, "application/xml", b"")

    def do_DELETE(self) -> None:
        self._capture()
        self._send(204, "application/xml", b"")

    def do_HEAD(self) -> None:
        self._capture()
        self._send(200, "application/xml", b"")

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


def r2_server() -> tuple[ThreadingHTTPServer, threading.Thread]:
    instance = ThreadingHTTPServer(("127.0.0.1", 0), R2Handler)
    thread = threading.Thread(target=instance.serve_forever)
    thread.start()
    return instance, thread


def test_r2_sigv4_and_object_operations() -> None:
    instance, thread = r2_server()
    try:
        client = R2Client(
            "access",
            "secret",
            f"http://127.0.0.1:{instance.server_port}",
            session_token="session",
        )
        buckets = client.list_buckets()
        assert (
            buckets["ListAllMyBucketsResult"]["Buckets"]["Bucket"][1]["Name"] == "two"
        )
        assert re.match(
            r"AWS4-HMAC-SHA256 Credential=access/\d{8}/auto/s3/aws4_request, ",
            R2Handler.request_headers["Authorization"],
        )
        assert "x-amz-security-token" in R2Handler.request_headers
        assert R2Handler.request_headers["x-amz-content-sha256"]

        assert client.list_objects("my bucket", prefix="a b", empty=None) == {
            "ListBucketResult": {"KeyCount": "0"}
        }
        assert R2Handler.request_path == "/my%20bucket?prefix=a%20b"
        assert (
            client.request("GET", "relative", headers={"Authorization": "forged"})
            == b"object-data"
        )
        assert "authorization" not in R2Handler.request_headers
        assert client.get_object("bucket", "folder/a b.txt") == b"object-data"
        assert R2Handler.request_path == "/bucket/folder/a%20b.txt"
        assert client.get_object("bucket", "folder/a?b#c") == b"object-data"
        assert R2Handler.request_path == "/bucket/folder/a%3Fb%23c"
        assert (
            client.put_object("bucket", "key", b"payload", content_type="text/plain")
            is None
        )
        assert R2Handler.request_body == b"payload"
        assert R2Handler.request_headers["content-type"] == "text/plain"
        assert client.delete_object("bucket", "key") is None
        assert client.head_object("bucket", "key")["content-type"] == "application/xml"
    finally:
        instance.shutdown()
        thread.join()


def test_r2_helpers_and_failures(tmp_path: Path) -> None:
    timestamp = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    headers = signed_headers(
        "host", b"body", {"X-Test": "  value  "}, "text/plain", "token", timestamp
    )
    authorization_header = authorization(
        "GET", "/path", "a=b", headers, "access", "secret", "auto", timestamp
    )
    assert "x-test" in authorization_header
    assert canonical_uri("/a%20b") == "/a%20b"
    assert canonical_uri("/bucket/a%2Fb") == "/bucket/a%2Fb"
    assert (
        canonical_query("z=last", {"a": "first value", "enabled": True, "skip": None})
        == "a=first%20value&enabled=true&z=last"
    )
    assert canonical_query("", {"tag": ["b", "a"]}) == "tag=a&tag=b"
    assert payload(None) == b""
    assert payload(b"raw") == b"raw"
    assert payload("text") == b"text"
    assert payload({"ok": True}) == b'{"ok": true}'
    assert decode(b"", None) is None
    assert decode(b'{"ok":true}', "application/json") == {"ok": True}
    assert decode(b"<Root><Value>ok</Value></Root>", None) == {"Root": {"Value": "ok"}}

    client = R2Client("access", "secret", "ftp://localhost")
    with pytest.raises(ValueError):
        client.request("GET")
    with pytest.raises(ValueError):
        R2Client.from_account(AccountConfig("missing", "id", None))
    derived = R2Client.from_account(
        AccountConfig(
            "derived",
            "id",
            None,
            s3_access_key_id="access",
            s3_secret_access_key="secret",
        )
    )
    assert derived.endpoint == "https://id.r2.cloudflarestorage.com"
    with pytest.raises(ValueError):
        R2Client.from_account(
            AccountConfig(
                "missing",
                None,
                None,
                s3_access_key_id="access",
                s3_secret_access_key="secret",
            )
        )

    instance, thread = r2_server()
    try:
        with pytest.raises(R2Error) as error:
            R2Client(
                "access", "secret", f"http://127.0.0.1:{instance.server_port}"
            ).request("GET", "/error")
        assert error.value.status == 403
        with pytest.raises(R2Error, match="invalid"):
            R2Client(
                "access", "secret", f"http://127.0.0.1:{instance.server_port}"
            ).request("GET", "/invalid-json")
        with pytest.raises(R2Error) as invalid_error:
            R2Client(
                "access", "secret", f"http://127.0.0.1:{instance.server_port}"
            ).request("GET", "/invalid-error")
        assert invalid_error.value.status == 403
        with pytest.raises(R2Error) as redirect_error:
            R2Client(
                "access", "secret", f"http://127.0.0.1:{instance.server_port}"
            ).request("GET", "/redirect")
        assert redirect_error.value.status == 302
    finally:
        instance.shutdown()
        thread.join()
        instance.server_close()
    with pytest.raises(R2Error):
        R2Client(
            "access", "secret", f"http://127.0.0.1:{instance.server_port}"
        ).request("GET")


def test_r2_cli_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    instance, thread = r2_server()
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[accounts.one]\n"
        'account_id = "id"\n'
        "[accounts.one.s3]\n"
        'access_key_id = "access"\n'
        'secret_access_key = "secret"\n'
        f'endpoint = "http://127.0.0.1:{instance.server_port}"\n',
        encoding="utf-8",
    )
    try:
        prefix = ["--config", str(config_path), "r2"]
        assert main([*prefix, "request", "GET", "/", "--format", "toon"]) == 0
        assert main([*prefix, "list-buckets"]) == 0
        assert main([*prefix, "list-objects", "bucket", "--query", "list-type=2"]) == 0
        output = tmp_path / "object.bin"
        assert (
            main([*prefix, "get-object", "bucket", "key", "--output-file", str(output)])
            == 0
        )
        assert output.read_bytes() == b"object-data"
        source = tmp_path / "source.bin"
        source.write_bytes(b"cli-data")
        assert (
            main(
                [
                    *prefix,
                    "put-object",
                    "bucket",
                    "key",
                    "--raw-file",
                    str(source),
                    "--query",
                    "uploadId=u",
                ]
            )
            == 0
        )
        assert R2Handler.request_path == "/bucket/key?uploadId=u"
        assert main([*prefix, "delete-object", "bucket", "key"]) == 0
        assert (
            main(
                [
                    *prefix,
                    "delete-object",
                    "bucket",
                    "key",
                    "--query",
                    "versionId=v",
                ]
            )
            == 0
        )
        assert R2Handler.request_path == "/bucket/key?versionId=v"
        assert (
            main(
                [
                    *prefix,
                    "head-object",
                    "bucket",
                    "key",
                    "--header",
                    "X-Test=yes",
                ]
            )
            == 0
        )
        assert R2Handler.request_headers["x-test"] == "yes"
    finally:
        instance.shutdown()
        thread.join()
    assert capsys.readouterr().out
