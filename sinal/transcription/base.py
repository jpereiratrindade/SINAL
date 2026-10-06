"""Contratos e interfaces para extração de fala e transcrição."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from sinal.media.subtitles import SubtitleCue


class TranscriptionError(RuntimeError):
    """Erro durante o processo de transcrição de áudio."""


class Transcriber(ABC):
    """Interface para geradores de legendas a partir de áudio/mídia."""

    @abstractmethod
    def transcribe(self, media_path: str | Path) -> list[SubtitleCue]:
        """Transcreve o áudio da mídia em uma lista de legendas temporizadas."""
