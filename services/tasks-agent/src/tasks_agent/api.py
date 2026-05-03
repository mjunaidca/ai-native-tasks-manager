"""FastAPI HTTP interface for the Tasks Manager Agent."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Annotated

from agents import RunConfig, Runner, SQLiteSession
from agents.sandbox import Manifest, SandboxRunConfig
from agents.sandbox.sandboxes.unix_local import UnixLocalSandboxClient
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from tasks_agent.agent import build_agent, build_mcp_server
from tasks_agent.cli import _configure_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()
    _configure_tracing()

    mcp_server = build_mcp_server()
    await mcp_server.__aenter__()
    try:
        agent = build_agent(mcp_server)
        run_config = RunConfig(
            sandbox=SandboxRunConfig(
                client=UnixLocalSandboxClient(),
                manifest=Manifest(root="/workspace", entries={}),
            )
        )
        app.state.agent = agent
        app.state.run_config = run_config
        app.state.sessions = {}
        yield
    finally:
        await mcp_server.__aexit__(None, None, None)


app = FastAPI(title="Tasks Manager Agent API", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = "default"


class ChatResponse(BaseModel):
    session_id: str
    reply: str


def _session(request: Request, session_id: str) -> SQLiteSession:
    sessions: dict[str, SQLiteSession] = request.app.state.sessions
    session = sessions.get(session_id)
    if session is None:
        session = SQLiteSession(f"tasks-agent-api:{session_id}")
        sessions[session_id] = session
    return session


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat")
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    session = _session(request, payload.session_id)
    result = await Runner.run(
        request.app.state.agent,
        payload.message,
        run_config=request.app.state.run_config,
        session=session,
    )
    return ChatResponse(session_id=payload.session_id, reply=str(result.final_output))
