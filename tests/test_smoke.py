from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from cloudflare_cli import AccountConfig, CloudflareClient
from cloudflare_cli.cli import main
from cloudflare_cli.toon import encode


class Handler(BaseHTTPRequestHandler):
    request_body = b""
    request_path = ""
    request_headers: dict[str, str] = {}

    def do_GET(self) -> None:
        type(self).request_path = self.path
        type(self).request_headers = {key: value for key, value in self.headers.items()}
        responses = {
            "/binary": (200, "text/plain", b"binary"),
            "/empty": (200, "application/json", b""),
            "/invalid": (200, "application/json", b"{"),
            "/error-invalid": (400, "application/json", b"{"),
            "/redirect": (302, "application/json", b""),
            "/error": (400, "application/json", b'{"errors":[{"code":1000}]}'),
            "/error-text": (500, "text/plain", b"server error"),
        }
        status, content_type, body = responses.get(
            urlsplit(self.path).path,
            (
                200,
                "application/json",
                b'{"success":true,"result":[{"id":"1","name":"zone"}]}',
            ),
        )
        self._send(status, content_type, body)

    def do_POST(self) -> None:
        type(self).request_body = self.rfile.read(int(self.headers["Content-Length"]))
        type(self).request_headers = {key: value for key, value in self.headers.items()}
        self._send(200, "application/json", b'{"success":true}')

    def do_DELETE(self) -> None:
        type(self).request_path = self.path
        type(self).request_headers = {key: value for key, value in self.headers.items()}
        self._send(200, "application/json", b'{"success":true}')

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


def server() -> tuple[ThreadingHTTPServer, threading.Thread]:
    instance = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=instance.serve_forever)
    thread.start()
    return instance, thread


def test_client_get_and_post() -> None:
    instance, thread = server()
    try:
        client = CloudflareClient(
            AccountConfig("test", "account", "token"),
            f"http://127.0.0.1:{instance.server_port}",
        )
        assert client.request("GET", "/zones", query={"page": 1})["success"] is True
        assert Handler.request_path == "/zones?page=1"
        assert (
            client.request("POST", "/zones", body={"name": "example.com"})["success"]
            is True
        )
        assert json.loads(Handler.request_body) == {"name": "example.com"}
    finally:
        instance.shutdown()
        thread.join()


def test_config_and_formats(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'default_account = "customer"\n'
        "[accounts.customer]\n"
        'account_id = "id"\n'
        'api_token = "token"\n',
        encoding="utf-8",
    )
    assert main(["--config", str(config_path), "accounts"]) == 0
    assert (
        encode({"users": [{"id": 1, "name": "Ada"}]}) == "users[1]{id,name}:\n  1,Ada"
    )
