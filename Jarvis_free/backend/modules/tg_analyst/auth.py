"""Авторизация userbot: телефон → OTP → 2FA. Сессия хранится локально."""

from __future__ import annotations

from dataclasses import dataclass

from modules.tg_analyst.models import AuthPhase, AuthStartOut, AuthVerifyOut
from modules.tg_analyst import runtime


@dataclass
class AuthState:
    phase: AuthPhase = AuthPhase.NONE
    phone: str = ""
    phone_code_hash: str = ""
    message: str = ""
    last_error: str | None = None


_state = AuthState()


def get_auth_state() -> AuthState:
    if runtime.session_exists() and _state.phase not in (
        AuthPhase.NEED_CODE,
        AuthPhase.NEED_PASSWORD,
    ):
        _state.phase = AuthPhase.READY
        _state.message = "Сессия Telegram активна"
    elif not runtime.session_exists() and _state.phase == AuthPhase.READY:
        _state.phase = AuthPhase.NEED_PHONE
    return _state


async def _auth_start_async(phone: str) -> AuthStartOut:
    from telethon.errors import FloodWaitError

    client = await runtime.get_client(connect=True)
    phone = phone.strip()
    try:
        sent = await client.send_code_request(phone)
        _state.phone = phone
        _state.phone_code_hash = sent.phone_code_hash
        _state.phase = AuthPhase.NEED_CODE
        _state.message = "Код отправлен в Telegram"
        _state.last_error = None
        return AuthStartOut(
            ok=True,
            phone_code_hash=sent.phone_code_hash,
            message=_state.message,
        )
    except FloodWaitError as e:
        _state.last_error = str(e)
        return AuthStartOut(ok=False, message=f"Подождите {e.seconds} сек.")
    except Exception as e:
        _state.phase = AuthPhase.NEED_PHONE
        _state.last_error = str(e)
        return AuthStartOut(ok=False, message=str(e))


async def _auth_verify_async(phone: str, code: str) -> AuthVerifyOut:
    client = await runtime.get_client(connect=True)
    try:
        await client.sign_in(
            phone=phone.strip(),
            code=code.strip(),
            phone_code_hash=_state.phone_code_hash or None,
        )
        _state.phase = AuthPhase.READY
        _state.message = "Вход выполнен"
        _state.last_error = None
        return AuthVerifyOut(ok=True, need_password=False, message=_state.message)
    except Exception as e:
        err = str(e).lower()
        if "password" in err or "two-step" in err or "2fa" in err:
            _state.phase = AuthPhase.NEED_PASSWORD
            _state.message = "Требуется пароль двухэтапной аутентификации"
            return AuthVerifyOut(ok=True, need_password=True, message=_state.message)
        _state.last_error = str(e)
        return AuthVerifyOut(ok=False, message=str(e))


async def _auth_password_async(password: str) -> AuthVerifyOut:
    client = await runtime.get_client(connect=True)
    try:
        await client.sign_in(password=password.strip())
        _state.phase = AuthPhase.READY
        _state.message = "Вход с 2FA выполнен"
        _state.last_error = None
        return AuthVerifyOut(ok=True, message=_state.message)
    except Exception as e:
        _state.last_error = str(e)
        return AuthVerifyOut(ok=False, message=str(e))


async def _auth_logout_async() -> None:
    await runtime.disconnect_client()
    _state.phase = AuthPhase.NEED_PHONE
    _state.phone = ""
    _state.phone_code_hash = ""
    _state.message = "Сессия отключена (файл .session не удалён)"


def auth_start(phone: str) -> AuthStartOut:
    if not runtime.telethon_installed():
        return AuthStartOut(ok=False, message="Установите telethon: pip install telethon")
    if not runtime.credentials_configured():
        return AuthStartOut(
            ok=False,
            message="Задайте TELEGRAM_API_ID и TELEGRAM_API_HASH в backend/.env",
        )
    return runtime.run_async(_auth_start_async(phone))


def auth_verify(phone: str, code: str) -> AuthVerifyOut:
    return runtime.run_async(_auth_verify_async(phone, code))


def auth_password(password: str) -> AuthVerifyOut:
    return runtime.run_async(_auth_password_async(password))


def auth_logout() -> dict:
    runtime.run_async(_auth_logout_async())
    return {"ok": True, "message": _state.message}
