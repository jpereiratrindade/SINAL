"""Renderizador sintético de avatar/janela de Libras via FFmpeg."""

from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Any

from sinal.libras.ir import validate_ir
from sinal.media.ffmpeg import detect_video_encoder, run_ffmpeg
from sinal.render.base import LibrasRenderError, LibrasRenderer


def _escape_drawtext(text: str) -> str:
    """Escapa caracteres especiais para filtros drawtext do FFmpeg."""
    return (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace("%", "\\%")
        .replace("\n", " ")
    )


class SyntheticPlaceholderRenderer(LibrasRenderer):
    """Gera um vídeo de acessibilidade em Libras sincronizado a partir do LIBRAS-IR.

    Renderiza uma janela com alto contraste, moldura ABNT, avatar representativo
    animado nas janelas de sinalização e legendas técnicas da glosa/sinal ativo.
    """

    def __init__(self, *, default_width: int = 640, default_height: int = 1080) -> None:
        self.default_width = default_width
        self.default_height = default_height

    def render(
        self,
        document: dict[str, Any],
        output_path: str | Path | None = None,
        *,
        duration: float | None = None,
        width: int | None = None,
        height: int | None = None,
        fps: int = 30,
        overwrite: bool = False,
    ) -> Path:
        validate_ir(document)

        w = width or self.default_width
        h = height or self.default_height

        if w <= 0 or h <= 0:
            raise ValueError("largura e altura devem ser positivas")
        if fps <= 0:
            raise ValueError("fps deve ser positivo")

        # Determina a duração total do vídeo
        max_end = 0.0
        for utterance in document.get("utterances", []):
            timing = utterance.get("source_timing", {})
            end = float(timing.get("end", 0.0))
            if end > max_end:
                max_end = end

        total_duration = duration if duration is not None else max(max_end, 1.0)
        if total_duration <= 0:
            raise ValueError("a duração do vídeo deve ser positiva")

        destination = (
            Path(output_path)
            if output_path is not None
            else Path("avatar.libras.mp4")
        )

        if destination.exists() and not overwrite:
            raise FileExistsError(
                f"arquivo de saída já existe: {destination}; use overwrite para substituir"
            )
        if not destination.parent.is_dir():
            raise FileNotFoundError(
                f"diretório de saída não encontrado: {destination.parent}"
            )

        # Monta a cadeia de filtros visuais
        filters: list[str] = []

        # 1. Moldura externa e cabeçalho ABNT
        filters.append(
            f"drawbox=x=12:y=12:w={w - 24}:h={h - 24}:color=0x414868@0.6:t=3"
        )
        filters.append(
            f"drawbox=x=16:y=16:w={w - 32}:h=56:color=0x24283b@0.9:t=fill"
        )
        filters.append(
            f"drawtext=text='ACESSIBILIDADE LIBRAS':fontsize=22:fontcolor=0x7aa2f7:"
            f"x=(w-text_w)/2:y=34"
        )

        # 2. Silhueta estilizada do avatar (base neutra de repouso)
        # Cabeça
        head_y = round(h * 0.22)
        head_r = round(w * 0.12)
        filters.append(
            f"drawbox=x={(w - head_r)//2}:y={head_y}:w={head_r}:h={head_r}:color=0xc0caf5@0.85:t=fill"
        )
        # Tronco
        torso_y = head_y + head_r + 14
        torso_w = round(w * 0.44)
        torso_h = round(h * 0.28)
        filters.append(
            f"drawbox=x={(w - torso_w)//2}:y={torso_y}:w={torso_w}:h={torso_h}:color=0x3b4261@0.9:t=fill"
        )

        # 3. Rodapé informativo
        footer_y = h - 160
        filters.append(
            f"drawbox=x=16:y={footer_y}:w={w - 32}:h=140:color=0x1f2335@0.95:t=fill"
        )

        # 4. Animação de mãos e sinais ativos para cada enunciado e sinal do LIBRAS-IR
        utterances = document.get("utterances", [])
        has_signs = False

        for utterance in utterances:
            source_text = _escape_drawtext(utterance.get("source", "")[:40])
            u_start = float(utterance["source_timing"]["start"])
            u_end = float(utterance["source_timing"]["end"])
            u_between = f"between(t,{u_start:.3f},{u_end:.3f})"

            # Legenda da fala de origem
            filters.append(
                f"drawtext=text='{source_text}':fontsize=18:fontcolor=0x9aa5ce:"
                f"x=(w-text_w)/2:y={footer_y + 92}:enable='{u_between}'"
            )

            signs = utterance.get("signs", [])
            gaps = utterance.get("gaps", [])

            if signs:
                has_signs = True
                for index, sign in enumerate(signs):
                    sign_id = _escape_drawtext(str(sign.get("id", "")))
                    s_start = float(sign.get("start", u_start))
                    s_dur = float(sign.get("duration", 1.0))
                    s_end = min(s_start + s_dur, u_end)
                    s_between = f"between(t,{s_start:.3f},{s_end:.3f})"

                    # Exibição do sinal ativo
                    filters.append(
                        f"drawtext=text='SINAL\\: {sign_id}':fontsize=24:fontcolor=0x73daca:"
                        f"x=(w-text_w)/2:y={footer_y + 24}:enable='{s_between}'"
                    )

                    # Animação da posição das mãos durante o sinal (gesto ativo)
                    offset_x = (index % 3 - 1) * 45
                    hand_left_x = (w - torso_w) // 2 - 20 + offset_x
                    hand_right_x = (w + torso_w) // 2 - 20 - offset_x
                    hand_y = torso_y + round(torso_h * 0.4) + ((index % 2) * 30 - 15)

                    filters.append(
                        f"drawbox=x={hand_left_x}:y={hand_y}:w=36:h=36:color=0x7aa2f7@0.95:t=fill:enable='{s_between}'"
                    )
                    filters.append(
                        f"drawbox=x={hand_right_x}:y={hand_y}:w=36:h=36:color=0x7aa2f7@0.95:t=fill:enable='{s_between}'"
                    )
            elif gaps:
                # Indicador de gap / tradução pendente
                filters.append(
                    f"drawtext=text='[TRADUÇÃO PENDENTE]':fontsize=20:fontcolor=0xe0af68:"
                    f"x=(w-text_w)/2:y={footer_y + 24}:enable='{u_between}'"
                )

        # Caso não haja sinais ativos em algum trecho, mantém mãos em postura de repouso
        hand_rest_y = torso_y + torso_h - 20
        filters.append(
            f"drawbox=x={(w - torso_w)//2 - 10}:y={hand_rest_y}:w=30:h=30:color=0x565f89@0.7:t=fill"
        )
        filters.append(
            f"drawbox=x={(w + torso_w)//2 - 20}:y={hand_rest_y}:w=30:h=30:color=0x565f89@0.7:t=fill"
        )

        filter_graph = ",".join(filters)
        encoder_name, encoder_flags = detect_video_encoder()

        # Usa arquivo temporário para o script do filtro complexo para suportar documentos grandes
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".filter", encoding="utf-8", delete=False
        ) as script_file:
            script_file.write(f"[0:v]{filter_graph}[outv]")
            script_path = Path(script_file.name)

        try:
            run_ffmpeg(
                [
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y" if overwrite else "-n",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=0x16161e:s={w}x{h}:r={fps}:d={total_duration:.3f}",
                    "-filter_complex_script",
                    str(script_path),
                    "-map",
                    "[outv]",
                    "-c:v",
                    encoder_name,
                    *encoder_flags,
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    str(destination),
                ]
            )
        except Exception as error:
            raise LibrasRenderError(f"falha ao renderizar avatar: {error}") from error
        finally:
            if script_path.exists():
                script_path.unlink()

        return destination
