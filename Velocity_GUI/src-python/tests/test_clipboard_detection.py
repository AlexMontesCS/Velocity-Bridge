"""Regression tests for Linux clipboard backend selection."""

from types import SimpleNamespace

import server


def test_get_linux_clipboard_uses_wayland_text_backend(monkeypatch):
    calls = []

    def fake_detect_display_server():
        return "wayland"

    def fake_run(command, capture_output=True, timeout=None):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=b"hello")

    monkeypatch.setattr(server, "detect_display_server", fake_detect_display_server)
    monkeypatch.setattr(server.subprocess, "run", fake_run)

    content_type, content = server.get_linux_clipboard()

    assert content_type == "text"
    assert content == "hello"
    assert calls[0] == ["wl-paste", "--list-types"]
    assert calls[1] == ["wl-paste", "--no-newline"]


def test_get_linux_clipboard_image_uses_wayland_backend(monkeypatch):
    calls = []

    def fake_detect_display_server():
        return "wayland"

    def fake_run(command, capture_output=True, timeout=None):
        calls.append(command)
        if command == ["wl-paste", "--list-types"]:
            return SimpleNamespace(returncode=0, stdout=b"text/plain\nimage/png\n")
        return SimpleNamespace(returncode=0, stdout=b"image-bytes")

    monkeypatch.setattr(server, "detect_display_server", fake_detect_display_server)
    monkeypatch.setattr(server.subprocess, "run", fake_run)

    result = server.get_linux_clipboard_image()

    assert result == ("image", "aW1hZ2UtYnl0ZXM=")
    assert calls[0] == ["wl-paste", "--list-types"]
    assert calls[1] == ["wl-paste", "--type", "image/png"]