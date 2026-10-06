"""Prepara uma mídia com um SRT externo como faixa de legenda selecionável."""

from __future__ import annotations

from pathlib import Path

from sinal.media.ffmpeg import run_ffmpeg
from sinal.media.probe import inspect_media
from sinal.media.subtitles import SubtitleCue, load_srt


def _validate_timeline(
    cues: list[SubtitleCue], media_duration: float | None, *, tolerance: float = 1.0
) -> None:
    if not cues:
        raise ValueError("o SRT não contém nenhuma legenda")

    previous_start = -1.0
    for position, cue in enumerate(cues, start=1):
        if not cue.text.strip():
            raise ValueError(f"a legenda {position} não contém texto")
        if cue.start_seconds < previous_start:
            raise ValueError(
                f"a legenda {position} está fora de ordem na linha do tempo"
            )
        previous_start = cue.start_seconds

    subtitle_end = max(cue.end_seconds for cue in cues)
    if media_duration is not None and subtitle_end > media_duration + tolerance:
        raise ValueError(
            "o SRT termina em "
            f"{subtitle_end:.3f}s, mas o vídeo termina em "
            f"{media_duration:.3f}s; gere/exporte arquivos da mesma versão"
        )


def prepare_media(
    media_path: str | Path,
    subtitle_path: str | Path,
    output_path: str | Path | None = None,
    *,
    language: str = "por",
    overwrite: bool = False,
) -> Path:
    """Valida vídeo + SRT e cria um MP4 com faixa ``mov_text`` sem recodificar."""

    source = Path(media_path)
    subtitles = Path(subtitle_path)
    destination = (
        Path(output_path)
        if output_path is not None
        else source.with_name(f"{source.stem}.sinal.mp4")
    )

    if not subtitles.is_file():
        raise FileNotFoundError(f"arquivo SRT não encontrado: {subtitles}")
    if destination.suffix.lower() not in {".mp4", ".mov"}:
        raise ValueError("a saída preparada deve usar extensão .mp4 ou .mov")
    if source.resolve() == destination.resolve():
        raise ValueError("a saída deve ser diferente do vídeo de entrada")
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"arquivo de saída já existe: {destination}; use --overwrite para substituir"
        )
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"diretório de saída não encontrado: {destination.parent}")

    info = inspect_media(source)
    if info.primary_video is None:
        raise ValueError("o arquivo de entrada não contém vídeo")
    cues = load_srt(subtitles)
    _validate_timeline(cues, info.duration_seconds)

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
            str(subtitles),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-map",
            "1:0",
            "-map_metadata",
            "0",
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            f"language={language}",
            "-metadata:s:s:0",
            "title=Português (SRT externo)",
            "-disposition:s:0",
            "default",
            "-movflags",
            "+faststart",
            str(destination),
        ]
    )
    return destination
