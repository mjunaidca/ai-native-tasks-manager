import logging
import os

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from tasks_mcp import tools as toolimpl
from tasks_mcp.errors import ToolError
from tasks_mcp.models import (
    CaptureTaskInput,
    ModifyTaskInput,
    RemoveTaskInput,
    RemoveTaskOutput,
    ResolveTaskInput,
    ReviewTasksInput,
    ReviewTasksOutput,
    Task,
)
from tasks_mcp.store import TaskStore

LOG = logging.getLogger("tasks_mcp")
STORE = TaskStore()


def build_mcp() -> FastMCP:
    """Build the FastMCP app with the 5 task tools registered."""
    mcp = FastMCP(
        "tasks_mcp",
        stateless_http=True,
        json_response=True,
        host=os.environ.get("TASKS_MCP_HOST", "0.0.0.0"),
        port=int(os.environ.get("TASKS_MCP_PORT", "8000")),
    )

    def _wrap_error(e: ToolError) -> dict:
        env = e.envelope()
        LOG.info("tool error code=%s message=%s", e.code.value, e.message)
        return env

    @mcp.tool(
        name="capture_task",
        annotations=ToolAnnotations(
            title="Capture a new task",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    def capture_task(params: CaptureTaskInput) -> Task | dict:
        """Create a new task in one call, with all known details.

        Datetimes (`due_at`) MUST be ISO-8601 in UTC with the trailing 'Z'
        suffix. The server never guesses timezone. If `user_id` is omitted,
        the task is owned by 'default-user'.
        """
        try:
            return toolimpl.capture_task(STORE, params)
        except ToolError as e:
            return _wrap_error(e)

    @mcp.tool(
        name="review_tasks",
        annotations=ToolAnnotations(
            title="Review tasks",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def review_tasks(params: ReviewTasksInput) -> ReviewTasksOutput | dict:
        """Return tasks matching a high-level filter.

        Filters: `today` | `overdue` | `upcoming` | `open` | `all`.
        `tz` (IANA) controls the calendar boundary for `today`. Returns full
        Task objects so no follow-up fetch is needed. Sorted by due_at asc
        (nulls last) then created_at asc.
        """
        try:
            return toolimpl.review_tasks(STORE, params)
        except ToolError as e:
            return _wrap_error(e)

    @mcp.tool(
        name="modify_task",
        annotations=ToolAnnotations(
            title="Modify an existing task",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def modify_task(params: ModifyTaskInput) -> Task | dict:
        """Edit editable fields of an existing task in one call.

        Status is NOT editable here — use `resolve_task`. To clear an optional
        field, pass `null` explicitly. At least one of `title`, `description`,
        `due_at` must be provided.
        """
        try:
            return toolimpl.modify_task(STORE, params)
        except ToolError as e:
            return _wrap_error(e)

    @mcp.tool(
        name="resolve_task",
        annotations=ToolAnnotations(
            title="Resolve a task (complete or cancel)",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def resolve_task(params: ResolveTaskInput) -> Task | dict:
        """End a task's lifecycle by marking it completed or cancelled.

        Allowed transitions: `pending → completed`, `pending → cancelled`.
        Resolving an already-resolved task with the same outcome is a no-op
        success. Conflicting outcomes return `invalid_state_transition`.
        """
        try:
            return toolimpl.resolve_task(STORE, params)
        except ToolError as e:
            return _wrap_error(e)

    @mcp.tool(
        name="remove_task",
        annotations=ToolAnnotations(
            title="Permanently delete a task",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def remove_task(params: RemoveTaskInput) -> RemoveTaskOutput:
        """Hard-delete a task. The agent layer must obtain user confirmation
        before calling this. Idempotent: removing an already-removed id still
        returns `{ id, removed: true }`.
        """
        return toolimpl.remove_task(STORE, params)

    return mcp


# Module-level singleton for ASGI mounts (`uvicorn tasks_mcp.server:app`).
mcp_app = build_mcp()


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("TASKS_MCP_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    LOG.info(
        "starting tasks_mcp on %s:%s (stateless streamable-http)",
        mcp_app.settings.host,
        mcp_app.settings.port,
    )
    mcp_app.run(transport="streamable-http")


if __name__ == "__main__":
    main()
