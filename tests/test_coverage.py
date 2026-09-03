from __future__ import annotations

import json
import os
from argparse import Namespace
from pathlib import Path

import pytest
from test_smoke import Handler, server

from cloudflare_cli import AccountConfig, CloudflareClient, CloudflareError
from cloudflare_cli.cli import main
from cloudflare_cli.cli_output import format_output
from cloudflare_cli.cli_r2 import run_r2 as _run_r2
from cloudflare_cli.cli_runtime import (
    run,
)
from cloudflare_cli.cli_values import body_from_args as _body
from cloudflare_cli.cli_values import query_from_args as _query
from cloudflare_cli.config import CloudflareConfig, load_config
from cloudflare_cli.toon import _field, encode


def test_account_headers_and_selection() -> None:
    token = AccountConfig("token", "id", "secret")
    assert token.headers() == {"Authorization": "Bearer secret"}
    key = AccountConfig("key", "id", None, "key", "mail")
    assert key.headers() == {"X-Auth-Key": "key", "X-Auth-Email": "mail"}
    with pytest.raises(ValueError):
        AccountConfig("bad", "id", None, "key").headers()
    config = CloudflareConfig({"one": token}, "one")
    assert config.account().name == "token"
    with pytest.raises(ValueError):
        config.account("missing")


