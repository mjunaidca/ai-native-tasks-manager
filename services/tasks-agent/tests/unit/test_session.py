"""Sanity check: SQLiteSession round-trips items in-process."""

from __future__ import annotations

import pytest
from agents import SQLiteSession


@pytest.mark.asyncio
async def test_session_round_trips_items() -> None:
    session = SQLiteSession("test-session")

    await session.add_items(
        [
            {"role": "user", "content": "remember teal"},
            {"role": "assistant", "content": "noted"},
        ]
    )

    items = await session.get_items()
    assert len(items) == 2
    assert items[0]["content"] == "remember teal"
    assert items[1]["content"] == "noted"


@pytest.mark.asyncio
async def test_session_clear_wipes_history() -> None:
    session = SQLiteSession("test-session-clear")
    await session.add_items([{"role": "user", "content": "hi"}])
    await session.clear_session()
    assert await session.get_items() == []
