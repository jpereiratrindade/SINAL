"""Primeiro CLI do SINAL: inspeção e extração de legendas."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

from sinal import __version__
from sinal.config import Settings
from sinal.media.ffmpeg import FFmpegError
from sinal.media.probe import MediaInfo, format_duration, inspect_media
from sinal.media.subtitles import NoSubtitleStreamError, extract_subtitles


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
    except NoSubtitleStreamError:
        print("No subtitle stream found.", file=sys.stderr)
        return 2
    except (FileNotFoundError, FileExistsError, ValueError, FFmpegError) as error:
        print(f"SINAL error: {error}", file=sys.stderr)
        return 1

    return 1


def entrypoint() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    entrypoint()

