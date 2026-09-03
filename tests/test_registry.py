from __future__ import annotations

import json
import re
from argparse import ArgumentParser, _SubParsersAction
from pathlib import Path

import pytest
from test_smoke import Handler, server

from cloudflare_cli import (
    AccountConfig,
    CloudflareClient,
    Operation,
    Parameter,
    operation,
    operations,
)
from cloudflare_cli.cli_catalog import _add_operation_parameters, _unique_command
from cloudflare_cli.cli_parser import (
    build_parser,
)
from cloudflare_cli.registry import method_name


def test_registry_contains_all_openapi_operations() -> None:
    items = operations()
    assert len(items) == 3407
    assert all(
        set(re.findall(r"{([^}]+)}", item.path))
        == {
            parameter.name
            for parameter in item.parameters
            if parameter.location == "path"
        }
        for item in items
    )
    assert isinstance(items[0], Operation)
    assert operation("accounts-list-accounts") == items[0]
    assert operation("accounts-list-accounts").parameters[0].name == "name"
    assert operation("zones-get").parameters[2].array is True
    assert (
        next(
            parameter
            for parameter in operation("get_EventListGet").parameters
            if parameter.name == "search"
        ).structured
        is True
    )
    assert operation("create_app").request_body_required is True
    assert (
        next(
            parameter
            for parameter in operation("get_EventRelationships").parameters
            if parameter.name == "relationshipTypes"
        ).array
        is True
    )
    assert method_name("accounts-list-accounts") == "accounts_list_accounts"
    with pytest.raises(ValueError):
        operation("not-an-operation")


def test_operation_method_calls_local_server() -> None:
    instance, thread = server()
    try:
        client = CloudflareClient(
            AccountConfig("test", "account", "token"),
            f"http://127.0.0.1:{instance.server_port}",
        )
        result = client.accounts_list_accounts(name="zone", page=2)
        assert result["success"] is True
        assert Handler.request_path == "/accounts?name=zone&page=2"
        client.analytics_engine_sql_query_get(query="select")
        assert (
            Handler.request_path
            == "/accounts/account/analytics_engine/sql?query=select"
        )
        with pytest.raises(ValueError, match="query"):
            client.analytics_engine_sql_query_get(query={"query": None})
        client.accounts_list_accounts(name=None)
        assert Handler.request_path == "/accounts"
        client.accounts_list_accounts(query={"page": [1, 2]})
        assert Handler.request_path == "/accounts?page=1&page=2"
        client.zones_get(type=["public", "private"])
        assert Handler.request_path == "/zones?type=public%2Cprivate"
        client.zones_get(type=[])
        assert Handler.request_path == "/zones"
        client.get_EventListGet(
            search=[{"field": "name", "op": "equals", "value": "x"}]
        )
        assert Handler.request_path == (
            "/accounts/account/cloudforce-one/events?search=%5B%7B%22field%22%3A%22name%22%2C%22op%22%3A%22equals%22%2C%22value%22%3A%22x%22%7D%5D"
        )
        client.passive_dns_by_ip_get_passive_dns_by_ip(
            start_end_params={"start": "2024-01-01", "end": "2024-01-02"}
        )
        assert Handler.request_path == (
            "/accounts/account/intel/dns?start=2024-01-01&end=2024-01-02"
        )
        assert "accounts_list_accounts" in dir(client)
        image_result = client.get_ImageList()
        assert image_result["success"] is True
        assert Handler.request_path == "/accounts/account/v1/images"
        client.get_ImageGet(path_params={"accountId": None, "imageId": "image"})
        assert Handler.request_path == "/accounts/account/v1/images/image"
        client.access_applications_list_access_applications(page=2)
        assert Handler.request_path == "/accounts/account/access/apps?page=2"
        client.getBuildByUuid(build_uuid="build")
        assert Handler.request_path == "/accounts/account/builds/builds/build"
        client.namespace_worker_script_delete_worker(
            dispatch_namespace="ns", script_name="demo"
        )
        assert Handler.request_path == (
            "/accounts/account/workers/dispatch/namespaces/ns/scripts/demo"
        )
        client.brapi_get_DevtoolsPage(
            session_id="session",
            target_id="target",
            **{"cf-brapi-guardrails": "guard"},
        )
        assert Handler.request_headers["cf-brapi-guardrails"] == "guard"
        with pytest.raises(ValueError):
            client.accounts_list_accounts(unknown="value")
        with pytest.raises(ValueError):
            client.worker_routes_update_route(
                zone_id="zone", route_id="route", body=None
            )
        with pytest.raises(ValueError):
            client.worker_routes_update_route(route_id="route", body={})
        missing_method = "no_such_method"
        with pytest.raises(AttributeError):
            getattr(client, missing_method)
    finally:
        instance.shutdown()
        thread.join()


def test_generated_registry_is_packaged() -> None:
    registry_path = Path(__file__).parents[1] / "src/cloudflare_cli/registry.json"
    document = json.loads(registry_path.read_text(encoding="utf-8"))
    assert document["openapi"] == "3.0.3"
    assert len(document["operations"]) == 3407


def test_operation_cli_parameter_name_collision() -> None:
    definition = Operation(
        "test",
        "GET",
        "/",
        "",
        (Parameter("format", "query", False), Parameter("format", "query", False)),
        False,
        False,
    )
    parser = ArgumentParser(add_help=False)
    specs = _add_operation_parameters(parser, definition)
    assert len(specs) == 2


def test_cli_groups_every_catalog_operation() -> None:
    parser = build_parser()
    operation_ids: list[str] = []

    def visit(current: ArgumentParser) -> None:
        for action in current._actions:
            if not isinstance(action, _SubParsersAction):
                continue
            for child in action.choices.values():
                if child._defaults.get("action") == "operation":
                    operation_ids.append(child._defaults["operation_id"])
                visit(child)

    visit(parser)
    assert set(operation_ids) == {item.operation_id for item in operations()}
    assert _unique_command("command", "GET", {"command", "command-get"}) == (
        "command-get-2"
    )
    image_args = parser.parse_args(["images", "get-image-list", "--account-id", "id"])
    assert image_args._operation_parameter_0 == "id"
    zones_args = parser.parse_args(
        ["zones", "get", "--type", "public", "--type", "private"]
    )
    assert zones_args._operation_parameter_2 == ["public", "private"]
    relationship_args = parser.parse_args(
        [
            "cloudforce-one",
            "get-event-relationships",
            "--relationship-types",
            "a",
            "--relationship-types",
            "b",
        ]
    )
    assert relationship_args._operation_parameter_4 == ["a", "b"]
