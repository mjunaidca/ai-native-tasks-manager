"""Tasks Manager Agent — Step 3: SandboxAgent + Tasks MCP."""

from __future__ import annotations

import os

from agents.extensions.models.litellm_model import LitellmModel
from agents.mcp import MCPServerStreamableHttp
from agents.sandbox import SandboxAgent

INSTRUCTIONS = """\
You are the Tasks Manager Agent. You help the user manage tasks
(capture, review, modify, resolve, remove) by calling the Tasks MCP
tools. Rules:

- Always operate as user_id="default-user" unless the user explicitly
  names another owner. Pass user_id on every MCP call.
- Times must be UTC ISO-8601 with a trailing "Z" (e.g.
  "2026-05-03T17:00:00Z"). If the user gives a local time without a
  timezone, ask them to confirm UTC before proceeding.
- For "show me my tasks", "what's due today", "overdue", "upcoming",
  call review_tasks with the right filter.
- For destructive actions (remove_task, or resolving as cancelled),
  echo what you're about to do before calling, then proceed.
- After every successful mutation, briefly confirm what changed (id +
  title).
- If a tool returns an error, report it plainly; do not retry blindly.
"""


def _model() -> LitellmModel | str:
    provider = os.environ.get("TASKS_AGENT_PROVIDER", "gemini").lower()
    if provider == "gemini":
        api_key = os.environ["GEMINI_API_KEY"]
        model_name = os.environ.get(
            "TASKS_AGENT_GEMINI_MODEL", "gemini-3.1-flash-lite-preview"
        )
        return LitellmModel(model=f"gemini/{model_name}", api_key=api_key)
    if provider == "openai":
        return os.environ.get("TASKS_AGENT_OPENAI_MODEL", "gpt-4.1-mini")
    raise RuntimeError(f"Unknown TASKS_AGENT_PROVIDER={provider!r}")


def build_mcp_server() -> MCPServerStreamableHttp:
    url = os.environ.get("TASKS_MCP_URL", "http://127.0.0.1:8000/mcp")
    return MCPServerStreamableHttp(
        name="Tasks MCP",
        params={"url": url, "timeout": 10},
        cache_tools_list=True,
        max_retry_attempts=3,
    )


def build_agent(mcp_server: MCPServerStreamableHttp) -> SandboxAgent:
    # capabilities=[] avoids hosted/grammar tools (Responses-API only).
    # Gemini via LiteLLM speaks ChatCompletions; sandbox runtime still applies.
    return SandboxAgent(
        name="Tasks Manager",
        instructions=INSTRUCTIONS,
        model=_model(),
        capabilities=[],
        mcp_servers=[mcp_server],
    )
