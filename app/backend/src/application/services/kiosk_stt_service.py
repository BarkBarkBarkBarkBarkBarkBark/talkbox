"""One-shot speech-to-text service for the kiosk voice search button."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.infrastructure.config import Settings, settings

logger = logging.getLogger(__name__)


class KioskSttError(Exception):
    status_code = 500


class SttDisabledError(KioskSttError):
    status_code = 503


class SttUnavailableError(KioskSttError):
    status_code = 503


class SttInvalidAudioError(KioskSttError):
    status_code = 400


class SttUploadTooLargeError(KioskSttError):
    status_code = 413


class Runner(Protocol):
    def __call__(self, args: list[str], **kwargs) -> subprocess.CompletedProcess:
        ...


@dataclass
class KioskSttResult:
    text: str
    provider: str
    duration_ms: int
    fallback_used: bool = False
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "provider": self.provider,
            "duration_ms": self.duration_ms,
            "fallback_used": self.fallback_used,
            "error": self.error,
        }


class KioskSttService:
    def __init__(self, cfg: Settings = settings, runner: Runner = subprocess.run):
        self._settings = cfg
        self._run = runner

    def transcribe(self, audio: bytes, filename: str = "audio.webm") -> KioskSttResult:
        start = time.monotonic()
        self._validate_audio(audio)

        provider = self._settings.kiosk_stt_provider.strip().lower()
        if provider not in {"local", "openai", "auto"}:
            raise SttUnavailableError("KIOSK_STT_PROVIDER must be local, openai, or auto.")

        local_error: str | None = None
        if provider in {"local", "auto"}:
            try:
                result = self._transcribe_local(audio, filename, start)
                if self._is_usable(result.text):
                    return result
                local_error = "Local transcription was empty."
            except KioskSttError as exc:
                local_error = str(exc)
                if provider == "local":
                    raise

        if provider in {"openai", "auto"}:
            try:
                result = self._transcribe_openai(audio, filename, start)
                result.fallback_used = provider == "auto"
                return result
            except KioskSttError as exc:
                if provider == "openai":
                    raise
                raise SttUnavailableError(local_error or str(exc)) from exc

        raise SttUnavailableError(local_error or "Speech transcription failed.")

    def _validate_audio(self, audio: bytes) -> None:
        if not self._settings.kiosk_stt_enabled:
            raise SttDisabledError("Speech search is disabled.")
        if not audio:
            raise SttInvalidAudioError("No audio was uploaded.")
        if len(audio) > self._settings.kiosk_stt_max_upload_bytes:
            raise SttUploadTooLargeError("Uploaded audio is too large.")

    def _transcribe_local(
        self,
        audio: bytes,
        filename: str,
        start: float,
    ) -> KioskSttResult:
        whisper_bin = self._resolve_executable(self._settings.kiosk_stt_whisper_bin)
        ffmpeg_bin = shutil.which("ffmpeg")
        model_path = Path(self._settings.kiosk_stt_model_path)

        if not ffmpeg_bin:
            raise SttUnavailableError("ffmpeg is not installed.")
        if not whisper_bin:
            raise SttUnavailableError("whisper.cpp binary is not installed.")
        if not model_path.exists():
            raise SttUnavailableError("whisper.cpp model file is not installed.")

        suffix = Path(filename or "audio.webm").suffix or ".webm"
        with tempfile.TemporaryDirectory(prefix="talkbox-stt-") as tmp:
            input_path = Path(tmp) / f"input{suffix}"
            wav_path = Path(tmp) / "input.wav"
            input_path.write_bytes(audio)

            self._run_checked(
                [
                    ffmpeg_bin,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(input_path),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(wav_path),
                ],
                timeout=self._settings.kiosk_stt_max_seconds + 10,
                label="audio conversion",
            )
            completed = self._run_checked(
                [
                    whisper_bin,
                    "-m",
                    str(model_path),
                    "-f",
                    str(wav_path),
                    "-l",
                    self._settings.kiosk_stt_language,
                    "-nt",
                ],
                timeout=self._settings.kiosk_stt_max_seconds + 25,
                label="local transcription",
            )

        text = self._parse_whisper_output(completed.stdout or "")
        return KioskSttResult(
            text=text,
            provider="local",
            duration_ms=self._elapsed_ms(start),
            error=None if self._is_usable(text) else "Transcript was empty.",
        )

    def _transcribe_openai(
        self,
        audio: bytes,
        filename: str,
        start: float,
    ) -> KioskSttResult:
        if not self._settings.openai_api_key:
            raise SttUnavailableError("OpenAI transcription fallback is not configured.")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise SttUnavailableError("OpenAI SDK is not installed.") from exc

        suffix = Path(filename or "audio.webm").suffix or ".webm"
        with tempfile.TemporaryDirectory(prefix="talkbox-stt-openai-") as tmp:
            input_path = Path(tmp) / f"input{suffix}"
            input_path.write_bytes(audio)
            client = OpenAI(api_key=self._settings.openai_api_key)
            with input_path.open("rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model=self._settings.kiosk_stt_openai_model,
                    file=audio_file,
                    language=self._settings.kiosk_stt_language,
                )

        text = (getattr(response, "text", "") or "").strip()
        if not self._is_usable(text):
            raise SttUnavailableError("OpenAI transcription was empty.")
        return KioskSttResult(
            text=text,
            provider="openai",
            duration_ms=self._elapsed_ms(start),
        )

    def _run_checked(
        self,
        args: list[str],
        timeout: int,
        label: str,
    ) -> subprocess.CompletedProcess:
        try:
            completed = self._run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SttUnavailableError(f"{label} timed out.") from exc
        except OSError as exc:
            raise SttUnavailableError(f"{label} could not start.") from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            logger.warning("%s failed: %s", label, detail)
            raise SttUnavailableError(f"{label} failed.")
        return completed

    def _is_usable(self, text: str) -> bool:
        return len((text or "").strip()) >= self._settings.kiosk_stt_min_chars

    @staticmethod
    def _resolve_executable(configured: str) -> str | None:
        configured = configured.strip()
        if not configured:
            return None
        path = Path(configured)
        if path.is_absolute():
            return str(path) if path.exists() else None
        return shutil.which(configured)

    @staticmethod
    def _parse_whisper_output(output: str) -> str:
        lines: list[str] = []
        for raw in output.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("whisper_") or line.startswith("system_info:"):
                continue
            line = re.sub(r"^\[[^\]]+\]\s*", "", line).strip()
            if line:
                lines.append(line)
        return " ".join(" ".join(lines).split())

    @staticmethod
    def _elapsed_ms(start: float) -> int:
        return int((time.monotonic() - start) * 1000)
