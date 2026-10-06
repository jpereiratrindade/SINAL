"""Transcritor mock para desenvolvimento e testes determinísticos."""

from __future__ import annotations

from pathlib import Path

from sinal.media.probe import inspect_media
from sinal.media.subtitles import SubtitleCue
from sinal.transcription.base import Transcriber


class MockTranscriber(Transcriber):
    """Gera legendas simuladas ou utiliza legendas existentes da mídia."""

    def __init__(self, *, default_text: str = "Transcrição automática de teste.") -> None:
        self.default_text = default_text

    def transcribe(self, media_path: str | Path) -> list[SubtitleCue]:
        source = Path(media_path)
        info = inspect_media(source)

        duration = info.duration_seconds or 10.0
        # Cria segmentos de até 4 segundos uniformemente
        segment_duration = 4.0
        num_segments = max(1, int(duration // segment_duration))
        cues: list[SubtitleCue] = []

        for i in range(num_segments):
            start = i * segment_duration
            end = min((i + 1) * segment_duration, duration)
            cues.append(
                SubtitleCue(
                    index=i + 1,
                    start_seconds=start,
                    end_seconds=end,
                    text=f"{self.default_text} (trecho {i + 1})",
                )
            )
        return cues
