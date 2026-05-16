"""Regression tests for relay transport recovery behavior."""

from types import SimpleNamespace

import relay_client


class _NoopLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass


def _make_transport():
    return relay_client.RelayTransport(
        load_config=lambda: {
            "relay_enabled": True,
            "relay_url": "https://example.invalid",
            "relay_pair_id": "pair-123",
            "relay_token": "token-123",
        },
        read_clipboard=lambda: ("text", "hello"),
        write_clipboard=lambda *args, **kwargs: {},
        write_image=lambda *args, **kwargs: {},
        logger=_NoopLogger(),
    )


def test_stream_sse_uses_http11(monkeypatch):
    transport = _make_transport()
    captured = {}

    class _EmptyStream:
        def __iter__(self):
            return iter(())

        def close(self):
            pass

    class FakeProc:
        def __init__(self, command, stdout=None, stderr=None, text=None, bufsize=None):
            captured["command"] = command
            self.stdout = _EmptyStream()
            self.stderr = SimpleNamespace(read=lambda: b"")

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(relay_client.subprocess, "Popen", FakeProc)

    transport._stream_sse_with_curl("https://example.invalid/stream", transport.load_config())

    assert "--http1.1" in captured["command"]


def test_run_falls_back_to_polling(monkeypatch):
    transport = _make_transport()
    events = []

    class FakeStop:
        def __init__(self):
            self.wait_calls = 0

        def is_set(self):
            return self.wait_calls > 0

        def wait(self, timeout=None):
            self.wait_calls += 1
            return True

    transport._stop = FakeStop()
    monkeypatch.setattr(transport, "_try_sse", lambda cfg: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(transport, "_poll_once", lambda cfg: events.append("polled"))
    monkeypatch.setattr(transport, "_relay_poll_seconds", lambda cfg: 0.01)

    transport._run()

    assert events == ["polled"]
    assert transport._last_error is None


def test_run_polls_after_clean_sse_session(monkeypatch):
    transport = _make_transport()
    events = []

    class FakeStop:
        def __init__(self):
            self.wait_calls = 0

        def is_set(self):
            return self.wait_calls > 0

        def wait(self, timeout=None):
            self.wait_calls += 1
            return True

    transport._stop = FakeStop()
    monkeypatch.setattr(transport, "_try_sse", lambda cfg: events.append("sse"))
    monkeypatch.setattr(transport, "_poll_once", lambda cfg: events.append("polled"))

    transport._run()

    assert events == ["sse", "polled"]
    assert transport._last_error is None


def test_stream_sse_treats_idle_tls_eof_as_transient(monkeypatch):
    transport = _make_transport()

    class _EmptyStream:
        def __iter__(self):
            return iter(())

        def close(self):
            pass

    class FakeProc:
        def __init__(self, command, stdout=None, stderr=None, text=None, bufsize=None):
            self.stdout = _EmptyStream()
            self.stderr = SimpleNamespace(
                read=lambda: (
                    "curl: (56) OpenSSL SSL_read: OpenSSL/3.5.5: "
                    "error:0A000126:SSL routines::unexpected eof while reading, errno 0"
                )
            )

        def wait(self, timeout=None):
            return 56

    monkeypatch.setattr(relay_client.subprocess, "Popen", FakeProc)

    transport._stream_sse_with_curl("https://example.invalid/stream", transport.load_config())


def test_desktop_after_cursor_uses_overlap():
    transport = _make_transport()
    transport._desktop_cursor = 1_778_894_555_190_121

    assert transport._desktop_after_cursor() == 1_778_893_955_190_121


def test_duplicate_overlap_message_is_skipped():
    writes = []
    transport = relay_client.RelayTransport(
        load_config=lambda: {
            "relay_enabled": True,
            "relay_url": "https://example.invalid",
            "relay_pair_id": "pair-123",
            "relay_token": "token-123",
        },
        read_clipboard=lambda: ("text", "hello"),
        write_clipboard=lambda *args, **kwargs: writes.append(args) or {},
        write_image=lambda *args, **kwargs: {},
        logger=_NoopLogger(),
    )
    cfg = transport.load_config()
    message = {
        "id": 123,
        "kind": "clipboard",
        "payload": {"kind": "clipboard", "type": "text", "content": "hello"},
    }

    transport._process_desktop_message(cfg, message)
    transport._process_desktop_message(cfg, message)

    assert len(writes) == 1


def test_clipboard_sync_loop_polls_while_sse_is_open(monkeypatch):
    transport = _make_transport()
    events = []

    class FakeStop:
        def __init__(self):
            self.wait_calls = 0

        def is_set(self):
            return self.wait_calls > 0

        def wait(self, timeout=None):
            self.wait_calls += 1
            return True

    transport._stop = FakeStop()
    monkeypatch.setattr(transport, "_poll_once", lambda cfg: events.append("polled"))
    monkeypatch.setattr(transport, "_sync_local_clipboard", lambda cfg: events.append("synced"))
    monkeypatch.setattr(transport, "_relay_poll_seconds", lambda cfg: 0.01)

    transport._clipboard_sync_loop()

    assert events == ["polled", "synced"]
