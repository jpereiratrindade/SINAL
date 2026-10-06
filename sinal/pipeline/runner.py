"""Orquestração de ponta a ponta do pipeline SINAL."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sinal.compose import compose_libras_video
from sinal.libras import (
    MockLibrasTranslator,
    RuleBasedLibrasTranslator,
    VlibrasHttpTranslator,
    write_ir,
)
from sinal.media.prepare import prepare_media
from sinal.media.probe import inspect_media
from sinal.media.subtitles import extract_subtitles, load_srt
from sinal.render import render_libras
from sinal.transcription import transcribe_media


@dataclass(frozen=True)
class PipelineResult:
    """Resultado contendo todos os artefatos intermediários e finais do pipeline."""

    prepared_media: Path
    srt_path: Path
    ir_path: Path
    avatar_path: Path | None
    final_video: Path | None


def run_pipeline(
    media_path: str | Path,
    *,
    srt_path: str | Path | None = None,
    output_path: str | Path | None = None,
    engine: str = "mock",
    endpoint: str = "http://127.0.0.1:3000",
    allow_network: bool = False,
    render: bool = True,
    position: str = "bottom-right",
    scale: float = 0.28,
    margin: int = 24,
    overwrite: bool = False,
) -> PipelineResult:
    """Executa o pipeline completo: preparação, legendas, LIBRAS-IR, render e composição."""

    source = Path(media_path)
    if not source.is_file():
        raise FileNotFoundError(f"arquivo de mídia não encontrado: {source}")

    info = inspect_media(source)
    duration = info.duration_seconds

    # 1. Determina ou extrai legendas (SRT)
    if srt_path is not None:
        srt_file = Path(srt_path)
        if not srt_file.is_file():
            raise FileNotFoundError(f"arquivo SRT não encontrado: {srt_file}")
        cues = load_srt(srt_file)
    elif info.subtitles:
        srt_file = source.with_suffix(".extracted.srt")
        extract_subtitles(source, srt_file, overwrite=overwrite)
        cues = load_srt(srt_file)
    else:
        # Sem SRT fornecido nem embutido: executa transcrição
        cues = transcribe_media(source, engine="mock")
        srt_file = source.with_suffix(".transcribed.srt")
        # Escreve o SRT gerado
        from sinal.media.subtitles import format_timestamp

        srt_content = "\n\n".join(
            f"{c.index}\n{format_timestamp(c.start_seconds)} --> {format_timestamp(c.end_seconds)}\n{c.text}"
            for c in cues
        )
        srt_file.write_text(srt_content + "\n", encoding="utf-8")

    if not cues:
        raise ValueError("nenhuma legenda disponível para o pipeline")

    # 2. Prepara mídia com faixa de legenda incorporada
    prepared_media_path = source.with_name(f"{source.stem}.prepared.mp4")
    if prepared_media_path.resolve() != source.resolve():
        prepare_media(source, srt_file, prepared_media_path, overwrite=overwrite)
    else:
        prepared_media_path = source

    # 3. Gera e valida o LIBRAS-IR
    if engine in ("rules", "rule-based"):
        translator = RuleBasedLibrasTranslator()
    elif engine == "mock":
        translator = MockLibrasTranslator()
    elif engine == "vlibras":
        if not allow_network:
            raise ValueError(
                "--engine vlibras requer --allow-network para autorizar o envio do texto ao endpoint"
            )
        translator = VlibrasHttpTranslator(endpoint=endpoint)
    else:
        raise ValueError(f"motor de tradução desconhecido: {engine}")

    ir_document = translator.translate(cues)
    ir_file = source.with_suffix(".libras-ir.json")
    write_ir(ir_document, ir_file, overwrite=overwrite)

    avatar_file: Path | None = None
    final_file: Path | None = None

    # 4. Renderiza o avatar de Libras e compõe o vídeo final
    if render:
        avatar_file = source.with_name(f"{source.stem}.avatar.mp4")
        render_libras(
            ir_document,
            avatar_file,
            duration=duration,
            overwrite=overwrite,
        )

        final_dest = (
            Path(output_path)
            if output_path is not None
            else source.with_name(f"{source.stem}.final.mp4")
        )
        compose_libras_video(
            prepared_media_path,
            avatar_file,
            final_dest,
            position=position,
            scale=scale,
            margin=margin,
            overwrite=overwrite,
        )
        final_file = final_dest

    return PipelineResult(
        prepared_media=prepared_media_path,
        srt_path=srt_file,
        ir_path=ir_file,
        avatar_path=avatar_file,
        final_video=final_file,
    )
