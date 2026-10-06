"""Detecção e extração de áudio para futuros backends de transcrição."""

from __future__ import annotations

import logging
from pathlib import Path

from sinal.media.ffmpeg import run_ffmpeg
from sinal.media.probe import AudioStream, inspect_media


LOGGER = logging.getLogger("media")


class NoAudioStreamError(RuntimeError):
    """O arquivo de entrada não contém stream de áudio."""


def _choose_audio(
    streams: tuple[AudioStream, ...], stream_index: int | None
) -> AudioStream:
    if not streams:
        raise NoAudioStreamError("No audio stream found.")
    if stream_index is not None:
        selected = next((item for item in streams if item.index == stream_index), None)
        if selected is None:
            available = ", ".join(str(item.index) for item in streams)
            raise ValueError(
                f"stream de áudio {stream_index} não encontrado; disponíveis: {available}"
            )
        return selected
    return next((item for item in streams if item.default), streams[0])


def extract_audio(
    media_path: str | Path,
    output_path: str | Path | None = None,
    *,
    stream_index: int | None = None,
    sample_rate: int = 16_000,
    channels: int = 1,
    overwrite: bool = False,
) -> Path:
    """Extrai PCM WAV adequado ao ASR futuro; não executa transcrição."""

    if sample_rate <= 0 or channels <= 0:
        raise ValueError("sample_rate e channels devem ser positivos")
    source = Path(media_path)
    info = inspect_media(source)
    stream = _choose_audio(info.audios, stream_index)
    destination = (
        Path(output_path) if output_path else source.with_suffix(".audio.wav")
    )
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"arquivo de saída já existe: {destination}; habilite overwrite para substituir"
        )
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"diretório de saída não encontrado: {destination.parent}")

    LOGGER.debug("extracting audio stream %d to %s", stream.index, destination)
    run_ffmpeg(
        [
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if overwrite else "-n",
            "-i",
            str(source),
            "-map",
            f"0:{stream.index}",
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            str(destination),
        ]
    )
    return destination
