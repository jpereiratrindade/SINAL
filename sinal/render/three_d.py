"""Renderizador 3D anatômico de avatar de Libras com paralelismo multi-core e progress bar."""

from __future__ import annotations

import math
import os
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path
from typing import Any

from sinal.libras.ir import validate_ir
from sinal.media.ffmpeg import detect_video_encoder
from sinal.render.base import LibrasRenderError, LibrasRenderer
from sinal.render.math3d import Camera3D, Vec3
from sinal.render.poses import POSE_REST, BodyPose3D, get_sign_pose


class Color(tuple):
    @classmethod
    def rgb(cls, r: int, g: int, b: int) -> Color:
        return cls((max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))))


SKIN_BASE = Color.rgb(235, 195, 165)
SKIN_SHADOW = Color.rgb(180, 135, 110)
SHIRT_BASE = Color.rgb(28, 34, 52)
SHIRT_LIGHT = Color.rgb(45, 55, 82)
EYE_WHITE = Color.rgb(240, 245, 255)
PUPIL_COLOR = Color.rgb(30, 25, 20)
LIP_COLOR = Color.rgb(195, 120, 115)
HAIR_COLOR = Color.rgb(40, 30, 25)

DEFAULT_CAMERA = Camera3D(
    position=Vec3(0.0, 0.28, 2.1),
    target=Vec3(0.0, 0.22, 0.0),
    fov_deg=42.0,
)
LIGHT_DIR = Vec3(0.4, 0.8, 0.6).normalize()


def _escape_drawtext(text: str) -> str:
    """Escapa caracteres especiais para filtros drawtext do FFmpeg."""
    return (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace("%", "\\%")
        .replace("\n", " ")
    )


def _shade_color(base_color: Color, normal: Vec3) -> Color:
    diffuse = max(0.0, normal.dot(LIGHT_DIR))
    ambient = 0.45
    intensity = ambient + (1.0 - ambient) * diffuse
    return Color.rgb(
        round(base_color[0] * intensity),
        round(base_color[1] * intensity),
        round(base_color[2] * intensity),
    )


_SINA_MODEL_CACHE = None


def _get_sina_model():
    global _SINA_MODEL_CACHE
    if _SINA_MODEL_CACHE is None:
        from sinal.avatar.sina import SinaAvatarModel
        _SINA_MODEL_CACHE = SinaAvatarModel()
    return _SINA_MODEL_CACHE


def _draw_ellipsoid(buffer: bytearray, w: int, h: int, params: tuple) -> None:
    center, radii, base_color, highlight_color = params
    proj = DEFAULT_CAMERA.project(center, w, h)
    if proj is None:
        return

    sx, sy, depth = proj
    fov_factor = w / (depth * math.tan(DEFAULT_CAMERA.fov_rad / 2.0))
    prx = max(1, round(radii.x * fov_factor))
    pry = max(1, round(radii.y * fov_factor))

    min_x = max(0, round(sx - prx))
    max_x = min(w - 1, round(sx + prx))
    min_y = max(0, round(sy - pry))
    max_y = min(h - 1, round(sy + pry))

    rx_sq = prx * prx
    ry_sq = pry * pry

    for py in range(min_y, max_y + 1):
        dy = py - sy
        dy_term = (dy * dy) / ry_sq
        if dy_term > 1.0:
            continue
        row_idx = py * w * 3
        for px in range(min_x, max_x + 1):
            dx = px - sx
            dist_norm = (dx * dx) / rx_sq + dy_term
            if dist_norm <= 1.0:
                nz = math.sqrt(max(0.0, 1.0 - dist_norm))
                nx = dx / prx
                ny = -dy / pry
                normal = Vec3(nx / radii.x, ny / radii.y, nz / radii.z).normalize()
                shaded = _shade_color(base_color, normal)
                idx = row_idx + px * 3
                buffer[idx] = shaded[0]
                buffer[idx + 1] = shaded[1]
                buffer[idx + 2] = shaded[2]


def _draw_sphere(buffer: bytearray, w: int, h: int, params: tuple) -> None:
    center, radius, base_color, _ = params if len(params) == 4 else (*params, base_color)
    proj = DEFAULT_CAMERA.project(center, w, h)
    if proj is None:
        return

    sx, sy, depth = proj
    pixel_r = max(1, round(radius * w / (depth * math.tan(DEFAULT_CAMERA.fov_rad / 2.0))))

    min_x = max(0, round(sx - pixel_r))
    max_x = min(w - 1, round(sx + pixel_r))
    min_y = max(0, round(sy - pixel_r))
    max_y = min(h - 1, round(sy + pixel_r))

    r_sq = pixel_r * pixel_r
    for py in range(min_y, max_y + 1):
        dy = py - sy
        dy_sq = dy * dy
        row_idx = py * w * 3
        for px in range(min_x, max_x + 1):
            dx = px - sx
            dist_sq = dx * dx + dy_sq
            if dist_sq <= r_sq:
                nz = math.sqrt(max(0.0, 1.0 - dist_sq / r_sq))
                nx = dx / pixel_r
                ny = -dy / pixel_r
                normal = Vec3(nx, ny, nz).normalize()
                shaded = _shade_color(base_color, normal)
                idx = row_idx + px * 3
                buffer[idx] = shaded[0]
                buffer[idx + 1] = shaded[1]
                buffer[idx + 2] = shaded[2]


