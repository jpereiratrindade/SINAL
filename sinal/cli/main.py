"""CLI do SINAL para mídia, legendas e LIBRAS-IR."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

from sinal import __version__
from sinal.compose import POSITIONS, compose_libras_video
from sinal.config import Settings
from sinal.libras import (
    MockLibrasTranslator,
    RuleBasedLibrasTranslator,
    VlibrasHttpTranslator,
    load_ir,
    write_ir,
)
from sinal.libras.translator import LibrasTranslationError
from sinal.media.ffmpeg import FFmpegError
from sinal.media.prepare import prepare_media
from sinal.media.probe import MediaInfo, format_duration, inspect_media
from sinal.media.subtitles import (
    NoSubtitleStreamError,
    extract_subtitles,
    format_timestamp,
    load_srt,
    write_srt,
)
from sinal.pipeline import run_pipeline
from sinal.render import LibrasRenderError, render_libras
from sinal.render.readiness import audit_render_readiness
from sinal.transcription import TranscriptionError, transcribe_media


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sinal",
        description="Sistema Inteligente de Acessibilidade Narrativa em Libras",
    )
    parser.add_argument("--version", action="version", version=f"SINAL {__version__}")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="exibe logs operacionais"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    inspect_parser = commands.add_parser(
        "inspect", help="inspeciona os streams de um arquivo de mídia"
    )
    inspect_parser.add_argument("media", type=Path, help="arquivo de vídeo ou áudio")
    inspect_parser.add_argument(
        "--json", action="store_true", help="emite o resultado como JSON"
    )

    extract_parser = commands.add_parser(
        "extract-subtitles", help="extrai uma legenda incorporada como SRT"
    )
    extract_parser.add_argument("media", type=Path, help="arquivo de vídeo")
    extract_parser.add_argument("-o", "--output", type=Path, help="arquivo SRT de saída")
    extract_parser.add_argument(
        "--stream", type=int, help="índice absoluto do stream retornado pelo FFprobe"
    )
    extract_parser.add_argument(
        "--overwrite", action="store_true", help="substitui o arquivo de saída"
    )

    transcribe_parser = commands.add_parser(
        "transcribe", help="transcreve o áudio da mídia para um arquivo SRT"
    )
    transcribe_parser.add_argument("media", type=Path, help="arquivo de mídia/áudio")
    transcribe_parser.add_argument(
        "-o", "--output", type=Path, help="arquivo SRT de saída (padrão: <mídia>.srt)"
    )
    transcribe_parser.add_argument(
        "--engine",
        choices=("mock", "whisper"),
        default="mock",
        help="motor de transcrição (padrão: %(default)s)",
    )
    transcribe_parser.add_argument(
        "--overwrite", action="store_true", help="substitui o arquivo de saída"
    )

    process_parser = commands.add_parser(
        "process",
        help="executa o pipeline SINAL de preparação, LIBRAS-IR, render e composição",
    )
    process_parser.add_argument("media", type=Path, help="arquivo de vídeo")
    process_parser.add_argument(
        "--srt", type=Path, help="arquivo SRT externo opcional"
    )
    process_parser.add_argument(
        "-o", "--output", type=Path, help="MP4/MOV final de saída (padrão: <vídeo>.sinal.mp4)"
    )
    process_parser.add_argument(
        "--render",
        action="store_true",
        help="solicita avatar e composição; falha sem backend/catálogo validados",
    )
    process_parser.add_argument(
        "--engine",
        choices=("rules", "rule-based", "mock", "vlibras"),
        default="mock",
        help="motor de tradução LIBRAS-IR (padrão: %(default)s)",
    )
    process_parser.add_argument(
        "--motion-catalog",
        type=Path,
        help="catálogo JSON de movimentos de Libras revisado por especialista",
    )
    process_parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:3000",
        help="URL base de uma instância VLibras API (padrão: %(default)s)",
    )
    process_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="autoriza o envio do texto ao endpoint VLibras",
    )
    process_parser.add_argument(
        "--position",
        choices=sorted(POSITIONS),
        default="bottom-right",
        help="posição do avatar no vídeo (padrão: %(default)s)",
    )
    process_parser.add_argument(
        "--scale",
        type=float,
        default=0.28,
        help="fração da largura ocupada pelo avatar (padrão: %(default)s)",
    )
    process_parser.add_argument(
        "--language", default="por", help="idioma ISO 639 da legenda (padrão: por)"
    )
    process_parser.add_argument(
        "--overwrite", action="store_true", help="substitui o arquivo de saída"
    )

    ir_parser = commands.add_parser(
        "build-ir",
        help="gera LIBRAS-IR a partir de um SRT",
    )
    ir_parser.add_argument("srt", type=Path, help="arquivo SRT em português")
    ir_parser.add_argument(
        "-o", "--output", type=Path, help="JSON de saída (padrão: <SRT>.libras-ir.json)"
    )
    ir_parser.add_argument(
        "--engine",
        choices=("rules", "rule-based", "mock", "vlibras"),
        default="mock",
        help="motor de tradução: rules (protótipo lexical), mock (lacunas) ou vlibras (padrão: %(default)s)",
    )
    ir_parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:3000",
        help="URL base de uma instância VLibras API (padrão: %(default)s)",
    )
    ir_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="autoriza o envio do texto à instância definida por --endpoint",
    )
    ir_parser.add_argument(
        "--overwrite", action="store_true", help="substitui o arquivo de saída"
    )

    validate_parser = commands.add_parser(
        "validate-ir", help="valida um documento LIBRAS-IR 0.1.0"
    )
    validate_parser.add_argument("document", type=Path, help="arquivo JSON LIBRAS-IR")

    render_parser = commands.add_parser(
        "render", help="gera preview procedural; a saída não é Libras publicável"
    )
    render_parser.add_argument("document", type=Path, help="arquivo JSON LIBRAS-IR")
    render_parser.add_argument(
        "--media", type=Path, help="mídia de origem de referência para a duração"
    )
    render_parser.add_argument(
        "--duration", type=float, help="duração total do vídeo em segundos"
    )
    render_parser.add_argument(
        "-o", "--output", type=Path, help="MP4 de saída do avatar (padrão: <document>.avatar.mp4)"
    )
    render_parser.add_argument(
        "--fps", type=int, default=30, help="taxa de quadros por segundo (padrão: %(default)s)"
    )
    render_parser.add_argument(
        "--motion-catalog",
        type=Path,
        help="catálogo JSON de movimentos de Libras revisado por especialista",
    )
    render_parser.add_argument(
        "--allow-unreviewed-preview",
        action="store_true",
        help="gera somente uma prévia técnica com aviso visível; não é Libras publicável",
    )
    render_parser.add_argument(
        "--overwrite", action="store_true", help="substitui o arquivo de saída"
    )

    audit_parser = commands.add_parser(
        "audit-render",
        help="verifica revisão e cobertura de movimentos antes de renderizar",
    )
    audit_parser.add_argument("document", type=Path, help="arquivo JSON LIBRAS-IR")
    audit_parser.add_argument(
        "--motion-catalog",
        type=Path,
        help="catálogo JSON de movimentos a auditar; sem ele, audita os protótipos internos",
    )
    audit_parser.add_argument("--json", action="store_true", help="emite o relatório como JSON")

    compose_parser = commands.add_parser(
        "compose", help="sobrepõe um vídeo de avatar já sincronizado à mídia"
    )
    compose_parser.add_argument("media", type=Path, help="vídeo de origem")
    compose_parser.add_argument(
        "--avatar", required=True, type=Path, help="vídeo do avatar na mesma timeline"
    )
    compose_parser.add_argument(
        "-o", "--output", type=Path, help="MP4/MOV final (padrão: <vídeo>.libras.mp4)"
    )
    compose_parser.add_argument(
        "--position",
        choices=sorted(POSITIONS),
        default="bottom-right",
        help="posição do avatar (padrão: %(default)s)",
    )
    compose_parser.add_argument(
        "--scale",
        type=float,
        default=0.28,
        help="fração da largura ocupada pelo avatar (padrão: %(default)s)",
    )
    compose_parser.add_argument(
        "--margin", type=int, default=24, help="margem em pixels (padrão: %(default)s)"
    )
    compose_parser.add_argument(
        "--overwrite", action="store_true", help="substitui o arquivo de saída"
    )

    export_parser = commands.add_parser(
        "export-avatar", help="exporta o modelo 3D da SINA em formato padrão GLB / glTF 2.0"
    )
    export_parser.add_argument(
        "-o", "--output", type=Path, default=Path("sina.glb"), help="arquivo de saída .glb (padrão: %(default)s)"
    )
    export_parser.add_argument(
        "--pose", default="REST", help="pose da SINA a exportar (ex: REST, OLA, OI, COMPLEXO, CHEIO, VIDA)"
    )
    export_parser.add_argument(
        "--overwrite", action="store_true", help="substitui o arquivo de saída"
    )
    return parser


def _configure_logging(verbose: bool) -> None:
    settings = Settings.from_environment()
    level = logging.DEBUG if verbose else getattr(logging, settings.log_level, logging.INFO)
    logging.basicConfig(
        level=level,
        format="[SINAL][%(name)s] %(message)s",
    )


def _display(value: object | None) -> str:
    return str(value) if value not in (None, "") else "unknown"


def _render_inspection(info: MediaInfo) -> str:
    lines = [f"SINAL {__version__}", "", "Input:", f"  {info.path}", "", "Video:"]
    video = info.primary_video
    if video is None:
        lines.append("  no")
    else:
        resolution = (
            f"{video.width}x{video.height}"
            if video.width is not None and video.height is not None
            else "unknown"
        )
        lines.extend(
            [
                f"  codec: {video.codec}",
                f"  resolution: {resolution}",
                f"  duration: {format_duration(info.duration_seconds)}",
            ]
        )

    lines.extend(["", "Audio:"])
    audio = info.primary_audio
    if audio is None:
        lines.append("  no")
    else:
        lines.extend(
            [
                "  yes",
                f"  stream: {audio.index}",
                f"  codec: {audio.codec}",
                f"  language: {_display(audio.language)}",
            ]
        )

    lines.extend(["", "Subtitles:"])
    if not info.subtitles:
        lines.append("  no")
    else:
        lines.append("  yes")
        for position, subtitle in enumerate(info.subtitles):
            prefix = "  " if position == 0 else "  additional "
            lines.extend(
                [
                    f"{prefix}stream: {subtitle.index}",
                    f"{prefix}codec: {subtitle.codec}",
                    f"{prefix}language: {_display(subtitle.language)}",
                ]
            )
    return "\n".join(lines)


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    _configure_logging(args.verbose)
    logger = logging.getLogger("cli")

    try:
        if args.command == "inspect":
            logger.debug("inspecting %s", args.media)
            info = inspect_media(args.media)
            if args.json:
                print(json.dumps(info.to_dict(), ensure_ascii=False, indent=2))
            else:
                print(_render_inspection(info))
            return 0

        if args.command == "extract-subtitles":
            logger.debug("extracting subtitles from %s", args.media)
            destination = extract_subtitles(
                args.media,
                args.output,
                stream_index=args.stream,
                overwrite=args.overwrite,
            )
            print(f"Subtitle extracted: {destination}")
            return 0

        if args.command == "transcribe":
            logger.debug("transcribing %s", args.media)
            cues = transcribe_media(args.media, engine=args.engine)
            destination = write_srt(
                cues,
                args.output or args.media.with_suffix(".srt"),
                overwrite=args.overwrite,
            )
            print(f"Transcription completed ({len(cues)} cues): {destination}")
            return 0

        if args.command == "process":
            if args.render:
                logger.debug("running full pipeline on %s", args.media)
                result = run_pipeline(
                    args.media,
                    srt_path=args.srt,
                    output_path=args.output,
                    engine=args.engine,
                    endpoint=args.endpoint,
                    allow_network=args.allow_network,
                    render=True,
                    position=args.position,
                    scale=args.scale,
                    motion_catalog=args.motion_catalog,
                    overwrite=args.overwrite,
                )
                print(f"Media prepared: {result.prepared_media}")
                print(f"LIBRAS-IR generated: {result.ir_path}")
                if result.avatar_path:
                    print(f"Avatar rendered: {result.avatar_path}")
                if result.final_video:
                    print(f"Final video composed: {result.final_video}")
                return 0

            # Modo de preparação básica de mídia
            if not args.srt:
                raise ValueError("especifique --srt ou use --render para executar o pipeline completo")
            logger.debug("preparing %s with subtitles %s", args.media, args.srt)
            destination = prepare_media(
                args.media,
                args.srt,
                args.output,
                language=args.language,
                overwrite=args.overwrite,
            )
            print(f"Media prepared: {destination}")
            print("Subtitle track embedded; use build-ir to prepare the translation stage.")
            return 0

        if args.command == "build-ir":
            cues = load_srt(args.srt)
            if not cues:
                raise ValueError("o SRT não contém nenhuma legenda")
            destination = args.output or args.srt.with_suffix(".libras-ir.json")
            if args.engine in ("rules", "rule-based"):
                translator = RuleBasedLibrasTranslator()
            elif args.engine == "mock":
                translator = MockLibrasTranslator()
            else:
                if not args.allow_network:
                    raise ValueError(
                        "--engine vlibras requer --allow-network para autorizar o "
                        "envio do texto ao endpoint configurado"
                    )
                translator = VlibrasHttpTranslator(endpoint=args.endpoint)
            document = translator.translate(cues)
            written = write_ir(document, destination, overwrite=args.overwrite)
            print(f"LIBRAS-IR written: {written}")
            if args.engine == "mock":
                print("Translation pending: mock recorded gaps and generated no signs.")
            elif args.engine in ("rules", "rule-based"):
                print(
                    "Experimental lexical pre-glosses generated; this is not a "
                    "reviewed Libras translation and production rendering will be blocked."
                )
            else:
                print("Machine translation generated; human Libras review is required.")
            return 0

        if args.command == "validate-ir":
            document = load_ir(args.document)
            print(
                f"Valid LIBRAS-IR {document['version']}: "
                f"{len(document['utterances'])} utterance(s)"
            )
            return 0

        if args.command == "audit-render":
            from sinal.animation.motion import MotionLibrary

            document = load_ir(args.document)
            library = (
                MotionLibrary.from_catalog(args.motion_catalog)
                if args.motion_catalog is not None
                else MotionLibrary()
            )
            report = audit_render_readiness(document, library)
            if args.json:
                print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
            else:
                state = "PRONTO" if report.ready else "BLOQUEADO"
                print(
                    f"Render: {state} — {report.covered_signs}/{report.total_signs} "
                    "sinais cobertos por movimentos revisados"
                )
                for issue in report.issues:
                    location = ""
                    if issue.utterance_index is not None:
                        location = f" [enunciado {issue.utterance_index + 1}"
                        if issue.sign_index is not None:
                            location += f", sinal {issue.sign_index + 1}"
                        location += "]"
                    print(f"- {issue.code}{location}: {issue.message}")
            return 0 if report.ready else 1

        if args.command == "render":
            logger.debug("rendering %s", args.document)
            document = load_ir(args.document)
            duration = args.duration
            if duration is None and args.media is not None:
                info = inspect_media(args.media)
                duration = info.duration_seconds

            destination = render_libras(
                document,
                args.output or args.document.with_suffix(".avatar.mp4"),
                duration=duration,
                fps=args.fps,
                overwrite=args.overwrite,
                motion_catalog=args.motion_catalog,
                allow_unreviewed_preview=args.allow_unreviewed_preview,
            )
            print(f"Technical avatar preview rendered (NOT validated Libras): {destination}")
            return 0

        if args.command == "compose":
            destination = compose_libras_video(
                args.media,
                args.avatar,
                args.output,
                position=args.position,
                scale=args.scale,
                margin=args.margin,
                overwrite=args.overwrite,
            )
            print(f"Libras video composed: {destination}")
            return 0

        if args.command == "export-avatar":
            from sinal.avatar.gltf_export import export_sina_glb
            from sinal.render.poses import get_sign_pose
            dest = Path(args.output)
            if dest.exists() and not args.overwrite:
                raise FileExistsError(f"arquivo de saída já existe: {dest}; use --overwrite para substituir")
            pose = get_sign_pose(args.pose, 1.0)
            exported = export_sina_glb(dest, pose=pose)
            print(f"SINA 3D model exported: {exported} (glTF 2.0 / GLB)")
            return 0
    except NoSubtitleStreamError:
        print("No subtitle stream found.", file=sys.stderr)
        return 2
    except (
        FileNotFoundError,
        FileExistsError,
        ValueError,
        FFmpegError,
        LibrasTranslationError,
        LibrasRenderError,
        TranscriptionError,
    ) as error:
        print(f"SINAL error: {error}", file=sys.stderr)
        return 1

    return 1


def entrypoint() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    entrypoint()
