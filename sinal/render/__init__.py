"""Módulo de renderização de Libras a partir do LIBRAS-IR."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sinal.render.base import LibrasRenderError, LibrasRenderer
from sinal.render.synthetic import SyntheticPlaceholderRenderer

__all__ = [
    "LibrasRenderError",
    "LibrasRenderer",
    "SyntheticPlaceholderRenderer",
    "render_libras",
]


def render_libras(
    document: dict[str, Any],
    output_path: str | Path | None = None,
    *,
    renderer: LibrasRenderer | None = None,
    duration: float | None = None,
    width: int = 640,
    height: int = 1080,
    fps: int = 30,
    overwrite: bool = False,
) -> Path:
    """Renderiza um documento LIBRAS-IR em vídeo de avatar."""
    engine = renderer or SyntheticPlaceholderRenderer()
    return engine.render(
        document,
        output_path,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        overwrite=overwrite,
    )
