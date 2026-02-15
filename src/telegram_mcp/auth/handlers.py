from __future__ import annotations

import sys

from aiohttp import web
from telethon import TelegramClient
from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)
from telethon.tl.functions.auth import SendCodeRequest


class AuthHandlers:
    def __init__(self, client: TelegramClient, phone: str) -> None:
        self._client = client
        self._phone = phone
        self._phone_code_hash: str | None = None

    async def status(self, _request: web.Request) -> web.Response:
        authorized = await self._client.is_user_authorized()
        return web.json_response({
            "authorized": authorized,
            "phone": self._phone,
        })

    async def send_code(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            phone = body.get("phone", self._phone)
            result = await self._client.send_code_request(phone)
            self._phone_code_hash = result.phone_code_hash
            print(f"Code sent to {phone}", file=sys.stderr)
            return web.json_response({"phone_code_hash": result.phone_code_hash})
        except Exception as exc:
            print(f"send_code error: {exc}", file=sys.stderr)
            return web.json_response({"error": str(exc)}, status=400)

    async def sign_in(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            code = body.get("code", "")
            if not code:
                return web.json_response({"error": "Code is required"}, status=400)

            await self._client.sign_in(
                self._phone,
                code,
                phone_code_hash=self._phone_code_hash,
            )
            me = await self._client.get_me()
            name = f"{me.first_name or ''} {me.last_name or ''}".strip()
            print(f"Signed in as {name}", file=sys.stderr)
            return web.json_response({"ok": True, "name": name})

        except SessionPasswordNeededError:
            return web.json_response({"2fa_required": True})

        except (PhoneCodeInvalidError, PhoneCodeExpiredError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

        except Exception as exc:
            print(f"sign_in error: {exc}", file=sys.stderr)
            return web.json_response({"error": str(exc)}, status=400)

    async def verify_2fa(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            password = body.get("password", "")
            if not password:
                return web.json_response({"error": "Password is required"}, status=400)

            await self._client.sign_in(password=password)
            me = await self._client.get_me()
            name = f"{me.first_name or ''} {me.last_name or ''}".strip()
            print(f"2FA verified, signed in as {name}", file=sys.stderr)
            return web.json_response({"ok": True, "name": name})

        except Exception as exc:
            print(f"verify_2fa error: {exc}", file=sys.stderr)
            return web.json_response({"error": str(exc)}, status=400)
