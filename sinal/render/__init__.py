"""Módulo de renderização de Libras a partir do LIBRAS-IR.

Os renderizadores são importados de forma tardia. Além de reduzir o custo de
importação, isso impede um ciclo entre ``animation`` e ``render`` quando a
biblioteca de movimentos é usada isoladamente.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sinal.render.base import LibrasRenderError, LibrasRenderer

__all__ = [
    "LibrasRenderError",
    "LibrasRenderer",
    "SyntheticPlaceholderRenderer",
    "ThreeDLibrasRenderer",
    "VlibrasWebRuntime",
    "VlibrasWebRenderer",
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
    motion_catalog: str | Path | None = None,
    allow_unreviewed_preview: bool = False,
) -> Path:
    """Executa o renderer configurado para um documento LIBRAS-IR.

    Por padrão a renderização é *fail closed*: exige tradução revisada e
    cobertura integral por movimentos revisados. O renderer procedural padrão é
    apenas preview e nunca deve ser publicado como Libras.
    """
    if renderer is None:
        from sinal.animation.motion import MotionLibrary
        from sinal.render.three_d import ThreeDLibrasRenderer

        library = (
            MotionLibrary.from_catalog(motion_catalog)
            if motion_catalog is not None
            else MotionLibrary()
        )
        engine = ThreeDLibrasRenderer(
            motion_library=library,
            allow_unreviewed_preview=allow_unreviewed_preview,
        )
    else:
        if motion_catalog is not None or allow_unreviewed_preview:
            raise ValueError(
                "motion_catalog/allow_unreviewed_preview não podem ser usados "
                "com um renderer fornecido diretamente"
            )
        engine = renderer
    return engine.render(
        document,
        output_path,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        overwrite=overwrite,
    )


def __getattr__(name: str):
    if name == "SyntheticPlaceholderRenderer":
        from sinal.render.synthetic import SyntheticPlaceholderRenderer

        return SyntheticPlaceholderRenderer
    if name == "ThreeDLibrasRenderer":
        from sinal.render.three_d import ThreeDLibrasRenderer

        return ThreeDLibrasRenderer
    if name in {"VlibrasWebRuntime", "VlibrasWebRenderer"}:
        from sinal.render.vlibras import VlibrasWebRenderer, VlibrasWebRuntime

        return {
            "VlibrasWebRuntime": VlibrasWebRuntime,
            "VlibrasWebRenderer": VlibrasWebRenderer,
        }[name]
    raise AttributeError(name)
