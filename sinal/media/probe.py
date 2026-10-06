"""Modelo tipado e inspeção dos streams de um arquivo de mídia."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sinal.media.ffmpeg import run_ffprobe


LOGGER = logging.getLogger("media")


@dataclass(frozen=True, slots=True)
class VideoStream:
    index: int
    codec: str
    width: int | None
    height: int | None
    language: str | None
    default: bool


@dataclass(frozen=True, slots=True)
class AudioStream:
    index: int
    codec: str
    channels: int | None
    sample_rate: int | None
    language: str | None
    default: bool


@dataclass(frozen=True, slots=True)
class SubtitleStream:
    index: int
    codec: str
    language: str | None
    title: str | None
    default: bool
    forced: bool


@dataclass(frozen=True, slots=True)
class MediaInfo:
    path: Path
    duration_seconds: float | None
    format_name: str | None
    videos: tuple[VideoStream, ...]
    audios: tuple[AudioStream, ...]
    subtitles: tuple[SubtitleStream, ...]

    @property
    def primary_video(self) -> VideoStream | None:
        return _primary(self.videos)

    @property
    def primary_audio(self) -> AudioStream | None:
        return _primary(self.audios)

    @property
    def has_audio(self) -> bool:
        return bool(self.audios)

    @property
    def has_subtitles(self) -> bool:
        return bool(self.subtitles)

    def to_dict(self) -> dict[str, Any]:
        document = asdict(self)
        document["path"] = str(self.path)
        return document


def _primary(streams: tuple[Any, ...]) -> Any | None:
    if not streams:
        return None
    return next((stream for stream in streams if stream.default), streams[0])


def _integer(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _floating(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _text(value: object) -> str | None:
    return str(value) if value not in (None, "") else None


def _tags(stream: dict[str, Any]) -> dict[str, Any]:
    value = stream.get("tags")
    return value if isinstance(value, dict) else {}


def _disposition(stream: dict[str, Any], name: str) -> bool:
    value = stream.get("disposition")
    return bool(value.get(name, 0)) if isinstance(value, dict) else False


def inspect_media(media_path: str | Path) -> MediaInfo:
    """Inspeciona vídeo, áudio e legendas por meio de FFprobe."""

    path = Path(media_path)
    document = run_ffprobe(path)
    raw_streams = document.get("streams", [])
    streams = raw_streams if isinstance(raw_streams, list) else []

    videos: list[VideoStream] = []
    audios: list[AudioStream] = []
    subtitles: list[SubtitleStream] = []

    for stream in streams:
        if not isinstance(stream, dict):
            continue
        index = _integer(stream.get("index"))
        if index is None:
            continue
        codec_type = stream.get("codec_type")
        codec = _text(stream.get("codec_name")) or "unknown"
        tags = _tags(stream)
        language = _text(tags.get("language"))

        if codec_type == "video":
            videos.append(
                VideoStream(
                    index=index,
                    codec=codec,
                    width=_integer(stream.get("width")),
                    height=_integer(stream.get("height")),
                    language=language,
                    default=_disposition(stream, "default"),
                )
            )
        elif codec_type == "audio":
            audios.append(
                AudioStream(
                    index=index,
                    codec=codec,
                    channels=_integer(stream.get("channels")),
                    sample_rate=_integer(stream.get("sample_rate")),
                    language=language,
                    default=_disposition(stream, "default"),
                )
            )
        elif codec_type == "subtitle":
            subtitles.append(
                SubtitleStream(
                    index=index,
                    codec=codec,
                    language=language,
                    title=_text(tags.get("title")),
                    default=_disposition(stream, "default"),
                    forced=_disposition(stream, "forced"),
                )
            )

    raw_format = document.get("format")
    media_format = raw_format if isinstance(raw_format, dict) else {}
    duration = _floating(media_format.get("duration"))
    if duration is None:
        duration = next(
            (
                parsed
                for stream in streams
                if isinstance(stream, dict)
                and (parsed := _floating(stream.get("duration"))) is not None
            ),
            None,
        )

    info = MediaInfo(
        path=path,
        duration_seconds=duration,
        format_name=_text(media_format.get("format_name")),
        videos=tuple(videos),
        audios=tuple(audios),
        subtitles=tuple(subtitles),
    )
    LOGGER.debug(
        "probe complete: video=%d audio=%d subtitles=%d",
        len(info.videos),
        len(info.audios),
        len(info.subtitles),
    )
    return info


def format_duration(seconds: float | None) -> str:
    """Formata segundos como HH:MM:SS, ou ``unknown`` quando ausentes."""

    if seconds is None or seconds < 0:
        return "unknown"
    rounded = int(seconds + 0.5)
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