def _draw_capsule(buffer: bytearray, w: int, h: int, params: tuple) -> None:
    p1, p2, radius, base_color, _ = params if len(params) == 5 else (*params, base_color)
    dist = (p2 - p1).length()
    steps = max(16, min(64, round(dist / (radius * 0.15))))
    for i in range(steps + 1):
        t = i / steps
        p = p1.lerp(p2, t)
        _draw_sphere(buffer, w, h, (p, radius, base_color, base_color))


def _put_pixel(buffer: bytearray, w: int, h: int, x: int, y: int, r: int, g: int, b: int) -> None:
    if 0 <= x < w and 0 <= y < h:
        idx = (y * w + x) * 3
        buffer[idx] = r
        buffer[idx + 1] = g
        buffer[idx + 2] = b


def _render_frame_standalone(
    w: int,
    h: int,
    pose: BodyPose3D,
    active_sign: tuple[str, str, float] | None,
) -> bytes:
    buffer = bytearray(w * h * 3)

    for y in range(h):
        t_grad = y / h
        bg_r = round(16 + 12 * (1.0 - t_grad))
        bg_g = round(20 + 16 * (1.0 - t_grad))
        bg_b = round(32 + 24 * (1.0 - t_grad))
        row_offset = y * w * 3
        for x in range(w):
            idx = row_offset + x * 3
            buffer[idx] = bg_r
            buffer[idx + 1] = bg_g
            buffer[idx + 2] = bg_b

    draw_list = _get_sina_model().build_scene_primitives(pose)

    for _depth, shape_type, params in draw_list:
        if shape_type == "ellipsoid":
            _draw_ellipsoid(buffer, w, h, params)
        elif shape_type == "sphere":
            _draw_sphere(buffer, w, h, params)
        elif shape_type == "capsule":
            _draw_capsule(buffer, w, h, params)

    # UI Overlay
    border_thickness = 4
    for x in range(w):
        for y in range(border_thickness):
            _put_pixel(buffer, w, h, x, y, 65, 72, 104)
            _put_pixel(buffer, w, h, x, h - 1 - y, 65, 72, 104)
    for y in range(h):
        for x in range(border_thickness):
            _put_pixel(buffer, w, h, x, y, 65, 72, 104)
            _put_pixel(buffer, w, h, w - 1 - x, y, 65, 72, 104)

    header_h = 44
    for y in range(border_thickness, header_h):
        for x in range(border_thickness, w - border_thickness):
            _put_pixel(buffer, w, h, x, y, 22, 26, 40)

    footer_h = 130
    footer_y = h - footer_h - border_thickness
    for y in range(footer_y, h - border_thickness):
        for x in range(border_thickness, w - border_thickness):
            _put_pixel(buffer, w, h, x, y, 18, 22, 34)

    if active_sign is not None:
        _sign_id, _, progress = active_sign
        bar_w = round((w - 40) * progress)
        for x in range(20, 20 + bar_w):
            for y in range(footer_y + 4, footer_y + 8):
                _put_pixel(buffer, w, h, x, y, 115, 218, 202)

    return bytes(buffer)


from sinal.animation.motion import CoarticulationTimeline, SignTimelineItem, MotionLibrary

_GLOBAL_MOTION_LIB = MotionLibrary()


def _render_frame_task(task_args: tuple) -> tuple[int, bytes]:
    frame_idx, w, h, fps, timeline_raw = task_args
    current_time = frame_idx / fps

    items = [
        SignTimelineItem(start=s[0], end=s[1], sign_id=s[2], source_text=s[3])
        for s in timeline_raw
    ]
    solver = CoarticulationTimeline(items, _GLOBAL_MOTION_LIB)
    current_pose, active_sign = solver.get_pose_at(current_time)

    frame_bytes = _render_frame_standalone(w, h, current_pose, active_sign)
    return (frame_idx, frame_bytes)


