"""
Outbound HTTPS relay client for Velocity Bridge.

The desktop never accepts inbound relay traffic. It polls a public relay for
phone-to-desktop messages and command requests, then posts responses back over
normal HTTPS.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable


USER_AGENT = "VelocityBridge-iOS/3.0"

ClipboardReader = Callable[[], tuple[str, str]]
ClipboardWriter = Callable[[str, str, str], dict[str, Any]]
ImageWriter = Callable[[str, str, str], dict[str, Any]]
ConfigLoader = Callable[[], dict[str, Any]]


class RelayTransport:
    def __init__(
        self,
        load_config: ConfigLoader,
        read_clipboard: ClipboardReader,
        write_clipboard: ClipboardWriter,
        write_image: ImageWriter,
        logger: Any,
    ) -> None:
        self.load_config = load_config
        self.read_clipboard = read_clipboard
        self.write_clipboard = write_clipboard
        self.write_image = write_image
        self.logger = logger
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._desktop_cursor = 0
        self._last_error: str | None = None
        self._last_event: str | None = None
        self._last_poll: str | None = None
        self._messages_received = 0
        self._messages_sent = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="velocity-relay", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def status(self) -> dict[str, Any]:
        cfg = self.load_config()
        return {
            "enabled": bool(cfg.get("relay_enabled", False)),
            "configured": self._is_configured(cfg),
            "running": bool(self._thread and self._thread.is_alive()),
            "url": cfg.get("relay_url", ""),
            "pair_id": cfg.get("relay_pair_id", ""),
            "last_error": self._last_error,
            "last_event": self._last_event,
            "last_poll": self._last_poll,
            "messages_received": self._messages_received,
            "messages_sent": self._messages_sent,
        }

    def send_current_clipboard(self) -> dict[str, Any]:
        cfg = self.load_config()
        self._require_config(cfg)

        content_type, content = self.read_clipboard()
        if content_type in ("empty", "error"):
            raise RuntimeError(content or f"Clipboard is {content_type}")

        payload: dict[str, Any] = {
            "token": cfg["relay_token"],
            "kind": "clipboard",
            "type": content_type,
        }
        if content_type == "image":
            payload["image"] = content
            payload["filename"] = "clipboard_image.png"
        else:
            payload["content"] = content

        response = self._post_message(cfg, "phone", payload)
        self._messages_sent += 1
        self._last_event = "Sent clipboard to relay for phone"
        return response

    def _run(self) -> None:
        while not self._stop.is_set():
            cfg = self.load_config()
            poll_seconds = float(cfg.get("relay_poll_seconds", 3) or 3)

            if not cfg.get("relay_enabled", False) or not self._is_configured(cfg):
                self._stop.wait(min(max(poll_seconds, 1), 10))
                continue

            try:
                self._poll_once(cfg)
                self._last_error = None
                self._last_poll = time.strftime("%Y-%m-%dT%H:%M:%S")
            except Exception as exc:  # pragma: no cover - depends on network
                self._last_error = str(exc)
                self.logger.warning(f"Relay poll failed: {exc}")

            self._stop.wait(min(max(poll_seconds, 1), 30))

    def _poll_once(self, cfg: dict[str, Any]) -> None:
        messages = self._get_messages(cfg, "desktop", self._desktop_cursor)
        for message in messages:
            payload = message.get("payload", {})
            kind = payload.get("kind") or message.get("kind")

            if kind == "command":
                self._handle_command(cfg, payload)
            elif kind in ("clipboard", "response"):
                self._handle_clipboard_payload(payload)

            self._desktop_cursor = max(self._desktop_cursor, int(message["id"]))

    def _handle_command(self, cfg: dict[str, Any], payload: dict[str, Any]) -> None:
        if payload.get("command") != "get_clipboard":
            return

        content_type, content = self.read_clipboard()
        response: dict[str, Any] = {
            "token": cfg["relay_token"],
            "kind": "response",
            "correlation_id": payload.get("correlation_id") or payload.get("request_id"),
            "request_id": payload.get("request_id"),
            "type": content_type,
        }
        if content_type == "image":
            response["image"] = content
            response["filename"] = "clipboard_image.png"
        else:
            response["content"] = content

        self._post_message(cfg, "phone", response)
        self._messages_sent += 1
        self._last_event = "Answered phone clipboard request"

    def _handle_clipboard_payload(self, payload: dict[str, Any]) -> None:
        payload_type = payload.get("type", "text")
        if payload_type == "image" or payload.get("image"):
            self.write_image(
                payload.get("image") or payload.get("content") or "",
                payload.get("filename") or "clipboard_image.png",
                "Relay",
            )
        else:
            self.write_clipboard(payload_type, payload.get("content") or "", "Relay")

        self._messages_received += 1
        self._last_event = f"Received {payload_type} from relay"

    def _get_messages(self, cfg: dict[str, Any], target: str, after: int) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(
            {
                "token": cfg["relay_token"],
                "after": after,
                "limit": 25,
            }
        )
        pair_id = urllib.parse.quote(cfg['relay_pair_id'], safe='')
        target_encoded = urllib.parse.quote(target, safe='')
        url = f"{self._base_url(cfg)}/v1/pairs/{pair_id}/messages/{target_encoded}?{query}"
        data = self._request_json("GET", url)
        return data.get("messages", [])

    def _post_message(
        self,
        cfg: dict[str, Any],
        target: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        pair_id = urllib.parse.quote(cfg['relay_pair_id'], safe='')
        target_encoded = urllib.parse.quote(target, safe='')
        url = f"{self._base_url(cfg)}/v1/pairs/{pair_id}/messages/{target_encoded}"
        return self._request_json("POST", url, payload)

    def _request_json(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if shutil.which("curl"):
            return self._request_json_with_curl(method, url, payload)
        return self._request_json_with_urllib(method, url, payload)

    def _request_json_with_curl(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = b""
        command = [
            "curl",
            "--silent",
            "--show-error",
            "--max-time",
            "15",
            "--request",
            method,
            "--header",
            "Accept: application/json",
            "--header",
            f"User-Agent: {USER_AGENT}",
            "--write-out",
            "\n%{http_code}",
            url,
        ]

        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            command[12:12] = [
                "--header",
                "Content-Type: application/json",
                "--data-binary",
                "@-",
            ]

        result = subprocess.run(
            command,
            input=body,
            capture_output=True,
            timeout=20,
        )
        output = result.stdout.decode("utf-8", errors="replace")
        response_body, _, status_text = output.rpartition("\n")

        try:
            status_code = int(status_text)
        except ValueError:
            detail = result.stderr.decode("utf-8", errors="replace") or output
            raise RuntimeError(f"Relay request failed: {detail}")

        if status_code >= 400:
            raise RuntimeError(f"Relay returned HTTP {status_code}: {response_body}")
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace") or response_body
            raise RuntimeError(f"Relay request failed: {detail}")
        if not response_body:
            return {}
        return json.loads(response_body)

    def _request_json_with_urllib(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None
        headers = {
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Relay returned HTTP {exc.code}: {detail}") from exc

        if not raw:
            return {}
        return json.loads(raw)

    def _base_url(self, cfg: dict[str, Any]) -> str:
        return str(cfg.get("relay_url", "")).rstrip("/")

    def _is_configured(self, cfg: dict[str, Any]) -> bool:
        return bool(cfg.get("relay_url") and cfg.get("relay_pair_id") and cfg.get("relay_token"))

    def _require_config(self, cfg: dict[str, Any]) -> None:
        if not cfg.get("relay_enabled", False):
            raise RuntimeError("Relay mode is disabled")
        if not self._is_configured(cfg):
            raise RuntimeError("Relay URL, pair id, and token are required")
