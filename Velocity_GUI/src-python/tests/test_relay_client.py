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
