from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, cast

from .presentation.server import create_server

TransportName = Literal["stdio", "sse", "streamable-http"]


@dataclass(frozen=True, slots=True)
class RuntimeOptions:
    transport: TransportName
    http_host: str
    http_port: int
    mount_path: str


def _read_env(environ: Mapping[str, str], key: str, default: str) -> str:
    value = environ.get(key, "").strip()
    return value or default


def _read_env_port(environ: Mapping[str, str], key: str, default: int) -> int:
    raw_value = _read_env(environ, key, str(default))
    try:
        port = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{key} must be an integer") from exc
    if port <= 0 or port > 65535:
        raise RuntimeError(f"{key} must be in range 1..65535")
    return port


def _build_parser(environ: Mapping[str, str]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run telegram-mcp server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default=_read_env(environ, "MCP_TRANSPORT", "stdio"),
        help="MCP transport: stdio, sse, or streamable-http",
    )
    parser.add_argument(
        "--http-host",
        default=_read_env(environ, "MCP_HTTP_HOST", "127.0.0.1"),
        help="HTTP bind host for SSE/streamable-http transports",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=_read_env_port(environ, "MCP_HTTP_PORT", 8000),
        help="HTTP bind port for SSE/streamable-http transports",
    )
    parser.add_argument(
        "--mount-path",
        default=_read_env(environ, "MCP_MOUNT_PATH", "/"),
        help="Optional mount path prefix for SSE message endpoint",
    )
    return parser


def parse_runtime_options(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> RuntimeOptions:
    source_env = os.environ if environ is None else environ
    parser = _build_parser(source_env)
    parsed = parser.parse_args(argv)

    if parsed.http_port <= 0 or parsed.http_port > 65535:
        parser.error("--http-port must be in range 1..65535")
    if not parsed.mount_path.startswith("/"):
        parser.error("--mount-path must start with '/'")

    return RuntimeOptions(
        transport=cast(TransportName, parsed.transport),
        http_host=parsed.http_host,
        http_port=parsed.http_port,
        mount_path=parsed.mount_path,
    )


def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    options = parse_runtime_options(argv)
    server = create_server(
        host=options.http_host,
        port=options.http_port,
        mount_path=options.mount_path,
    )
    run_mount_path = options.mount_path if options.transport == "sse" else None
    server.run(transport=options.transport, mount_path=run_mount_path)


if __name__ == "__main__":
    main()