class ThreeDLibrasRenderer(LibrasRenderer):
    """Renderizador 3D com esqueleto articulado, dedos individuais, iluminação e multi-core."""

    def __init__(self, *, default_width: int = 640, default_height: int = 1080) -> None:
        self.default_width = default_width
        self.default_height = default_height

    def _render_frame(self, w: int, h: int, pose: BodyPose3D, active_sign: tuple[str, str, float] | None) -> bytes:
        return _render_frame_standalone(w, h, pose, active_sign)

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
        workers: int | None = None,
    ) -> Path:
        validate_ir(document)

        w = width or self.default_width
        h = height or self.default_height

        if w <= 0 or h <= 0 or fps <= 0:
            raise ValueError("dimensões e fps devem ser positivos")

        max_end = 0.0
        utterances = document.get("utterances", [])
        for u in utterances:
            end = float(u.get("source_timing", {}).get("end", 0.0))
            if end > max_end:
                max_end = end

        total_duration = duration if duration is not None else max(max_end, 1.0)
        total_frames = max(1, round(total_duration * fps))

        destination = (
            Path(output_path)
            if output_path is not None
            else Path("avatar-3d.libras.mp4")
        )

        if destination.exists() and not overwrite:
            raise FileExistsError(
                f"arquivo de saída já existe: {destination}; use overwrite para substituir"
            )
        if not destination.parent.is_dir():
            raise FileNotFoundError(f"diretório de saída não encontrado: {destination.parent}")

        encoder_name, encoder_flags = detect_video_encoder()

        # Constrói os filtros de texto nítido (título, sinal ativo e legendas)
        footer_y = h - 130 - 4
        text_filters: list[str] = [
            f"drawtext=text='ACESSIBILIDADE LIBRAS':fontsize=22:fontcolor=0x7aa2f7:x=(w-text_w)/2:y=16"
        ]

        for u in utterances:
            source_text = _escape_drawtext(str(u.get("source", ""))[:45])
            u_start = float(u.get("source_timing", {}).get("start", 0.0))
            u_end = float(u.get("source_timing", {}).get("end", 0.0))
            u_between = f"between(t,{u_start:.3f},{u_end:.3f})"

            text_filters.append(
                f"drawtext=text='{source_text}':fontsize=18:fontcolor=0x9aa5ce:x=(w-text_w)/2:y={footer_y + 85}:enable='{u_between}'"
            )

            signs = u.get("signs", [])
            for sign in signs:
                sign_id = _escape_drawtext(str(sign.get("id", "")))
                s_start = float(sign.get("start", u_start))
                s_dur = float(sign.get("duration", 1.0))
                s_end = min(s_start + s_dur, u_end)
                s_between = f"between(t,{s_start:.3f},{s_end:.3f})"

                text_filters.append(
                    f"drawtext=text='SINAL\\: {sign_id}':fontsize=24:fontcolor=0x73daca:x=(w-text_w)/2:y={footer_y + 24}:enable='{s_between}'"
                )

        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".filter", encoding="utf-8", delete=False) as script_file:
            script_file.write(f"[0:v]{','.join(text_filters)}[outv]")
            script_path = Path(script_file.name)

        ffmpeg_cmd = [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if overwrite else "-n",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{w}x{h}",
            "-r",
            str(fps),
            "-i",
            "-",
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

        try:
            proc = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as error:
            if script_path.exists():
                script_path.unlink()
            raise LibrasRenderError(f"não foi possível iniciar FFmpeg: {error}") from error

        assert proc.stdin is not None

        timeline: list[tuple[float, float, str, str]] = []
        for u in utterances:
            src = str(u.get("source", ""))
            for sign in u.get("signs", []):
                s_start = float(sign.get("start", 0.0))
                s_dur = float(sign.get("duration", 1.0))
                s_id = str(sign.get("id", ""))
                timeline.append((s_start, s_start + s_dur, s_id, src))

        num_workers = workers or min(32, os.cpu_count() or 4)
        tasks = [(i, w, h, fps, timeline) for i in range(total_frames)]

        t_start = time.time()
        completed_count = 0

        try:
            # Processamento paralelo com todos os núcleos CPU
            with Pool(processes=num_workers) as pool:
                # Buffer para garantir que os frames entrem no FFmpeg em ordem exata
                frame_buffer: dict[int, bytes] = {}
                next_write_idx = 0

                for frame_idx, frame_data in pool.imap_unordered(_render_frame_task, tasks, chunksize=8):
                    frame_buffer[frame_idx] = frame_data
                    completed_count += 1

                    # Atualiza a barra de progresso no terminal
                    pct = (completed_count / total_frames) * 100
                    elapsed = time.time() - t_start
                    fps_rate = completed_count / elapsed if elapsed > 0 else 0
                    remaining = (total_frames - completed_count) / fps_rate if fps_rate > 0 else 0
                    bar_w = 28
                    filled = int(bar_w * completed_count // total_frames)
                    bar = "█" * filled + "░" * (bar_w - filled)

                    sys.stdout.write(
                        f"\r\033[K[SINAL] Renderizando 3D ({num_workers} threads): [{bar}] {pct:5.1f}% "
                        f"({completed_count}/{total_frames} qd - {fps_rate:.1f} fps - ETA: {int(remaining)}s)"
                    )
                    sys.stdout.flush()

                    # Despeja no FFmpeg todos os frames consecutivos disponíveis
                    while next_write_idx in frame_buffer:
                        proc.stdin.write(frame_buffer.pop(next_write_idx))
                        next_write_idx += 1

                sys.stdout.write("\n")
                sys.stdout.flush()

            proc.stdin.close()
            proc.wait()
            if proc.returncode != 0:
                stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
                raise LibrasRenderError(f"FFmpeg falhou na renderização 3D ({proc.returncode}): {stderr}")
        except Exception as error:
            proc.kill()
            raise LibrasRenderError(f"erro durante a renderização 3D: {error}") from error
        finally:
            if script_path.exists():
                try:
                    script_path.unlink()
                except OSError:
                    pass

        return destination