def test_config_file_validation(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'default_account = "missing"\n'
        "[accounts.one]\n"
        'account_id = "id"\n'
        'api_token = "token"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_config(config_path)
    config_path.write_text("[accounts]\none = 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(config_path)
    config_path.write_text("accounts = 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(config_path)
    config_path.write_text(
        'default_account = 1\n[accounts.one]\naccount_id = "id"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="default_account"):
        load_config(config_path)
    config_path.write_text(
        'unknown = "value"\n[accounts.one]\naccount_id = "id"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="top-level"):
        load_config(config_path)
    config_path.write_text("[accounts.one]\naccount_id = 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(config_path)
    config_path.write_text('[accounts.one]\nunknown = "value"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(config_path)
    config_path.write_text(
        '[accounts.one]\naccount_id = "id"\n'
        '[accounts.one.s3]\naccess_key_id = "access"\n'
        'secret_access_key = "secret"\nregion = "auto"\n',
        encoding="utf-8",
    )
    account = load_config(config_path).account()
    assert account.s3_access_key_id == "access"
    config_path.write_text('[accounts.one.s3]\nunknown = "value"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(config_path)
    config_path.write_text("[accounts.one]\ns3 = 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(config_path)


def test_environment_configuration(tmp_path: Path) -> None:
    names = (
        "CLOUDFLARE",
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_API_KEY",
        "CLOUDFLARE_EMAIL",
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_ACCOUNT",
        "CLOUDFLARE_CONFIG",
        "XDG_CONFIG_HOME",
        "APPDATA",
        "CLOUDFLARE_R2_ACCESS_KEY_ID",
        "CLOUDFLARE_R2_SECRET_ACCESS_KEY",
        "CLOUDFLARE_R2_ENDPOINT",
        "CLOUDFLARE_R2_REGION",
        "CLOUDFLARE_R2_SESSION_TOKEN",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_ENDPOINT_URL",
        "AWS_REGION",
        "AWS_SESSION_TOKEN",
    )
    saved = {name: os.environ.get(name) for name in names}
    try:
        for name in names:
            os.environ.pop(name, None)
        with pytest.raises(ValueError):
            load_config()
        os.environ.update(
            {
                "CLOUDFLARE_API_TOKEN": "token",
                "CLOUDFLARE_ACCOUNT_ID": "id",
                "CLOUDFLARE_ACCOUNT": "env",
            }
        )
        assert load_config().account().name == "env"
        os.environ.pop("CLOUDFLARE_API_TOKEN")
        os.environ.update(
            {"CLOUDFLARE": "token", "CLOUDFLARE_CONFIG": "does-not-exist"}
        )
        with pytest.raises(FileNotFoundError):
            load_config()
        for name in names:
            os.environ.pop(name, None)
        os.environ.update(
            {
                "CLOUDFLARE_R2_ACCESS_KEY_ID": "access",
                "CLOUDFLARE_R2_SECRET_ACCESS_KEY": "secret",
                "CLOUDFLARE_ACCOUNT_ID": "id",
                "CLOUDFLARE_R2_REGION": "auto",
            }
        )
        account = load_config().account()
        assert account.s3_secret_access_key == "secret"
        config_home = tmp_path / "config-home"
        config_home.mkdir()
        (config_home / "cloudflare").mkdir()
        (config_home / "cloudflare" / "config.toml").write_text(
            "[accounts.default]\n"
            'account_id = "default-id"\n'
            'api_token = "default-token"\n',
            encoding="utf-8",
        )
        os.environ.pop("CLOUDFLARE_ACCOUNT_ID")
        os.environ["XDG_CONFIG_HOME"] = str(config_home)
        assert load_config().account().account_id == "default-id"
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_environment_overlay_preserves_file_account(tmp_path: Path) -> None:
    names = (
        "CLOUDFLARE",
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ACCOUNT",
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_R2_REGION",
        "AWS_REGION",
    )
    saved = {name: os.environ.get(name) for name in names}
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[accounts.customer]\n"
        'account_id = "file-account"\n'
        'api_token = "file-token"\n'
        "[accounts.customer.s3]\n"
        'region = "eu"\n',
        encoding="utf-8",
    )
    try:
        for name in names:
            os.environ.pop(name, None)
        os.environ.update(
            {
                "CLOUDFLARE": "environment-token",
                "CLOUDFLARE_ACCOUNT": "customer",
            }
        )
        account = load_config(config_path).account()
        assert account.account_id == "file-account"
        assert account.api_token == "environment-token"
        assert account.s3_region == "eu"
        os.environ["CLOUDFLARE_R2_REGION"] = "us"
        assert load_config(config_path).account().s3_region == "us"
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_client_failures_and_binary_response() -> None:
    instance, thread = server()
    try:
        client = CloudflareClient(
            AccountConfig("test", "id", "token"),
            f"http://127.0.0.1:{instance.server_port}",
        )
        assert client.request("GET", "/binary") == b"binary"
        assert client.request("GET", "binary") == b"binary"
        assert client.request("GET", "/empty") is None
        assert client.request("GET", "/binary", headers={"X-Test": "yes"}) == b"binary"
        assert Handler.request_headers["X-Test"] == "yes"
        assert (
            client.request(
                "GET", "/binary", headers={"Accept": "application/javascript"}
            )
            == b"binary"
        )
        assert Handler.request_headers["Accept"] == "application/javascript"
        assert (
            client.request("GET", "/binary", headers={"authorization": "Bearer forged"})
            == b"binary"
        )
        assert "authorization" not in Handler.request_headers
        assert Handler.request_headers["Authorization"] == "Bearer token"
        client.request("GET", "/zones?existing=yes", query={"page": 1})
        assert Handler.request_path == "/zones?existing=yes&page=1"
        client.request("GET", "/zones", query={"enabled": True, "tag": ["a", "b"]})
        assert Handler.request_path == "/zones?enabled=true&tag=a&tag=b"
        client.request(
            "GET",
            "/zones",
            query={"search": [{"field": "name", "op": "equals", "value": "x"}]},
        )
        assert Handler.request_path == (
            "/zones?search=%5B%7B%22field%22%3A%22name%22%2C%22op%22%3A%22equals%22%2C%22value%22%3A%22x%22%7D%5D"
        )
        client.request("GET", "/zones", query={"filter": {"name": "x"}})
        assert Handler.request_path == "/zones?filter=%7B%22name%22%3A%22x%22%7D"
        assert client.request(
            "POST", "/zones", body=b"raw", content_type="text/plain"
        ) == {"success": True}
        assert Handler.request_body == b"raw"
        assert Handler.request_headers["Content-Type"] == "text/plain"
        client.request("POST", "/zones", body="SELECT 1", content_type="text/plain")
        assert Handler.request_body == b"SELECT 1"
        with pytest.raises(ValueError, match="bytes or str"):
            client.request(
                "POST", "/zones", body={"query": "SELECT 1"}, content_type="text/plain"
            )
        client.request(
            "POST", "/zones", body=b"raw", headers={"content-type": "text/plain"}
        )
        assert Handler.request_headers["Content-Type"] == "text/plain"
        assert client.request(
            "GET",
            "/accounts/{account_id}/zones/{zone_id}",
            path_params={"zone_id": "zone id"},
        ) == {
            "success": True,
            "result": [{"id": "1", "name": "zone"}],
        }
        with pytest.raises(CloudflareError, match="invalid JSON"):
            client.request("GET", "/invalid")
        with pytest.raises(CloudflareError) as error:
            client.request("GET", "/error")
        assert error.value.status == 400
        with pytest.raises(CloudflareError) as invalid_error:
            client.request("GET", "/error-invalid")
        assert invalid_error.value.status == 400
        with pytest.raises(CloudflareError) as redirect_error:
            client.request("GET", "/redirect")
        assert redirect_error.value.status == 302
        with pytest.raises(CloudflareError) as text_error:
            client.request("GET", "/error-text")
        assert text_error.value.status == 500
    finally:
        instance.shutdown()
        thread.join()
    with pytest.raises(CloudflareError):
        CloudflareClient(
            AccountConfig("test", "id", "token"), "http://127.0.0.1:1"
        ).request("GET", "/")
    with pytest.raises(ValueError):
        CloudflareClient(
            AccountConfig("test", "id", "token"), "ftp://127.0.0.1"
        ).request("GET", "/")
    with pytest.raises(ValueError):
        CloudflareClient(
            AccountConfig("test", None, "token"), "http://127.0.0.1"
        ).request("GET", "/accounts/{account_id}")
    with pytest.raises(ValueError, match="relative"):
        CloudflareClient(
            AccountConfig("test", "id", "token"), "http://127.0.0.1"
        ).request("GET", "https://example.com/zones")


def test_cli_helpers_and_request(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _query(["page=2", "active=true"]) == {"page": "2", "active": "true"}
    assert _query(["tag=a", "tag=b"], repeat=True) == {"tag": ["a", "b"]}
    with pytest.raises(ValueError):
        _query(["invalid"])
    body_file = tmp_path / "body.json"
    body_file.write_text('{"name":"zone"}', encoding="utf-8")
    assert _body(Namespace(data=None, data_file=body_file, raw_file=None)) == {
        "name": "zone"
    }
    assert _body(Namespace(data='{"ok":true}', data_file=None, raw_file=None)) == {
        "ok": True
    }
    with pytest.raises(ValueError):
        _body(Namespace(data="{}", data_file=body_file, raw_file=None))
    raw_file = tmp_path / "worker.js"
    raw_file.write_bytes(b"export default {}")
    assert (
        _body(Namespace(data=None, data_file=None, raw_file=raw_file))
        == b"export default {}"
    )
    with pytest.raises(ValueError):
        _body(Namespace(data="{}", data_file=None, raw_file=raw_file))
    assert json.loads(format_output({"ok": True}, "json")) == {"ok": True}
    assert format_output({"ok": True}, "toon") == "ok: true"
    assert encode({"empty": []}) == "empty: []"
    assert encode({"items": [{"rows": [{"id": 1}, {"id": 2}], "name": "x"}]}) == (
        "items[1]:\n  - rows[2]{id}:\n      1\n      2\n    name: x"
    )
    assert encode([{1: "a"}, {1: "b"}]) == '[2]{"1"}:\n  a\n  b'
    assert encode({"my-key": "true", "version": "123"}) == (
        '"my-key": "true"\nversion: "123"'
    )
    assert encode({"emoji😀": "value"}) == '"emoji😀": value'
    assert encode({"controls": "\b\f\\b"}) == 'controls: "\\u0008\\u000c\\\\b"'
    assert encode({"quote": '"\r\t'}) == 'quote: "\\"\\r\\t"'
    with pytest.raises(ValueError, match="surrogate"):
        encode("bad\ud800")
    assert encode({"nan": float("nan"), "infinity": float("inf")}) == (
        "nan: null\ninfinity: null"
    )
    assert encode({"million": 1_000_000.0, "tiny": 1e-6, "negative_zero": -0.0}) == (
        "million: 1000000\ntiny: 0.000001\nnegative_zero: 0"
    )
    assert isinstance(run(Namespace(action="operations")), list)
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[accounts.one]\naccount_id = "id"\napi_token = "token"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unknown R2 command"):
        _run_r2(
            Namespace(
                config=config_path,
                account=None,
                timeout=30.0,
                r2_command="unknown",
            )
        )
    instance, thread = server()
    try:
        assert main(["--config", str(config_path), "accounts"]) == 0
        capsys.readouterr()
        assert (
            main(
                [
                    "--config",
                    str(config_path),
                    "request",
                    "GET",
                    "/zones",
                    "--base-url",
                    f"http://127.0.0.1:{instance.server_port}",
                    "--query",
                    "page=1",
                    "--path-param",
                    "zone_id=zone-id",
                    "--header",
                    "X-Test=yes",
                    "--format",
                    "toon",
                ]
            )
            == 0
        )
        binary_output = tmp_path / "response.bin"
        assert (
            main(
                [
                    "--config",
                    str(config_path),
                    "request",
                    "GET",
                    "/binary",
                    "--base-url",
                    f"http://127.0.0.1:{instance.server_port}",
                    "--output-file",
                    str(binary_output),
                ]
            )
            == 0
        )
        assert binary_output.read_bytes() == b"binary"
        assert (
            main(
                [
                    "--config",
                    str(config_path),
                    "request",
                    "GET",
                    "/binary",
                    "--base-url",
                    f"http://127.0.0.1:{instance.server_port}",
                ]
            )
            == 1
        )
        assert (
            main(
                [
                    "--config",
                    str(config_path),
                    "accounts",
                    "list-accounts",
                    "--base-url",
                    f"http://127.0.0.1:{instance.server_port}",
                    "--name",
                    "zone",
                ]
            )
            == 0
        )
        assert (
            main(
                [
                    "--config",
                    str(config_path),
                    "request",
                    "POST",
                    "/zones",
                    "--base-url",
                    f"http://127.0.0.1:{instance.server_port}",
                    "--data-file",
                    str(body_file),
                ]
            )
            == 0
        )
        assert (
            main(
                [
                    "--config",
                    str(config_path),
                    "request",
                    "GET",
                    "/zones",
                    "--data",
                    "{",
                ]
            )
            == 1
        )
    finally:
        instance.shutdown()
        thread.join()
    assert "cloudflare:" in capsys.readouterr().err


def test_toon_shapes() -> None:
    assert encode(None) == "null"
    assert encode({"message": "line1\nline2"}) == 'message: "line1\\nline2"'
    assert encode({}) == "{}"
    assert encode(1) == "1"
    assert encode(False) == "false"
    assert encode([]) == "[]"
    assert encode({"items": []}) == "items: []"
    assert encode([True, None, 2]) == "[3]: true,null,2"
    assert encode({"items": ["one", "two"]}) == "items[2]: one,two"
    assert encode({"items": [{"id": 1}, {"id": 2}]}) == "items[2]{id}:\n  1\n  2"
    assert encode({"items": [{"id": 1}, "two"]}) == "items[2]:\n  - id: 1\n  - two"
    assert encode({"items": [{}, {"id": 1, "name": "one"}]}) == (
        "items[2]:\n  -\n  - id: 1\n    name: one"
    )
    assert encode({"items": [[]]}) == "items[1]:\n  - [0]:"
    assert encode({"items": [[1, 2]]}) == "items[1]:\n  - [2]: 1,2"
    assert encode({"items": [[{"id": 1}]]}) == ("items[1]:\n  - [1]:\n    - id: 1")
    assert encode({"items": [("one", "two")]}) == (
        "items[1]:\n  -\n    \"('one', 'two')\""
    )
    assert encode({"users": {"alice": {"age": 30}, "bob": {"age": 25}}}) == (
        "users[2:]{age}:\n  alice: 30\n  bob: 25"
    )
    assert encode({"nested": {"value": "a:b"}}) == 'nested:\n  value: "a:b"'
    assert encode({"a b": "true"}) == '"a b": "true"'
    assert encode(float("nan")) == "null"
    assert encode(float("inf")) == "null"
    assert encode(1e21) == "1e+21"
    assert _field(None) == ""
