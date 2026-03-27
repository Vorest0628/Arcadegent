"""Focused tests for FastMCP HTTP discovery and AMap MCP config building."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.client.transports import StreamableHttpTransport
from fastapi.testclient import TestClient
import httpx

from app.agent.tools.mcp import (
    MCPServerConfig,
    MCPToolGateway,
    build_amap_mcp_server_config,
    build_mcp_server_configs,
)


def _build_http_transport(app: object, *, path: str = "/mcp") -> StreamableHttpTransport:
    def _factory(
        *,
        headers: dict[str, str] | None = None,
        auth: httpx.Auth | None = None,
        follow_redirects: bool = True,
        timeout: httpx.Timeout | None = None,
        **_: object,
    ) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            headers=headers,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
        )

    return StreamableHttpTransport(
        url=f"http://testserver{path}",
        httpx_client_factory=_factory,
    )


def test_build_amap_mcp_server_config_uses_http_url() -> None:
    config = build_amap_mcp_server_config(
        enabled=True,
        base_url="https://mcp.amap.com/mcp",
        api_key="secret-key",
        timeout_seconds=9,
        route_tool_name="maps_direction_walking",
    )

    assert config.source == "https://mcp.amap.com/mcp?key=secret-key"
    assert config.url == "https://mcp.amap.com/mcp?key=secret-key"
    assert config.source_type == "http"
    assert config.route_tool_name == "maps_direction_walking"


def test_build_amap_mcp_server_config_accepts_local_script(tmp_path: Path) -> None:
    script_path = tmp_path / "mock_server.py"
    script_path.write_text("print('placeholder')\n", encoding="utf-8")

    config = build_amap_mcp_server_config(
        enabled=True,
        base_url=str(script_path),
        api_key="",
        timeout_seconds=9,
        route_tool_name=None,
    )

    assert config.source == str(script_path)
    assert config.url == str(script_path)
    assert config.source_type == "script"


def test_build_mcp_server_configs_accepts_standard_remote_json() -> None:
    configs = build_mcp_server_configs(
        raw_config={
            "mcpServers": {
                "fetch": {
                    "type": "sse",
                    "url": "https://mcp.api-inference.modelscope.net/",
                    "headers": {"X-Token": "secret"},
                }
            }
        },
        default_timeout_seconds=7,
    )

    assert len(configs) == 1
    config = configs[0]
    assert config.name == "fetch"
    assert config.enabled is True
    assert config.url == "https://mcp.api-inference.modelscope.net/"
    assert config.timeout_seconds == 7
    assert config.source_type == "sse"
    assert config.source["mcpServers"]["fetch"]["transport"] == "sse"


def test_build_mcp_server_configs_accepts_standard_stdio_json() -> None:
    configs = build_mcp_server_configs(
        raw_config={
            "mcpServers": {
                "assistant": {
                    "command": "python",
                    "args": ["./assistant_server.py"],
                    "env": {"LOG_LEVEL": "INFO"},
                    "cwd": "/tmp",
                    "enabled": False,
                    "route_tool_name": "assistant_answer",
                }
            }
        },
        default_timeout_seconds=11,
    )

    assert len(configs) == 1
    config = configs[0]
    assert config.name == "assistant"
    assert config.enabled is False
    assert config.timeout_seconds == 11
    assert config.route_tool_name == "assistant_answer"
    assert config.source_type == "stdio"
    assert config.source["mcpServers"]["assistant"]["command"] == "python"
    assert config.source["mcpServers"]["assistant"]["args"] == ["./assistant_server.py"]
    assert config.source["mcpServers"]["assistant"]["env"] == {"LOG_LEVEL": "INFO"}


def test_mcp_gateway_discovers_and_executes_http_tools() -> None:
    mcp = FastMCP("HTTP MCP")

    @mcp.tool(name="maps_direction_walking", description="步行路径规划，输入 origin 和 destination，输出 paths。")
    def maps_direction_walking(origin: str, destination: str) -> dict[str, object]:
        return {
            "origin": origin,
            "destination": destination,
            "paths": [
                {
                    "distance": 2468,
                    "duration": 1200,
                    "steps": [
                        {
                            "instruction": "walk forward",
                            "polyline": "116.3,39.9;116.31,39.901",
                        }
                    ],
                }
            ],
        }

    app = mcp.http_app(path="/mcp", transport="http")
    with TestClient(app):
        gateway = MCPToolGateway(
            servers=[
                MCPServerConfig(
                    name="amap",
                    enabled=True,
                    source=_build_http_transport(app),
                    url="http://testserver/mcp",
                    timeout_seconds=3,
                    route_tool_name="maps_direction_walking",
                    source_type="http",
                )
            ]
        )

        asyncio.run(gateway.refresh())
        definitions = asyncio.run(gateway.build_tool_definitions(allowed_tools=["mcp__*"], strict=True))
        names = [item["function"]["name"] for item in definitions]
        assert "mcp__amap__maps_direction_walking" in names

        result = asyncio.run(
            gateway.execute(
                tool_name="mcp__amap__maps_direction_walking",
                raw_arguments={"origin": "116.3,39.9", "destination": "116.4,39.91"},
            )
        )

        assert result.status == "completed"
        assert result.output["server"] == "amap"
        assert result.output["tool"] == "maps_direction_walking"
        assert result.output["route"]["distance_m"] == 2468
        assert result.output["route"]["duration_s"] == 1200
        assert gateway.health()["servers"]["amap"]["source_type"] == "http"
