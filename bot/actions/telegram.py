"""Telegram Bot API helpers."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Shown on the Telegram bot profile / chat info (set via Bot API).
BOT_NAME = "AutoAccept Bot | Secret Shop"

BOT_SHORT_DESCRIPTION = (
    "AutoAccept Bot by Secret Shop — удобный помощник для Dota 2: "
    "поиск игры, автопринятие и мгновенные уведомления."
)

BOT_DESCRIPTION = (
    "AutoAccept Bot by Secret Shop\n"
    "\n"
    "Удобный инструмент для Dota 2, который следит за кнопкой «ПРИНЯТЬ» "
    "и помогает не пропустить игру, пока ты отошёл от ПК.\n"
    "\n"
    "Что умеет:\n"
    "• моментально пишет, когда игра найдена;\n"
    "• при необходимости сам принимает матч;\n"
    "• может прислать скрин экрана;\n"
    "• держит тебя в курсе статуса поиска.\n"
    "\n"
    "Подключи бота в AutoAccept Bot, сохрани Token и Chat ID — "
    "и получай алерты прямо в Telegram.\n"
    "\n"
    "Secret Shop — играй спокойнее, а мы закроем принятие."
)


def _api(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def _post_form(token: str, method: str, fields: dict[str, str], timeout: float = 12.0) -> bool:
    token = (token or "").strip()
    if not token:
        return False
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        _api(token, method),
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return bool(payload.get("ok"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return False


def apply_bot_profile(token: str) -> bool:
    """Set display name + short/full description on the user's Telegram bot."""
    token = (token or "").strip()
    if not token:
        return False
    ok_name = _post_form(token, "setMyName", {"name": BOT_NAME})
    ok_short = _post_form(
        token,
        "setMyShortDescription",
        {"short_description": BOT_SHORT_DESCRIPTION[:120]},
    )
    ok_desc = _post_form(
        token,
        "setMyDescription",
        {"description": BOT_DESCRIPTION[:512]},
    )
    return ok_name or ok_short or ok_desc


def send_message(token: str, chat_id: str, text: str, timeout: float = 12.0) -> bool:
    token = (token or "").strip()
    chat_id = (chat_id or "").strip()
    if not token or not chat_id:
        return False
    data = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    ).encode("utf-8")
    req = urllib.request.Request(
        _api(token, "sendMessage"),
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return bool(payload.get("ok"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return False


def get_updates(
    token: str,
    offset: int | None = None,
    timeout: int = 20,
) -> list[dict[str, Any]]:
    token = (token or "").strip()
    if not token:
        return []
    params: dict[str, str] = {
        "timeout": str(timeout),
        "allowed_updates": json.dumps(["message"]),
    }
    if offset is not None:
        params["offset"] = str(offset)
    url = _api(token, "getUpdates") + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET")
    try:
        # HTTP timeout a bit above long-poll timeout
        with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            if not payload.get("ok"):
                return []
            result = payload.get("result") or []
            return result if isinstance(result, list) else []
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return []


class TelegramCommandPoller:
    """Background long-poll for /start → reply that the bot is ready."""

    START_REPLY = "Бот запущен и готов к работе!"

    def __init__(self, get_settings: Callable[[], dict[str, Any]]) -> None:
        self.get_settings = get_settings
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._offset: int | None = None
        self._dropped_pending = False

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.alive:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="tg-commands", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=1.5)
        self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            settings = self.get_settings() or {}
            if not settings.get("tg_enabled"):
                self._stop.wait(1.0)
                continue
            token = str(settings.get("tg_token", "")).strip()
            if not token:
                self._stop.wait(1.0)
                continue

            # Skip backlog once so old /start messages don't spam
            if not self._dropped_pending:
                pending = get_updates(token, offset=self._offset, timeout=0)
                if pending:
                    self._offset = int(pending[-1]["update_id"]) + 1
                self._dropped_pending = True

            updates = get_updates(token, offset=self._offset, timeout=20)
            for update in updates:
                try:
                    self._offset = int(update["update_id"]) + 1
                except (KeyError, TypeError, ValueError):
                    continue
                message = update.get("message") or update.get("edited_message") or {}
                text = str(message.get("text") or "").strip()
                chat = message.get("chat") or {}
                chat_id = chat.get("id")
                if chat_id is None:
                    continue
                # /start or /start@BotName
                cmd = text.split()[0] if text else ""
                if cmd == "/start" or cmd.startswith("/start@"):
                    send_message(token, str(chat_id), self.START_REPLY)

            if not updates:
                # brief pause on empty/errors already handled inside get_updates
                if self._stop.is_set():
                    break


def send_photo(
    token: str,
    chat_id: str,
    photo_path: Path,
    caption: str = "",
    timeout: float = 20.0,
) -> bool:
    token = (token or "").strip()
    chat_id = (chat_id or "").strip()
    if not token or not chat_id or not photo_path.exists():
        return False

    boundary = "----SecretShopBoundary7MA4YWxkTrZu0gW"
    filename = photo_path.name
    file_bytes = photo_path.read_bytes()

    parts: list[bytes] = []
    for name, value in (("chat_id", chat_id), ("caption", caption)):
        if not value and name == "caption":
            continue
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(f"{value}\r\n".encode("utf-8"))

    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        (
            f'Content-Disposition: form-data; name="photo"; filename="{filename}"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode()
    )
    parts.append(file_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    req = urllib.request.Request(
        _api(token, "sendPhoto"),
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return bool(payload.get("ok"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError):
        return False
