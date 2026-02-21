from __future__ import annotations

import asyncio

import pytest

from tests.conftest import load_attr

SharedSessionRuntime = load_attr(
    "telegram_mcp.presentation.server",
    "_SharedSessionRuntime",
)


class FakeAdapter:
    def __init__(self) -> None:
        self.connect_calls = 0
        self.disconnect_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1
        await asyncio.sleep(0.01)

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        await asyncio.sleep(0.01)


class FakeMediaProxy:
    def __init__(self, *, fail_start: bool = False) -> None:
        self.fail_start = fail_start
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        self.start_calls += 1
        await asyncio.sleep(0.01)
        if self.fail_start:
            raise RuntimeError("start failed")

    async def stop(self) -> None:
        self.stop_calls += 1
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_shared_runtime_connects_once_for_parallel_sessions() -> None:
    adapter = FakeAdapter()
    media_proxy = FakeMediaProxy()
    runtime = SharedSessionRuntime(adapter, media_proxy)

    await asyncio.gather(runtime.acquire(), runtime.acquire(), runtime.acquire())

    assert adapter.connect_calls == 1
    assert media_proxy.start_calls == 1

    await runtime.release()
    assert media_proxy.stop_calls == 0
    assert adapter.disconnect_calls == 0

    await asyncio.gather(runtime.release(), runtime.release())

    assert media_proxy.stop_calls == 1
    assert adapter.disconnect_calls == 1

    await runtime.release()
    assert media_proxy.stop_calls == 1
    assert adapter.disconnect_calls == 1


@pytest.mark.asyncio
async def test_shared_runtime_rolls_back_connect_when_proxy_start_fails() -> None:
    adapter = FakeAdapter()
    media_proxy = FakeMediaProxy(fail_start=True)
    runtime = SharedSessionRuntime(adapter, media_proxy)

    with pytest.raises(RuntimeError, match="start failed"):
        await runtime.acquire()

    assert adapter.connect_calls == 1
    assert adapter.disconnect_calls == 1
    assert media_proxy.start_calls == 1
    assert media_proxy.stop_calls == 0
