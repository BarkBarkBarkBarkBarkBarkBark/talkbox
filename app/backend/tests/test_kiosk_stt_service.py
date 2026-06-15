from pathlib import Path

import pytest

from src.application.services.kiosk_stt_service import (
    KioskSttResult,
    KioskSttService,
    SttDisabledError,
    SttInvalidAudioError,
    SttUploadTooLargeError,
)
from src.infrastructure.config import Settings


def make_settings(tmp_path: Path, **overrides) -> Settings:
    model = tmp_path / "ggml-tiny.en-q5_1.bin"
    whisper = tmp_path / "whisper-cli"
    model.write_bytes(b"model")
    whisper.write_text("#!/bin/sh\n", encoding="utf-8")
    values = {
        "KIOSK_STT_ENABLED": True,
        "KIOSK_STT_PROVIDER": "local",
        "KIOSK_STT_MODEL_PATH": str(model),
        "KIOSK_STT_WHISPER_BIN": str(whisper),
        "KIOSK_STT_MAX_UPLOAD_BYTES": 32,
        "KIOSK_STT_MIN_CHARS": 3,
        **overrides,
    }
    return Settings(**values)


class Completed:
    returncode = 0
    stderr = ""

    def __init__(self, stdout=""):
        self.stdout = stdout


def test_disabled_raises_503(tmp_path):
    service = KioskSttService(make_settings(tmp_path, KIOSK_STT_ENABLED=False))

    with pytest.raises(SttDisabledError):
        service.transcribe(b"audio")


def test_empty_audio_is_rejected(tmp_path):
    service = KioskSttService(make_settings(tmp_path))

    with pytest.raises(SttInvalidAudioError):
        service.transcribe(b"")


def test_oversized_audio_is_rejected(tmp_path):
    service = KioskSttService(make_settings(tmp_path, KIOSK_STT_MAX_UPLOAD_BYTES=4))

    with pytest.raises(SttUploadTooLargeError):
        service.transcribe(b"12345")


def test_local_transcription_returns_transcript_and_cleans_tempdir(tmp_path, monkeypatch):
    temp_roots = []

    def fake_which(name):
        return "/usr/bin/ffmpeg" if name == "ffmpeg" else None

    def fake_run(args, **kwargs):
        if "ffmpeg" in args[0]:
            temp_roots.append(Path(args[-1]).parent)
            return Completed()
        return Completed(stdout="[00:00:00.000 --> 00:00:01.000] I need food\n")

    monkeypatch.setattr("src.application.services.kiosk_stt_service.shutil.which", fake_which)
    service = KioskSttService(make_settings(tmp_path), runner=fake_run)

    result = service.transcribe(b"audio", "voice.webm")

    assert result.text == "I need food"
    assert result.provider == "local"
    assert result.fallback_used is False
    assert temp_roots
    assert all(not root.exists() for root in temp_roots)


def test_auto_provider_falls_back_when_local_transcript_empty(tmp_path, monkeypatch):
    def fake_which(name):
        return "/usr/bin/ffmpeg" if name == "ffmpeg" else None

    def fake_run(args, **kwargs):
        return Completed(stdout="")

    monkeypatch.setattr("src.application.services.kiosk_stt_service.shutil.which", fake_which)
    service = KioskSttService(
        make_settings(tmp_path, KIOSK_STT_PROVIDER="auto"),
        runner=fake_run,
    )
    monkeypatch.setattr(
        service,
        "_transcribe_openai",
        lambda audio, filename, start: KioskSttResult(
            text="I need shelter",
            provider="openai",
            duration_ms=1,
        ),
    )

    result = service.transcribe(b"audio", "voice.webm")

    assert result.text == "I need shelter"
    assert result.provider == "openai"
    assert result.fallback_used is True
