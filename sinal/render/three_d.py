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


def _draw_sphere(buffer: bytearray, w: int, h: int, params: tuple) -> None:
    center, radius, base_color = params
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
    p1, p2, radius, base_color = params
    dist = (p2 - p1).length()
    steps = max(2, min(8, round(dist / (radius * 0.9))))
    for i in range(steps + 1):
        t = i / steps
        p = p1.lerp(p2, t)
        _draw_sphere(buffer, w, h, (p, radius, base_color))


def _add_sphere_3d(draw_list: list, center: Vec3, radius: float, color: Color) -> None:
    p_proj = DEFAULT_CAMERA.project(center, 1000, 1000)
    if p_proj is not None:
        draw_list.append((p_proj[2], "sphere", (center, radius, color)))


def _add_cylinder_3d(draw_list: list, p1: Vec3, p2: Vec3, radius: float, color: Color) -> None:
    mid = p1.lerp(p2, 0.5)
    p_proj = DEFAULT_CAMERA.project(mid, 1000, 1000)
    if p_proj is not None:
        draw_list.append((p_proj[2], "capsule", (p1, p2, radius, color)))


def _add_box_3d(draw_list: list, center: Vec3, size: Vec3, color: Color) -> None:
    p_top = center + Vec3(0, size.y * 0.35, 0)
    p_bot = center - Vec3(0, size.y * 0.35, 0)
    _add_cylinder_3d(draw_list, p_top, p_bot, size.x * 0.45, color)


def _add_head_3d(draw_list: list, center: Vec3, pose: BodyPose3D) -> None:
    rot = pose.head_rotation
    head_c = center + Vec3(rot.x * 0.05, rot.y * 0.05, 0.0)

    _add_sphere_3d(draw_list, head_c + Vec3(0, 0.03, -0.02), 0.125, HAIR_COLOR)
    _add_sphere_3d(draw_list, head_c, 0.118, SKIN_BASE)

    eye_y = head_c.y + 0.015
    eye_z = head_c.z + 0.105
    _add_sphere_3d(draw_list, Vec3(head_c.x - 0.042, eye_y, eye_z), 0.022, EYE_WHITE)
    _add_sphere_3d(draw_list, Vec3(head_c.x + 0.042, eye_y, eye_z), 0.022, EYE_WHITE)
    _add_sphere_3d(draw_list, Vec3(head_c.x - 0.042, eye_y, eye_z + 0.012), 0.011, PUPIL_COLOR)
    _add_sphere_3d(draw_list, Vec3(head_c.x + 0.042, eye_y, eye_z + 0.012), 0.011, PUPIL_COLOR)

    brow_y = eye_y + 0.032 + pose.eyebrow_raise * 0.015
    _add_cylinder_3d(draw_list, Vec3(head_c.x - 0.065, brow_y, eye_z + 0.005), Vec3(head_c.x - 0.020, brow_y + 0.005, eye_z + 0.005), 0.006, HAIR_COLOR)
    _add_cylinder_3d(draw_list, Vec3(head_c.x + 0.020, brow_y + 0.005, eye_z + 0.005), Vec3(head_c.x + 0.065, brow_y, eye_z + 0.005), 0.006, HAIR_COLOR)

    _add_sphere_3d(draw_list, Vec3(head_c.x, eye_y - 0.028, eye_z + 0.025), 0.016, SKIN_SHADOW)
    mouth_y = eye_y - 0.060
    _add_cylinder_3d(draw_list, Vec3(head_c.x - 0.028, mouth_y, eye_z + 0.01), Vec3(head_c.x + 0.028, mouth_y, eye_z + 0.01), 0.009, LIP_COLOR)


