"""Execução segura e centralizada das ferramentas FFmpeg.

Este módulo é a única fronteira da Fase 1 que cria subprocessos para FFmpeg e
FFprobe. Os demais módulos passam listas de argumentos, nunca comandos de shell.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any


class FFmpegError(RuntimeError):
    """Erro ao localizar ou executar uma ferramenta FFmpeg."""


class ExecutableNotFoundError(FFmpegError):
    """A ferramenta externa solicitada não está disponível."""


class FFmpegProcessError(FFmpegError):
    """Uma ferramenta FFmpeg terminou com código de erro."""

    def __init__(self, executable: str, returncode: int, stderr: str) -> None:
        detail = stderr.strip() or "sem detalhes no stderr"
        super().__init__(
            f"{executable} terminou com código {returncode}: {detail}"
        )
        self.executable = executable
        self.returncode = returncode
        self.stderr = stderr


def _resolve_executable(configured: str) -> str:
    """Resolve um executável configurado por nome ou caminho explícito."""

    candidate = Path(configured).expanduser()
    if candidate.parent != Path(".") or candidate.is_absolute():
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        raise ExecutableNotFoundError(
            f"executável não encontrado ou sem permissão: {configured}"
        )

    resolved = shutil.which(configured)
    if resolved is None:
        raise ExecutableNotFoundError(
            f"executável '{configured}' não encontrado no PATH"
        )
    return resolved


def _run(executable: str, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    command = [_resolve_executable(executable), *map(str, arguments)]
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        raise FFmpegError(f"não foi possível executar {executable}: {error}") from error


def run_ffprobe(
    media_path: str | Path,
    *,
    executable: str | None = None,
) -> dict[str, Any]:
    """Retorna a saída JSON do FFprobe para um arquivo de mídia."""

    path = Path(media_path)
    if not path.is_file():
        raise FileNotFoundError(f"arquivo de mídia não encontrado: {path}")

    program = executable or os.environ.get("SINAL_FFPROBE", "ffprobe")
    result = _run(
        program,
        [
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
    )
    if result.returncode != 0:
        raise FFmpegProcessError(program, result.returncode, result.stderr)

    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise FFmpegError(f"FFprobe retornou JSON inválido: {error}") from error
    if not isinstance(document, dict):
        raise FFmpegError("FFprobe retornou uma raiz JSON que não é um objeto")
    return document


def run_ffmpeg(
    arguments: Sequence[str],
    *,
    executable: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Executa FFmpeg sem shell e lança uma exceção em caso de falha."""

    program = executable or os.environ.get("SINAL_FFMPEG", "ffmpeg")
    result = _run(program, arguments)
    if result.returncode != 0:
        raise FFmpegProcessError(program, result.returncode, result.stderr)
    return result

