"""CLI entry point for the Tasks Manager Agent (Step 1, SandboxAgent)."""

from __future__ import annotations

import asyncio
import os
import sys

from agents import (
    RunConfig,
    Runner,
    SQLiteSession,
    set_tracing_disabled,
    set_tracing_export_api_key,
)
from agents.sandbox import Manifest, SandboxRunConfig
from agents.sandbox.sandboxes.unix_local import UnixLocalSandboxClient
from dotenv import load_dotenv

from tasks_agent.agent import build_agent, build_mcp_server


def _configure_tracing() -> bool:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        set_tracing_disabled(True)
        return False
    set_tracing_export_api_key(key)
    return True


async def _run_chat() -> None:
    sandbox = SandboxRunConfig(
        client=UnixLocalSandboxClient(),
        manifest=Manifest(root="/workspace", entries={}),
    )
    run_config = RunConfig(sandbox=sandbox)
    # In-memory SQLite — fresh history each process. Swap to a persistent
    # backend (Redis / SQLAlchemy) when an HTTP/UI surface lands.
    session = SQLiteSession("tasks-agent-cli")

    async with build_mcp_server() as mcp_server:
        agent = build_agent(mcp_server)
        while True:
            try:
                user_input = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not user_input:
                continue
            try:
                result = await Runner.run(
                    agent, user_input, run_config=run_config, session=session
                )
            except Exception as exc:
                print(f"[error] {exc}", file=sys.stderr)
                continue
            print(f"agent> {result.final_output}")


def main() -> None:
    load_dotenv()
    tracing_on = _configure_tracing()
    provider = os.environ.get("TASKS_AGENT_PROVIDER", "gemini")
    mcp_url = os.environ.get("TASKS_MCP_URL", "http://127.0.0.1:8000/mcp")
    print(
        f"Tasks Manager Agent ready (sandbox=unix-local, provider={provider}, "
        f"mcp={mcp_url}, tracing={'on' if tracing_on else 'off'}). Ctrl-D to exit."
    )
    asyncio.run(_run_chat())