def _add_hand_3d(draw_list: list, wrist: Vec3, is_right: bool, hand_pose: Any) -> None:
    dir_mult = 1.0 if is_right else -1.0
    palm_center = wrist + Vec3(0.02 * dir_mult, 0.04, 0.04)
    _add_sphere_3d(draw_list, palm_center, 0.038, SKIN_BASE)

    finger_spreads = [
        (-0.025 * dir_mult, -0.01, hand_pose.thumb),
        (-0.015 * dir_mult, 0.032, hand_pose.index),
        (0.000, 0.036, hand_pose.middle),
        (0.015 * dir_mult, 0.032, hand_pose.ring),
        (0.025 * dir_mult, 0.024, hand_pose.pinky),
    ]

    for fx, fy, flex in finger_spreads:
        f_base = palm_center + Vec3(fx, fy, 0.01)
        curl_z = (1.0 - flex) * 0.035 - flex * 0.015
        curl_y = (1.0 - flex) * 0.030 - flex * 0.010
        f_tip = f_base + Vec3(fx * 0.4, curl_y, curl_z)
        _add_cylinder_3d(draw_list, f_base, f_tip, 0.011, SKIN_BASE)
        _add_sphere_3d(draw_list, f_tip, 0.010, SKIN_SHADOW)


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

    draw_list: list[tuple[float, str, Any]] = []

    torso_center = Vec3(0.0, 0.12, 0.0)
    neck_pos = Vec3(0.0, 0.32, 0.0)
    head_pos = Vec3(0.0, 0.44, 0.0)
    l_shoulder = Vec3(-0.20, 0.26, 0.0)
    r_shoulder = Vec3(0.20, 0.26, 0.0)

    _add_box_3d(draw_list, torso_center, Vec3(0.42, 0.36, 0.22), SHIRT_BASE)
    _add_cylinder_3d(draw_list, neck_pos + Vec3(0, -0.06, 0), neck_pos + Vec3(0, 0.04, 0), 0.065, SKIN_BASE)
    _add_head_3d(draw_list, head_pos, pose)

    _add_sphere_3d(draw_list, l_shoulder, 0.06, SHIRT_LIGHT)
    _add_cylinder_3d(draw_list, l_shoulder, pose.left_elbow, 0.052, SHIRT_BASE)
    _add_sphere_3d(draw_list, pose.left_elbow, 0.052, SHIRT_LIGHT)
    _add_cylinder_3d(draw_list, pose.left_elbow, pose.left_wrist, 0.045, SKIN_BASE)
    _add_sphere_3d(draw_list, pose.left_wrist, 0.042, SKIN_BASE)
    _add_hand_3d(draw_list, pose.left_wrist, is_right=False, hand_pose=pose.left_hand)

    _add_sphere_3d(draw_list, r_shoulder, 0.06, SHIRT_LIGHT)
    _add_cylinder_3d(draw_list, r_shoulder, pose.right_elbow, 0.052, SHIRT_BASE)
    _add_sphere_3d(draw_list, pose.right_elbow, 0.052, SHIRT_LIGHT)
    _add_cylinder_3d(draw_list, pose.right_elbow, pose.right_wrist, 0.045, SKIN_BASE)
    _add_sphere_3d(draw_list, pose.right_wrist, 0.042, SKIN_BASE)
    _add_hand_3d(draw_list, pose.right_wrist, is_right=True, hand_pose=pose.right_hand)

    draw_list.sort(key=lambda item: item[0], reverse=True)

    for _depth, shape_type, params in draw_list:
        if shape_type == "sphere":
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


def _render_frame_task(task_args: tuple) -> tuple[int, bytes]:
    frame_idx, w, h, fps, timeline = task_args
    current_time = frame_idx / fps

    active_sign: tuple[str, str, float] | None = None
    for s_start, s_end, sign_id, src_text in timeline:
        if s_start <= current_time <= s_end:
            duration_s = max(0.01, s_end - s_start)
            progress = (current_time - s_start) / duration_s
            active_sign = (sign_id, src_text, progress)
            break

    if active_sign is not None:
        sign_id, _src_text, progress = active_sign
        target_pose = get_sign_pose(sign_id, progress)
        blend = math.sin(progress * math.pi)
        current_pose = POSE_REST.lerp(target_pose, blend)
    else:
        idle_breath = math.sin(current_time * 2.0) * 0.005
        current_pose = BodyPose3D(
            left_elbow=POSE_REST.left_elbow + Vec3(0, idle_breath * 0.5, 0),
            left_wrist=POSE_REST.left_wrist + Vec3(0, idle_breath, 0),
            right_elbow=POSE_REST.right_elbow + Vec3(0, idle_breath * 0.5, 0),
            right_wrist=POSE_REST.right_wrist + Vec3(0, idle_breath, 0),
            left_hand=POSE_REST.left_hand,
            right_hand=POSE_REST.right_hand,
        )

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
