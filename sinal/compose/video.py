"""Composição de um vídeo de avatar já sincronizado sobre a mídia de origem."""

from __future__ import annotations

from pathlib import Path

from sinal.media.ffmpeg import run_ffmpeg
from sinal.media.probe import MediaInfo, inspect_media


POSITIONS = {"top-left", "top-right", "bottom-left", "bottom-right"}


def _require_video(info: MediaInfo, label: str) -> tuple[int, int]:
    stream = info.primary_video
    if stream is None:
        raise ValueError(f"{label} não contém vídeo")
    if stream.width is None or stream.height is None:
        raise ValueError(f"não foi possível determinar a resolução de {label}")
    return stream.width, stream.height


def _scaled_width(
    base_size: tuple[int, int],
    avatar_size: tuple[int, int],
    scale: float,
    margin: int,
) -> int:
    base_width, base_height = base_size
    avatar_width, avatar_height = avatar_size
    target_width = max(2, round(base_width * scale / 2) * 2)
    available_height = max(2, base_height - 2 * margin)
    projected_height = avatar_height * target_width / avatar_width
    if projected_height > available_height:
        target_width = max(
            2,
            round((avatar_width * available_height / avatar_height) / 2) * 2,
        )
    return target_width


def compose_libras_video(
    media_path: str | Path,
    avatar_path: str | Path,
    output_path: str | Path | None = None,
    *,
    position: str = "bottom-right",
    scale: float = 0.28,
    margin: int = 24,
    overwrite: bool = False,
    duration_tolerance: float = 1.0,
) -> Path:
    """Sobrepõe um avatar com a mesma timeline e preserva áudio e legendas."""

    source = Path(media_path)
    avatar = Path(avatar_path)
    destination = (
        Path(output_path)
        if output_path is not None
        else source.with_name(f"{source.stem}.libras.mp4")
    )

    if position not in POSITIONS:
        raise ValueError(f"posição inválida: {position}")
    if isinstance(scale, bool) or not 0 < scale <= 1:
        raise ValueError("a escala do avatar deve estar entre 0 e 1")
    if isinstance(margin, bool) or margin < 0:
        raise ValueError("a margem do avatar deve ser não negativa")
    if destination.suffix.lower() not in {".mp4", ".mov"}:
        raise ValueError("a saída composta deve usar extensão .mp4 ou .mov")
    if source.resolve() == destination.resolve() or avatar.resolve() == destination.resolve():
        raise ValueError("a saída deve ser diferente dos vídeos de entrada")
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"arquivo de saída já existe: {destination}; use --overwrite para substituir"
        )
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"diretório de saída não encontrado: {destination.parent}")

    source_info = inspect_media(source)
    avatar_info = inspect_media(avatar)
    base_size = _require_video(source_info, "a mídia de origem")
    avatar_size = _require_video(avatar_info, "o vídeo do avatar")
    if (
        source_info.duration_seconds is not None
        and avatar_info.duration_seconds is not None
        and abs(source_info.duration_seconds - avatar_info.duration_seconds)
        > duration_tolerance
    ):
        raise ValueError(
            "o vídeo do avatar deve compartilhar a timeline da origem: "
            f"origem={source_info.duration_seconds:.3f}s, "
            f"avatar={avatar_info.duration_seconds:.3f}s"
        )

    target_width = _scaled_width(base_size, avatar_size, scale, margin)
    x = str(margin) if position.endswith("left") else f"W-w-{margin}"
    y = str(margin) if position.startswith("top") else f"H-h-{margin}"
    filter_graph = (
        "[0:v:0]setpts=PTS-STARTPTS[base];"
        f"[1:v:0]setpts=PTS-STARTPTS,scale={target_width}:-2[avatar];"
        f"[base][avatar]overlay=x={x}:y={y}:eof_action=pass:shortest=0[v]"
    )

    run_ffmpeg(
        [
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if overwrite else "-n",
            "-i",
            str(source),
            "-i",
            str(avatar),
            "-filter_complex",
            filter_graph,
            "-map",
            "[v]",
            "-map",
            "0:a?",
            "-map",
            "0:s?",
            "-map_metadata",
            "0",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-c:s",
            "mov_text",
            "-movflags",
            "+faststart",
            str(destination),
        ]
    )
    return destination
