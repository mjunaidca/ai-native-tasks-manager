"""End-to-end: launch the server as a real subprocess and speak MCP over HTTP.

Uses the official MCP Python SDK's streamable-http client to verify the
on-the-wire envelope is correct.
"""

import asyncio
import os
import socket
import subprocess
import sys
import time

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    port = _free_port()
    env = {
        **os.environ,
        "TASKS_MCP_HOST": "127.0.0.1",
        "TASKS_MCP_PORT": str(port),
        "TASKS_MCP_LOG_LEVEL": "WARNING",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "tasks_mcp.server"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    url = f"http://127.0.0.1:{port}/mcp"
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.1)
    else:
        proc.kill()
        out, err = proc.communicate(timeout=5)
        raise RuntimeError(f"server never bound: {err.decode()}")
    try:
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


async def _list_tool_names(url: str) -> set[str]:
    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return {t.name for t in tools.tools}


async def _call_tool(url: str, name: str, params: dict) -> dict:
    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, {"params": params})
            # The wire protocol always includes a content block; prefer it.
            import json as _json

            if result.content:
                first = result.content[0]
                if hasattr(first, "text"):
                    return _json.loads(first.text)
            if result.structuredContent and "result" in result.structuredContent:
                return result.structuredContent["result"]
            return result.structuredContent or {}


def test_e2e_list_tools(live_server: str) -> None:
    names = asyncio.run(_list_tool_names(live_server))
    assert names == {
        "capture_task",
        "review_tasks",
        "modify_task",
        "resolve_task",
        "remove_task",
    }


def test_e2e_capture_review_remove(live_server: str) -> None:
    cap = asyncio.run(_call_tool(live_server, "capture_task", {"title": "live!"}))
    assert cap["status"] == "pending"
    tid = cap["id"]

    review = asyncio.run(_call_tool(live_server, "review_tasks", {"filter": "open"}))
    assert any(t["id"] == tid for t in review["items"])

    rm = asyncio.run(_call_tool(live_server, "remove_task", {"id": tid}))
    assert rm == {"id": tid, "removed": True}
