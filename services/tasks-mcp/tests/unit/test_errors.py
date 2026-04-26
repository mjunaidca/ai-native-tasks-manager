from tasks_mcp.errors import ErrorCode, ToolError, error_envelope


def test_error_envelope_shape() -> None:
    env = error_envelope(ErrorCode.NOT_FOUND, "missing", "look elsewhere")
    assert env == {
        "error": {
            "code": "not_found",
            "message": "missing",
            "suggestion": "look elsewhere",
        }
    }


def test_tool_error_envelope_no_suggestion() -> None:
    env = ToolError(ErrorCode.INVALID_ARGUMENT, "bad").envelope()
    assert env["error"]["code"] == "invalid_argument"
    assert env["error"]["suggestion"] is None
