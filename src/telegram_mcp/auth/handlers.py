from __future__ import annotations

import logging

from aiohttp import web
from telethon import TelegramClient
from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)

from ..application.responses import error_response, success_response
from ..domain.errors import ErrorCode, ToolError

logger = logging.getLogger(__name__)


class AuthHandlers:
    def __init__(self, client: TelegramClient, phone: str) -> None:
        self._client = client
        self._default_phone = phone
        self._current_phone = phone
        self._phone_code_hash: str | None = None

    async def status(self, _request: web.Request) -> web.Response:
        authorized = await self._client.is_user_authorized()
        return web.json_response(
            success_response(
                {
                    "authorized": authorized,
                    "phone": self._current_phone,
                }
            )
        )

    async def send_code(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            phone = str(body.get("phone", self._default_phone)).strip()
            if not phone:
                raise ToolError(
                    ErrorCode.VALIDATION_ERROR,
                    "Phone is required",
                    {"field": "phone"},
                )

            result = await self._client.send_code_request(phone)
            self._phone_code_hash = result.phone_code_hash
            self._current_phone = phone
            logger.info("Code sent to %s", phone)
            return web.json_response(success_response({"phone_code_hash": result.phone_code_hash}))
        except ToolError as exc:
            return web.json_response(error_response(exc), status=400)
        except Exception as exc:
            logger.exception("send_code error")
            return web.json_response(
                error_response(
                    ToolError(
                        ErrorCode.PROVIDER_ERROR,
                        "Failed to send verification code",
                        {"error": str(exc)},
                    )
                ),
                status=400,
            )

    async def sign_in(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            code = str(body.get("code", "")).strip()
            if not code:
                raise ToolError(
                    ErrorCode.VALIDATION_ERROR,
                    "Code is required",
                    {"field": "code"},
                )
            if not self._phone_code_hash:
                raise ToolError(
                    ErrorCode.VALIDATION_ERROR,
                    "Call send_code before sign_in",
                    {"field": "phone_code_hash"},
                )

            await self._client.sign_in(
                self._current_phone,
                code,
                phone_code_hash=self._phone_code_hash,
            )
            me = await self._client.get_me()
            name = f"{me.first_name or ''} {me.last_name or ''}".strip()
            logger.info("Signed in as %s", name)
            return web.json_response(success_response({"ok": True, "name": name, "2fa_required": False}))

        except SessionPasswordNeededError:
            return web.json_response(success_response({"2fa_required": True}))

        except PhoneCodeInvalidError:
            return web.json_response(
                error_response(
                    ToolError(
                        ErrorCode.VALIDATION_ERROR,
                        "Invalid verification code",
                        {"reason": "invalid_code"},
                    )
                ),
                status=400,
            )

        except PhoneCodeExpiredError:
            return web.json_response(
                error_response(
                    ToolError(
                        ErrorCode.VALIDATION_ERROR,
                        "Verification code expired",
                        {"reason": "expired_code"},
                    )
                ),
                status=400,
            )

        except ToolError as exc:
            return web.json_response(error_response(exc), status=400)

        except Exception as exc:
            logger.exception("sign_in error")
            return web.json_response(
                error_response(
                    ToolError(
                        ErrorCode.PROVIDER_ERROR,
                        "Failed to sign in",
                        {"error": str(exc)},
                    )
                ),
                status=400,
            )

    async def verify_2fa(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            password = str(body.get("password", ""))
            if not password:
                raise ToolError(
                    ErrorCode.VALIDATION_ERROR,
                    "Password is required",
                    {"field": "password"},
                )

            await self._client.sign_in(password=password)
            me = await self._client.get_me()
            name = f"{me.first_name or ''} {me.last_name or ''}".strip()
            logger.info("2FA verified, signed in as %s", name)
            return web.json_response(success_response({"ok": True, "name": name}))

        except ToolError as exc:
            return web.json_response(error_response(exc), status=400)

        except Exception as exc:
            logger.exception("verify_2fa error")
            error_class = exc.__class__.__name__
            if error_class == "PasswordHashInvalidError":
                return web.json_response(
                    error_response(
                        ToolError(
                            ErrorCode.VALIDATION_ERROR,
                            "Invalid 2FA password",
                            {"reason": "invalid_2fa"},
                        )
                    ),
                    status=400,
                )
            return web.json_response(
                error_response(
                    ToolError(
                        ErrorCode.PROVIDER_ERROR,
                        "Failed to verify 2FA",
                        {"error": str(exc)},
                    )
                ),
                status=400,
            )
