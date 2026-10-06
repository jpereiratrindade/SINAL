"""Módulo de transcrição e reconhecimento de fala."""

from __future__ import annotations

from pathlib import Path

from sinal.media.subtitles import SubtitleCue
from sinal.transcription.base import Transcriber, TranscriptionError
from sinal.transcription.mock import MockTranscriber
from sinal.transcription.whisper import WhisperTranscriber

__all__ = [
    "MockTranscriber",
    "Transcriber",
    "TranscriptionError",
    "WhisperTranscriber",
    "transcribe_media",
]


def transcribe_media(
    media_path: str | Path,
    *,
    transcriber: Transcriber | None = None,
    engine: str = "mock",
    model_size: str = "small",
) -> list[SubtitleCue]:
    """Transcreve o áudio de um arquivo de mídia em legendas estruturadas."""
    if transcriber is not None:
        return transcriber.transcribe(media_path)
    if engine == "whisper":
        return WhisperTranscriber(model_size=model_size).transcribe(media_path)
    return MockTranscriber().transcribe(media_path)
