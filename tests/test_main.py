from __future__ import annotations

import pytest

from telegram_mcp.__main__ import RuntimeOptions, parse_runtime_options


def test_parse_runtime_options_uses_defaults() -> None:
    options = parse_runtime_options([], environ={})

    assert options == RuntimeOptions(
        transport="stdio",
        http_host="127.0.0.1",
        http_port=8000,
        mount_path="/",
    )


def test_parse_runtime_options_respects_env_overrides() -> None:
    options = parse_runtime_options(
        [],
        environ={
            "MCP_TRANSPORT": "sse",
            "MCP_HTTP_HOST": "0.0.0.0",
            "MCP_HTTP_PORT": "8903",
            "MCP_MOUNT_PATH": "/telegram",
        },
    )

    assert options == RuntimeOptions(
        transport="sse",
        http_host="0.0.0.0",
        http_port=8903,
        mount_path="/telegram",
    )


def test_parse_runtime_options_raises_for_invalid_env_port() -> None:
    with pytest.raises(RuntimeError, match="MCP_HTTP_PORT must be an integer"):
        parse_runtime_options([], environ={"MCP_HTTP_PORT": "invalid"})


def test_parse_runtime_options_rejects_invalid_mount_path() -> None:
    with pytest.raises(SystemExit):
        parse_runtime_options(["--mount-path", "telegram"], environ={})
