"""Seleção, extração e leitura de legendas SubRip (SRT)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from sinal.media.ffmpeg import run_ffmpeg
from sinal.media.probe import SubtitleStream, inspect_media


LOGGER = logging.getLogger("media")


class NoSubtitleStreamError(RuntimeError):
    """O arquivo de entrada não contém stream de legenda."""


@dataclass(frozen=True, slots=True)
class SubtitleCue:
    index: int
    start_seconds: float
    end_seconds: float
    text: str


_TIMING = re.compile(
    r"^\s*(?P<start>\d{1,3}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"(?P<end>\d{1,3}:\d{2}:\d{2}[,.]\d{3})(?:\s+.*)?$"
)


def timestamp_to_seconds(timestamp: str) -> float:
    """Converte timestamp SRT ``HH:MM:SS,mmm`` em segundos."""

    normalized = timestamp.strip().replace(".", ",")
    try:
        clock, milliseconds = normalized.rsplit(",", 1)
        hours, minutes, seconds = (int(part) for part in clock.split(":"))
        millis = int(milliseconds)
    except (ValueError, TypeError) as error:
        raise ValueError(f"timestamp SRT inválido: {timestamp!r}") from error
    if not (0 <= minutes < 60 and 0 <= seconds < 60 and len(milliseconds) == 3):
        raise ValueError(f"timestamp SRT inválido: {timestamp!r}")
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def parse_srt(content: str) -> list[SubtitleCue]:
    """Lê conteúdo SRT, incluindo texto multilinha e fim de linha Windows."""

    normalized = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n[ \t]*\n", normalized.strip()) if normalized.strip() else []
    cues: list[SubtitleCue] = []

    for ordinal, block in enumerate(blocks, start=1):
        lines = block.splitlines()
        timing_position = next(
            (position for position, line in enumerate(lines[:2]) if _TIMING.match(line)),
            None,
        )
        if timing_position is None:
            raise ValueError(f"bloco SRT {ordinal} não contém linha de tempo válida")

        match = _TIMING.match(lines[timing_position])
        assert match is not None
        if timing_position == 1:
            try:
                cue_index = int(lines[0].strip())
            except ValueError as error:
                raise ValueError(f"índice SRT inválido no bloco {ordinal}") from error
        else:
            cue_index = ordinal

        start = timestamp_to_seconds(match.group("start"))
        end = timestamp_to_seconds(match.group("end"))
        if end < start:
            raise ValueError(f"intervalo SRT invertido no bloco {ordinal}")
        text = "\n".join(lines[timing_position + 1 :]).strip()
        cues.append(SubtitleCue(cue_index, start, end, text))

    return cues


def load_srt(path: str | Path) -> list[SubtitleCue]:
    """Lê um arquivo SRT em UTF-8 (com BOM opcional)."""

    return parse_srt(Path(path).read_text(encoding="utf-8-sig"))


def _choose_stream(
    subtitles: tuple[SubtitleStream, ...], stream_index: int | None
) -> SubtitleStream:
    if not subtitles:
        raise NoSubtitleStreamError("No subtitle stream found.")
    if stream_index is not None:
        selected = next((item for item in subtitles if item.index == stream_index), None)
        if selected is None:
            available = ", ".join(str(item.index) for item in subtitles)
            raise ValueError(
                f"stream de legenda {stream_index} não encontrado; disponíveis: {available}"
            )
        return selected
    return next((item for item in subtitles if item.default), subtitles[0])


def extract_subtitles(
    media_path: str | Path,
    output_path: str | Path | None = None,
    *,
    stream_index: int | None = None,
    overwrite: bool = False,
) -> Path:
    """Extrai uma legenda textual para SRT e retorna o caminho produzido."""

    source = Path(media_path)
    info = inspect_media(source)
    stream = _choose_stream(info.subtitles, stream_index)
    destination = Path(output_path) if output_path else source.with_suffix(".srt")
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"arquivo de saída já existe: {destination}; use --overwrite para substituir"
        )
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"diretório de saída não encontrado: {destination.parent}")

    LOGGER.debug("extracting subtitle stream %d to %s", stream.index, destination)
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
            "-c:s",
            "srt",
            "-f",
            "srt",
            str(destination),
        ]
    )
    return destination
