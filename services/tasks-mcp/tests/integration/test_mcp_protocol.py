"""Integration tests: exercise the FastMCP server via its in-memory client API.

We boot the server with stateless streamable-http settings, but route
tool calls through the FastMCP `call_tool` API which exercises the same
registration and validation paths used by the protocol layer.
"""

import json

import pytest

from tasks_mcp.server import STORE, build_mcp


@pytest.fixture(autouse=True)
def clear_store() -> None:
    STORE.clear()


@pytest.fixture()
def mcp_server():
    return build_mcp()


@pytest.mark.asyncio
async def test_list_tools(mcp_server) -> None:
    tools = await mcp_server.list_tools()
    names = {t.name for t in tools}
    assert names == {
        "capture_task",
        "review_tasks",
        "modify_task",
        "resolve_task",
        "remove_task",
    }
    by_name = {t.name: t for t in tools}
    assert by_name["remove_task"].annotations.destructiveHint is True
    assert by_name["review_tasks"].annotations.readOnlyHint is True
    assert by_name["capture_task"].annotations.idempotentHint is False


def _payload(result):
    # FastMCP returns (content_blocks, structured_output). When the tool
    # returns a non-dict (e.g. a Pydantic model), FastMCP wraps the JSON
    # under a "result" key in structured_output. The raw JSON is also in
    # the text content block — prefer that for a faithful view of what the
    # client receives.
    blocks, structured = result
    if blocks and getattr(blocks[0], "text", None):
        return json.loads(blocks[0].text)
    if structured is not None and "result" in structured:
        return structured["result"]
    return structured


@pytest.mark.asyncio
async def test_capture_then_review_open(mcp_server) -> None:
    cap = await mcp_server.call_tool("capture_task", {"params": {"title": "Buy milk"}})
    task = _payload(cap)
    assert task["status"] == "pending"
    assert task["user_id"] == "default-user"

    review = await mcp_server.call_tool("review_tasks", {"params": {"filter": "open"}})
    out = _payload(review)
    assert any(t["id"] == task["id"] for t in out["items"])


@pytest.mark.asyncio
async def test_capture_naive_datetime_returns_validation_error(mcp_server) -> None:
    # Pydantic regex rejects this before the tool body runs; FastMCP raises.
    with pytest.raises(Exception):
        await mcp_server.call_tool(
            "capture_task",
            {"params": {"title": "x", "due_at": "2026-04-27T17:00:00"}},
        )


@pytest.mark.asyncio
async def test_cross_user_modify_returns_not_found(mcp_server) -> None:
    cap = await mcp_server.call_tool(
        "capture_task", {"params": {"title": "alice's", "user_id": "alice"}}
    )
    tid = _payload(cap)["id"]
    res = await mcp_server.call_tool(
        "modify_task",
        {"params": {"id": tid, "title": "stolen"}},  # default-user
    )
    body = _payload(res)
    assert body["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_resolve_idempotent_then_conflict(mcp_server) -> None:
    cap = await mcp_server.call_tool("capture_task", {"params": {"title": "x"}})
    tid = _payload(cap)["id"]
    a = _payload(
        await mcp_server.call_tool(
            "resolve_task", {"params": {"id": tid, "outcome": "completed"}}
        )
    )
    b = _payload(
        await mcp_server.call_tool(
            "resolve_task", {"params": {"id": tid, "outcome": "completed"}}
        )
    )
    assert a == b
    conflict = _payload(
        await mcp_server.call_tool(
            "resolve_task", {"params": {"id": tid, "outcome": "cancelled"}}
        )
    )
    assert conflict["error"]["code"] == "invalid_state_transition"


@pytest.mark.asyncio
async def test_remove_idempotent(mcp_server) -> None:
    cap = await mcp_server.call_tool("capture_task", {"params": {"title": "x"}})
    tid = _payload(cap)["id"]
    a = _payload(await mcp_server.call_tool("remove_task", {"params": {"id": tid}}))
    b = _payload(await mcp_server.call_tool("remove_task", {"params": {"id": tid}}))
    assert a == {"id": tid, "removed": True}
    assert b == {"id": tid, "removed": True}
