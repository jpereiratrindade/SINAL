"""Contratos e interfaces para renderização de Libras."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class LibrasRenderError(RuntimeError):
    """Erro durante o processo de renderização de Libras."""


class LibrasRenderer(ABC):
    """Interface base para renderizadores de avatar a partir do LIBRAS-IR."""

    @abstractmethod
    def render(
        self,
        document: dict[str, Any],
        output_path: str | Path | None = None,
        *,
        duration: float | None = None,
        width: int = 640,
        height: int = 1080,
        fps: int = 30,
        overwrite: bool = False,
    ) -> Path:
        """Renderiza o documento LIBRAS-IR em um arquivo de vídeo sincronizado."""
