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
    VlibrasHttpTranslator,
    load_ir,
    write_ir,
)
from sinal.libras.translator import LibrasTranslationError
from sinal.media.ffmpeg import FFmpegError
from sinal.media.prepare import prepare_media
from sinal.media.probe import MediaInfo, format_duration, inspect_media
from sinal.media.subtitles import NoSubtitleStreamError, extract_subtitles, load_srt


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

    process_parser = commands.add_parser(
        "process",
        help="valida vídeo + SRT e prepara um MP4 com legenda selecionável",
    )
    process_parser.add_argument("media", type=Path, help="arquivo de vídeo")
    process_parser.add_argument(
        "--srt", required=True, type=Path, help="arquivo SRT externo"
    )
    process_parser.add_argument(
        "-o", "--output", type=Path, help="MP4/MOV de saída (padrão: <vídeo>.sinal.mp4)"
    )
    process_parser.add_argument(
        "--language", default="por", help="idioma ISO 639 da legenda (padrão: por)"
    )
    process_parser.add_argument(
        "--overwrite", action="store_true", help="substitui o arquivo de saída"
    )

    ir_parser = commands.add_parser(
        "build-ir",
        help="gera LIBRAS-IR a partir de um SRT sem alegar renderização",
    )
    ir_parser.add_argument("srt", type=Path, help="arquivo SRT em português")
    ir_parser.add_argument(
        "-o", "--output", type=Path, help="JSON de saída (padrão: <SRT>.libras-ir.json)"
    )
    ir_parser.add_argument(
        "--engine",
        choices=("mock", "vlibras"),
        required=True,
        help="motor explícito: mock registra lacunas; vlibras chama uma API configurada",
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

        if args.command == "process":
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
            if args.engine == "mock":
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
    except NoSubtitleStreamError:
        print("No subtitle stream found.", file=sys.stderr)
        return 2
    except (
        FileNotFoundError,
        FileExistsError,
        ValueError,
        FFmpegError,
        LibrasTranslationError,
    ) as error:
        print(f"SINAL error: {error}", file=sys.stderr)
        return 1

    return 1


def entrypoint() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    entrypoint()
