from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    NOT_FOUND = "not_found"
    INVALID_ARGUMENT = "invalid_argument"
    INVALID_STATE_TRANSITION = "invalid_state_transition"
    INTERNAL = "internal"


class ToolError(Exception):
    """Raised inside tool handlers; serialized into the standard error envelope."""

    def __init__(
        self, code: ErrorCode, message: str, suggestion: str | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.suggestion = suggestion

    def envelope(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "suggestion": self.suggestion,
            }
        }


def error_envelope(
    code: ErrorCode, message: str, suggestion: str | None = None
) -> dict[str, Any]:
    return ToolError(code, message, suggestion).envelope()
