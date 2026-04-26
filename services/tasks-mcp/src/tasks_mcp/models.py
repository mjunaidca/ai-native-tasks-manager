from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_USER = "default-user"


class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReviewFilter(str, Enum):
    TODAY = "today"
    OVERDUE = "overdue"
    UPCOMING = "upcoming"
    OPEN = "open"
    ALL = "all"


class ResolveOutcome(str, Enum):
    COMPLETED = "completed"
    CANCELLED = "cancelled"


UserId = Annotated[str, Field(min_length=1, max_length=128)]
Title = Annotated[str, Field(min_length=1, max_length=200)]
Description = Annotated[str, Field(max_length=4000)]
Note = Annotated[str, Field(max_length=500)]
UtcIso = Annotated[
    str,
    Field(
        description="ISO-8601 datetime in UTC with trailing 'Z' (e.g. '2026-04-27T17:00:00Z').",
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
    ),
]


class Task(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    user_id: str
    title: str
    description: str | None
    status: TaskStatus
    due_at: str | None
    note: str | None
    created_at: str
    updated_at: str


class CaptureTaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: Title
    due_at: UtcIso | None = None
    description: Description | None = None
    user_id: UserId | None = None


class ReviewTasksInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    filter: ReviewFilter
    query: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    cursor: str | None = None
    user_id: UserId | None = None
    tz: str = "UTC"


class ReviewTasksOutput(BaseModel):
    items: list[Task]
    next_cursor: str | None


class ModifyTaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str
    title: Title | None = None
    description: Description | None = None
    due_at: UtcIso | None = None
    user_id: UserId | None = None
    # Track which optional fields were explicitly set (so `null` clears).
    description_set: bool = Field(default=False, exclude=True)
    due_at_set: bool = Field(default=False, exclude=True)

    def __init__(self, **data: object) -> None:
        description_set = "description" in data
        due_at_set = "due_at" in data
        super().__init__(**data)
        self.description_set = description_set
        self.due_at_set = due_at_set


class ResolveTaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str
    outcome: ResolveOutcome
    note: Note | None = None
    user_id: UserId | None = None


class RemoveTaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str
    user_id: UserId | None = None


class RemoveTaskOutput(BaseModel):
    id: str
    removed: Literal[True] = True
