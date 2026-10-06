"""Captura segura do player WebGL oficial e atual do VLibras."""

from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any

from sinal.libras.ir import validate_ir
from sinal.media.ffmpeg import detect_video_encoder, run_ffmpeg
from sinal.media.probe import inspect_media
from sinal.render.base import LibrasRenderError, LibrasRenderer


VLIBRAS_AVATARS = frozenset({"icaro", "hosana", "guga"})
HUMAN_REVIEW_STATUSES = frozenset({"human-reviewed", "human-corrected", "approved"})


@dataclass(frozen=True, slots=True)
class VlibrasCaptureResult:
    recording: Path
    trim_offset_seconds: float
    animation_seconds: float
    completed_signs: int
    total_signs: int


class _QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: object, control_document: bytes, **kwargs: object) -> None:
        self.control_document = control_document
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args: object) -> None:
        return None

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/__sinal_control__.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(self.control_document)))
            self.end_headers()
            self.wfile.write(self.control_document)
            return
        super().do_GET()


class VlibrasWebRuntime:
    """Runtime local de um checkout compilado do widget oficial VLibras."""

    def __init__(
        self,
        root: str | Path,
        *,
        node_executable: str = "node",
        chromium_executable: str | Path | None = None,
        timeout_seconds: float = 600.0,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.app_root = self.root / "app"
        self.node_executable = node_executable
        self.chromium_executable = (
            Path(chromium_executable).expanduser().resolve()
            if chromium_executable is not None
            else None
        )
        self.timeout_seconds = timeout_seconds
        self.version = self._validate()

    @classmethod
    def from_environment(
        cls,
        root: str | Path | None = None,
        *,
        chromium_executable: str | Path | None = None,
        timeout_seconds: float = 600.0,
    ) -> "VlibrasWebRuntime":
        data_home = Path(
            os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
        )
        default_root = data_home / "sinal" / "vlibras-web-browsers"
        configured_root = root or os.environ.get("SINAL_VLIBRAS_WEB_ROOT")
        if configured_root is None and default_root.is_dir():
            configured_root = default_root
        if configured_root is None:
            raise LibrasRenderError(
                "runtime VLibras não configurado; defina SINAL_VLIBRAS_WEB_ROOT "
                f"ou instale o checkout oficial compilado em {default_root}"
            )
        return cls(
            configured_root,
            node_executable=os.environ.get("SINAL_NODE", "node"),
            chromium_executable=(
                chromium_executable or os.environ.get("SINAL_VLIBRAS_CHROMIUM") or None
            ),
            timeout_seconds=timeout_seconds,
        )

    def _validate(self) -> str:
        required = (
            self.app_root / "unity" / "index.html",
            self.app_root / "unity" / "playerweb.data.unityweb",
            self.root / "node_modules" / "@playwright" / "test" / "index.mjs",
            self.root / "package.json",
        )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise LibrasRenderError(
                "runtime VLibras incompleto; execute pnpm install, pnpm build e "
                f"playwright install chromium. Ausente: {missing[0]}"
            )
        if shutil.which(self.node_executable) is None and not Path(self.node_executable).is_file():
            raise LibrasRenderError(f"Node.js não encontrado: {self.node_executable}")
        if self.chromium_executable is not None and not self.chromium_executable.is_file():
            raise LibrasRenderError(
                f"Chromium configurado não foi encontrado: {self.chromium_executable}"
            )
        try:
            package = json.loads((self.root / "package.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise LibrasRenderError("package.json inválido no runtime VLibras") from error
        return str(package.get("version") or "unknown")

    def capture(
        self,
        gloss: str,
        capture_directory: Path,
        *,
        avatar: str,
        width: int,
        height: int,
    ) -> VlibrasCaptureResult:
        if avatar not in VLIBRAS_AVATARS:
            raise ValueError(f"avatar VLibras inválido: {avatar}")
        capture_directory.mkdir(parents=True, exist_ok=True)
        control_document = files("sinal.render.assets").joinpath("vlibras_control.html").read_bytes()
        handler = functools.partial(
            _QuietHandler,
            directory=str(self.app_root),
            control_document=control_document,
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        helper = files("sinal.render.assets").joinpath("vlibras_capture.mjs")
        payload = {
            "runtimeRoot": str(self.root),
            "controlUrl": f"http://127.0.0.1:{server.server_port}/__sinal_control__.html",
            "captureDirectory": str(capture_directory),
            "chromiumExecutable": (
                str(self.chromium_executable) if self.chromium_executable else None
            ),
            "gloss": gloss,
            "avatar": avatar,
            "width": width,
            "height": height,
            "timeoutMs": int(self.timeout_seconds * 1000),
            "dictionaryUrl": "https://dicionario2.vlibras.gov.br/2018.3.1/WEBGL/",
        }
        try:
            result = subprocess.run(
                [self.node_executable, str(helper)],
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds + 30,
                check=False,
                cwd=self.root,
            )
        except subprocess.TimeoutExpired as error:
            raise LibrasRenderError(
                f"player VLibras excedeu {self.timeout_seconds:g}s para sinalizar"
            ) from error
        except OSError as error:
            raise LibrasRenderError(f"não foi possível iniciar o player VLibras: {error}") from error
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        if result.returncode != 0:
            error_lines = result.stderr.strip().splitlines()
            detail = " | ".join(error_lines[-20:]) if error_lines else "sem detalhes"
            raise LibrasRenderError(f"captura do player VLibras falhou: {detail}")
        try:
            response = json.loads(result.stdout.strip().splitlines()[-1])
            capture = VlibrasCaptureResult(
                recording=Path(response["recording"]),
                trim_offset_seconds=float(response["trimOffsetSeconds"]),
                animation_seconds=float(response["animationSeconds"]),
                completed_signs=int(response["completedSigns"]),
                total_signs=int(response["totalSigns"]),
            )
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise LibrasRenderError("capturador VLibras retornou metadados inválidos") from error
        if not capture.recording.is_file() or capture.total_signs <= 0:
            raise LibrasRenderError("player VLibras não produziu uma animação completa")
        if capture.completed_signs != capture.total_signs:
            raise LibrasRenderError(
                "player VLibras terminou sem executar todos os sinais "
                f"({capture.completed_signs}/{capture.total_signs})"
            )
        return capture


class VlibrasWebRenderer(LibrasRenderer):
    """Renderiza glosas no player oficial moderno, preservando velocidade natural."""

    def __init__(self, runtime: VlibrasWebRuntime, *, avatar: str = "hosana") -> None:
        if avatar not in VLIBRAS_AVATARS:
            raise ValueError(f"avatar VLibras inválido: {avatar}")
        self.runtime = runtime
        self.avatar = avatar

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
        validate_ir(document)
        if width <= 0 or height <= 0 or fps <= 0:
            raise ValueError("dimensões e fps devem ser positivos")
        gloss = libras_ir_to_gloss_text(document)
        destination = Path(output_path) if output_path is not None else Path("avatar.vlibras.mp4")
        provenance_path = destination.with_suffix(destination.suffix + ".provenance.json")
        if (destination.exists() or provenance_path.exists()) and not overwrite:
            raise FileExistsError(
                f"arquivo de saída ou proveniência já existe: {destination}; use overwrite"
            )
        if not destination.parent.is_dir():
            raise FileNotFoundError(f"diretório de saída não encontrado: {destination.parent}")

        destination.unlink(missing_ok=True)
        provenance_path.unlink(missing_ok=True)
        with tempfile.TemporaryDirectory(prefix="sinal-vlibras-") as directory:
            capture = self.runtime.capture(
                gloss,
                Path(directory),
                avatar=self.avatar,
                width=width,
                height=height,
            )
            encoder, encoder_flags = detect_video_encoder()
            run_ffmpeg(
                [
                    "-y",
                    "-ss",
                    f"{capture.trim_offset_seconds:.3f}",
                    "-i",
                    str(capture.recording),
                    "-t",
                    f"{capture.animation_seconds + 0.35:.3f}",
                    "-an",
                    "-r",
                    str(fps),
                    "-c:v",
                    encoder,
                    *encoder_flags,
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    str(destination),
                ]
            )

        info = inspect_media(destination)
        if not info.videos or info.duration_seconds is None:
            destination.unlink(missing_ok=True)
            raise LibrasRenderError("captura VLibras não contém um stream de vídeo válido")
        source_duration = duration if duration is not None else _document_duration(document)
        drift = info.duration_seconds - source_duration
        synchronized = source_duration > 0 and abs(drift) <= 1.0
        provenance_path.write_text(
            json.dumps(
                {
                    "schema": "sinal.render-provenance",
                    "version": "1.0.0",
                    "renderer": "vlibras-web-player",
                    "runtime_version": self.runtime.version,
                    "avatar": self.avatar,
                    "source_translator": document.get("metadata", {}).get("translator"),
                    "source_review": document.get("review", {}).get("status"),
                    "completed_signs": capture.completed_signs,
                    "total_signs": capture.total_signs,
                    "source_duration_seconds": source_duration,
                    "rendered_duration_seconds": info.duration_seconds,
                    "timeline_drift_seconds": drift,
                    "timeline_synchronized": synchronized,
                    "speed_policy": "natural-no-retiming",
                    "generated_at": datetime.now(UTC).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        if duration is not None and not synchronized:
            raise LibrasRenderError(
                "a sinalização natural não cabe na timeline solicitada: "
                f"fonte={source_duration:.3f}s, Libras={info.duration_seconds:.3f}s. "
                f"O vídeo autônomo foi preservado em {destination}, mas a composição foi bloqueada"
            )
        return destination


def libras_ir_to_gloss_text(document: dict[str, Any]) -> str:
    """Extrai apenas glosas oficiais ou humanamente revisadas do LIBRAS-IR."""
    validate_ir(document)
    metadata = document.get("metadata", {})
    translator = str(metadata.get("translator", "")).lower()
    review_status = str(document.get("review", {}).get("status", ""))
    if not translator.startswith("vlibras") and review_status not in HUMAN_REVIEW_STATUSES:
        raise LibrasRenderError(
            "o player VLibras aceita apenas IR produzido pelo VLibras ou tradução "
            "humana revisada; pré-glosas baseadas em regras foram recusadas"
        )
    glosses: list[str] = []
    for index, utterance in enumerate(document.get("utterances", []), start=1):
        unresolved = [gap for gap in utterance.get("gaps", []) if gap.get("review_required")]
        gloss = utterance.get("translation", {}).get("gloss")
        if unresolved or not isinstance(gloss, str) or not gloss.strip():
            raise LibrasRenderError(f"enunciado {index} possui tradução pendente")
        glosses.append(gloss.strip())
    if not glosses:
        raise LibrasRenderError("LIBRAS-IR não contém enunciados para renderizar")
    return " ".join(glosses)


def read_render_provenance(video_path: str | Path) -> dict[str, Any] | None:
    path = Path(video_path).with_suffix(Path(video_path).suffix + ".provenance.json")
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LibrasRenderError(f"proveniência inválida do avatar: {path}") from error
    return value if isinstance(value, dict) else None


def _document_duration(document: dict[str, Any]) -> float:
    return max(
        (float(item.get("source_timing", {}).get("end", 0.0)) for item in document.get("utterances", [])),
        default=0.0,
    )
