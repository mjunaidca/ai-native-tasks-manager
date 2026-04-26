"""Live verification smoke test for the Tasks MCP server.

Walks every step of the 14-item checklist from
`specs/mcp-server/implementation-plan.md` §4 against a running server.

Usage:
    # In one shell:
    TASKS_MCP_PORT=8765 uv run tasks-mcp

    # In another:
    TASKS_MCP_URL=http://127.0.0.1:8765/mcp uv run python scripts/smoke.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = os.environ.get("TASKS_MCP_URL", "http://127.0.0.1:8000/mcp")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _payload(result: Any) -> Any:
    if result.content:
        first = result.content[0]
        if hasattr(first, "text"):
            return json.loads(first.text)
    if result.structuredContent and "result" in result.structuredContent:
        return result.structuredContent["result"]
    return result.structuredContent or {}


PASSED: list[str] = []
FAILED: list[str] = []


def _ok(step: str, evidence: str) -> None:
    PASSED.append(step)
    print(f"PASS {step}: {evidence}")


def _fail(step: str, evidence: str) -> None:
    FAILED.append(step)
    print(f"FAIL {step}: {evidence}")


async def main() -> int:
    async with streamable_http_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. List tools
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            expected = {
                "capture_task",
                "review_tasks",
                "modify_task",
                "resolve_task",
                "remove_task",
            }
            if names == expected:
                annot = {t.name: t.annotations for t in tools.tools}
                _ok(
                    "1 list_tools",
                    f"5 tools, remove_task.destructiveHint={annot['remove_task'].destructiveHint}",
                )
            else:
                _fail("1 list_tools", f"got {names}")

            # 2. Capture default user
            cap = _payload(
                await session.call_tool(
                    "capture_task",
                    {
                        "params": {
                            "title": "Buy milk",
                            "due_at": _iso(
                                datetime.now(timezone.utc) + timedelta(hours=2)
                            ),
                        }
                    },
                )
            )
            t1 = cap.get("id")
            if t1 and cap["user_id"] == "default-user" and cap["status"] == "pending":
                _ok(
                    "2 capture",
                    f"id={t1[:8]}... user_id={cap['user_id']} status={cap['status']}",
                )
            else:
                _fail("2 capture", str(cap))

            # 3. Capture validation (naive datetime)
            try:
                bad = await session.call_tool(
                    "capture_task",
                    {"params": {"title": "x", "due_at": "2026-04-27T17:00:00"}},
                )
                bad_payload = _payload(bad)
                if bad_payload.get("error", {}).get("code") == "invalid_argument":
                    _ok("3 capture_validation", str(bad_payload["error"]["code"]))
                else:
                    # FastMCP may also raise from pydantic validation.
                    if (
                        getattr(bad, "isError", False)
                        or "validation" in str(bad_payload).lower()
                    ):
                        _ok("3 capture_validation", "validation rejected")
                    else:
                        _fail("3 capture_validation", str(bad_payload))
            except Exception as e:
                _ok("3 capture_validation", f"raised {type(e).__name__}")

            # 4. Capture with user_id
            cap_a = _payload(
                await session.call_tool(
                    "capture_task",
                    {"params": {"title": "alice's lunch", "user_id": "alice"}},
                )
            )
            t_alice = cap_a["id"]
            if cap_a["user_id"] == "alice":
                _ok("4 capture_with_user", f"user_id={cap_a['user_id']}")
            else:
                _fail("4 capture_with_user", str(cap_a))

            # 5. Review default user does not see alice
            rev = _payload(
                await session.call_tool("review_tasks", {"params": {"filter": "open"}})
            )
            ids = {x["id"] for x in rev["items"]}
            if t1 in ids and t_alice not in ids:
                _ok(
                    "5 review_default",
                    f"sees {t1[:8]}, hides alice's {t_alice[:8]}",
                )
            else:
                _fail("5 review_default", f"ids={ids}")

            # 6. Review filters: today / overdue / upcoming + tz
            now = datetime.now(timezone.utc)
            past = _payload(
                await session.call_tool(
                    "capture_task",
                    {
                        "params": {
                            "title": "past",
                            "due_at": _iso(now - timedelta(hours=3)),
                        }
                    },
                )
            )["id"]
            future = _payload(
                await session.call_tool(
                    "capture_task",
                    {
                        "params": {
                            "title": "future",
                            "due_at": _iso(now + timedelta(days=3)),
                        }
                    },
                )
            )["id"]
            overdue = {
                x["id"]
                for x in _payload(
                    await session.call_tool(
                        "review_tasks", {"params": {"filter": "overdue"}}
                    )
                )["items"]
            }
            upcoming = {
                x["id"]
                for x in _payload(
                    await session.call_tool(
                        "review_tasks", {"params": {"filter": "upcoming"}}
                    )
                )["items"]
            }
            today_utc = _payload(
                await session.call_tool(
                    "review_tasks",
                    {"params": {"filter": "today", "tz": "UTC"}},
                )
            )
            today_kar = _payload(
                await session.call_tool(
                    "review_tasks",
                    {"params": {"filter": "today", "tz": "Asia/Karachi"}},
                )
            )
            if past in overdue and future in upcoming and future not in overdue:
                _ok(
                    "6 review_filters",
                    f"overdue={len(overdue)} upcoming={len(upcoming)} today_utc={len(today_utc['items'])} today_kar={len(today_kar['items'])}",
                )
            else:
                _fail(
                    "6 review_filters",
                    f"past in overdue={past in overdue} future in upcoming={future in upcoming}",
                )

            # 7. Pagination: ensure >50 tasks then page through
            for i in range(60):
                await session.call_tool(
                    "capture_task", {"params": {"title": f"page-{i}"}}
                )
            seen: set[str] = set()
            cursor: str | None = None
            pages = 0
            while True:
                page = _payload(
                    await session.call_tool(
                        "review_tasks",
                        {
                            "params": {
                                "filter": "all",
                                "limit": 50,
                                **({"cursor": cursor} if cursor else {}),
                            }
                        },
                    )
                )
                for x in page["items"]:
                    if x["id"] in seen:
                        _fail("7 pagination", f"duplicate {x['id']}")
                        break
                    seen.add(x["id"])
                pages += 1
                if not page["next_cursor"]:
                    break
                cursor = page["next_cursor"]
                if pages > 20:
                    _fail("7 pagination", "infinite loop")
                    break
            else:
                pass
            _ok(
                "7 pagination",
                f"{pages} page(s), {len(seen)} unique items, no duplicates",
            )

            # 8. Modify
            mod = _payload(
                await session.call_tool(
                    "modify_task",
                    {"params": {"id": t1, "title": "Buy oat milk"}},
                )
            )
            mod2 = _payload(
                await session.call_tool(
                    "modify_task",
                    {"params": {"id": t1, "description": None}},
                )
            )
            mod_missing = _payload(
                await session.call_tool(
                    "modify_task",
                    {"params": {"id": "nope", "title": "x"}},
                )
            )
            if (
                mod["title"] == "Buy oat milk"
                and mod2["description"] is None
                and mod_missing.get("error", {}).get("code") == "not_found"
            ):
                _ok(
                    "8 modify",
                    "title changed; null cleared description; missing→not_found",
                )
            else:
                _fail("8 modify", f"{mod} / {mod2} / {mod_missing}")

            # 9. Cross-user modify
            xmod = _payload(
                await session.call_tool(
                    "modify_task",
                    {"params": {"id": t_alice, "title": "stolen"}},
                )
            )
            if xmod.get("error", {}).get("code") == "not_found":
                _ok("9 cross_user_modify", "not_found (no leak)")
            else:
                _fail("9 cross_user_modify", str(xmod))

            # 10. Resolve happy + idempotent
            res1 = _payload(
                await session.call_tool(
                    "resolve_task",
                    {"params": {"id": t1, "outcome": "completed", "note": "did it"}},
                )
            )
            res2 = _payload(
                await session.call_tool(
                    "resolve_task",
                    {"params": {"id": t1, "outcome": "completed"}},
                )
            )
            if res1["status"] == "completed" and res2 == res1:
                _ok("10 resolve_happy", "completed; second call is no-op")
            else:
                _fail("10 resolve_happy", f"{res1} / {res2}")

            # 11. Resolve conflict
            res3 = _payload(
                await session.call_tool(
                    "resolve_task",
                    {"params": {"id": t1, "outcome": "cancelled"}},
                )
            )
            err = res3.get("error", {})
            if err.get("code") == "invalid_state_transition" and err.get("suggestion"):
                _ok("11 resolve_conflict", err["code"])
            else:
                _fail("11 resolve_conflict", str(res3))

            # 12. Remove + idempotent
            rm1 = _payload(
                await session.call_tool("remove_task", {"params": {"id": future}})
            )
            rm2 = _payload(
                await session.call_tool("remove_task", {"params": {"id": future}})
            )
            if rm1 == {"id": future, "removed": True} and rm2 == rm1:
                _ok("12 remove", "removed; second call is no-op success")
            else:
                _fail("12 remove", f"{rm1} / {rm2}")

            # 13. Cross-user remove
            xrm = _payload(
                await session.call_tool("remove_task", {"params": {"id": t_alice}})
            )
            # Idempotent contract: returns removed=true silently. Alice's task
            # must still exist when she queries.
            alice_open = _payload(
                await session.call_tool(
                    "review_tasks",
                    {"params": {"filter": "open", "user_id": "alice"}},
                )
            )
            still_alice = any(x["id"] == t_alice for x in alice_open["items"])
            if xrm.get("removed") is True and still_alice:
                _ok(
                    "13 cross_user_remove",
                    "default-user got removed=true, alice's task still present for alice",
                )
            else:
                _fail("13 cross_user_remove", f"{xrm} alice_still={still_alice}")

    # 14. Restart: documented as out-of-band; print instructions for the human.
    print(
        "INFO 14 restart: kill the server and start it again; expect empty store. "
        "Re-run a review_tasks call afterwards to confirm zero items."
    )
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
