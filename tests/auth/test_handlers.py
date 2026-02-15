from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, cast

import pytest

from tests.conftest import load_attr

AuthHandlers = load_attr("telegram_mcp.auth.handlers", "AuthHandlers")


class FakeRequest:
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self._payload = payload or {}

    async def json(self) -> dict[str, object]:
        return self._payload


class FakeClient:
    def __init__(self) -> None:
        self.sent_phone: str | None = None
        self.sign_in_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.sign_in_error: Exception | None = None

    async def is_user_authorized(self) -> bool:
        _ = self.sent_phone
        return False

    async def send_code_request(self, phone: str) -> object:
        self.sent_phone = phone
        return SimpleNamespace(phone_code_hash="hash-1")

    async def sign_in(self, *args: object, **kwargs: object) -> None:
        self.sign_in_calls.append((args, kwargs))
        if self.sign_in_error is not None:
            raise self.sign_in_error

    async def get_me(self) -> object:
        _ = self.sign_in_error
        return SimpleNamespace(first_name="Alice", last_name="Test")


def _response_json(response: Any) -> dict[str, Any]:
    return json.loads(response.text)


@pytest.mark.asyncio
async def test_send_code_and_sign_in_use_same_phone() -> None:
    client = FakeClient()
    handlers = AuthHandlers(client=client, phone="+10000000000")

    send_response = await handlers.send_code(cast(Any, FakeRequest({"phone": "+12223334444"})))
    sign_in_response = await handlers.sign_in(cast(Any, FakeRequest({"code": "12345"})))

    send_payload = _response_json(send_response)
    sign_payload = _response_json(sign_in_response)

    assert send_payload["ok"] is True
    assert sign_payload["ok"] is True
    args, kwargs = client.sign_in_calls[-1]
    assert args[0] == "+12223334444"
    assert kwargs["phone_code_hash"] == "hash-1"


@pytest.mark.asyncio
async def test_sign_in_returns_explicit_invalid_code_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeInvalidCodeError(Exception):
        pass

    monkeypatch.setattr("telegram_mcp.auth.handlers.PhoneCodeInvalidError", FakeInvalidCodeError)

    client = FakeClient()
    handlers = AuthHandlers(client=client, phone="+10000000000")
    await handlers.send_code(cast(Any, FakeRequest({"phone": "+10000000000"})))
    client.sign_in_error = FakeInvalidCodeError("invalid")

    response = await handlers.sign_in(cast(Any, FakeRequest({"code": "11111"})))
    payload = _response_json(response)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["details"]["reason"] == "invalid_code"


@pytest.mark.asyncio
async def test_sign_in_returns_2fa_required(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTwoFactorError(Exception):
        pass

    monkeypatch.setattr("telegram_mcp.auth.handlers.SessionPasswordNeededError", FakeTwoFactorError)

    client = FakeClient()
    handlers = AuthHandlers(client=client, phone="+10000000000")
    await handlers.send_code(cast(Any, FakeRequest({"phone": "+10000000000"})))
    client.sign_in_error = FakeTwoFactorError("2fa")

    response = await handlers.sign_in(cast(Any, FakeRequest({"code": "22222"})))
    payload = _response_json(response)

    assert payload["ok"] is True
    assert payload["data"]["2fa_required"] is True
