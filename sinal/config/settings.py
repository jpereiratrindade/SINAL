"""Configuração central e imutável usada pelas camadas do SINAL."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class InputSettings:
    language: str = "pt-BR"


@dataclass(frozen=True, slots=True)
class TranscriptionSettings:
    engine: str = "whisper"
    model: str = "small"


@dataclass(frozen=True, slots=True)
class LibrasSettings:
    engine: str = "vlibras"


@dataclass(frozen=True, slots=True)
class RenderSettings:
    mode: str = "overlay"
    avatar_scale: float = 0.28
    position: str = "bottom-right"


@dataclass(frozen=True, slots=True)
class OutputSettings:
    keep_intermediate: bool = True


@dataclass(frozen=True, slots=True)
class ToolSettings:
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"


@dataclass(frozen=True, slots=True)
class Settings:
    input: InputSettings = field(default_factory=InputSettings)
    transcription: TranscriptionSettings = field(default_factory=TranscriptionSettings)
    libras: LibrasSettings = field(default_factory=LibrasSettings)
    render: RenderSettings = field(default_factory=RenderSettings)
    output: OutputSettings = field(default_factory=OutputSettings)
    tools: ToolSettings = field(default_factory=ToolSettings)
    log_level: str = "INFO"

    @classmethod
    def from_environment(cls) -> "Settings":
        """Carrega somente os ajustes operacionais permitidos via ambiente."""

        return cls(
            tools=ToolSettings(
                ffmpeg=os.environ.get("SINAL_FFMPEG", "ffmpeg"),
                ffprobe=os.environ.get("SINAL_FFPROBE", "ffprobe"),
            ),
            log_level=os.environ.get("SINAL_LOG_LEVEL", "INFO").upper(),
        )

