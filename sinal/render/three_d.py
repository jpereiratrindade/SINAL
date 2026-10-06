"""Renderizador 3D anatômico de avatar de Libras com articulação esquelética."""

from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Any

from sinal.libras.ir import validate_ir
from sinal.media.ffmpeg import detect_video_encoder
from sinal.render.base import LibrasRenderError, LibrasRenderer
from sinal.render.math3d import Camera3D, Vec3, rotate_x, rotate_y
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


class ThreeDLibrasRenderer(LibrasRenderer):
    """Renderizador 3D com esqueleto articulado, dedos individuais e iluminação tridimensional."""

    def __init__(self, *, default_width: int = 640, default_height: int = 1080) -> None:
        self.default_width = default_width
        self.default_height = default_height
        self.camera = Camera3D(
            position=Vec3(0.0, 0.28, 2.1),
            target=Vec3(0.0, 0.22, 0.0),
            fov_deg=42.0,
        )
        self.light_dir = Vec3(0.4, 0.8, 0.6).normalize()

    def _shade_color(self, base_color: Color, normal: Vec3) -> Color:
        diffuse = max(0.0, normal.dot(self.light_dir))
        ambient = 0.45
        intensity = ambient + (1.0 - ambient) * diffuse
        return Color.rgb(
            round(base_color[0] * intensity),
            round(base_color[1] * intensity),
            round(base_color[2] * intensity),
        )

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

        if w <= 0 or h <= 0 or fps <= 0:
            raise ValueError("dimensões e fps devem ser positivos")

        # Determina a duração total
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
            raise LibrasRenderError(f"não foi possível iniciar FFmpeg: {error}") from error

        assert proc.stdin is not None

        # Prepara a timeline de sinais e poses
        timeline: list[tuple[float, float, str, str]] = []
        for u in utterances:
            src = str(u.get("source", ""))
            for sign in u.get("signs", []):
                s_start = float(sign.get("start", 0.0))
                s_dur = float(sign.get("duration", 1.0))
                s_id = str(sign.get("id", ""))
                timeline.append((s_start, s_start + s_dur, s_id, src))

        # Renderiza cada quadro da animação 3D
        try:
            for frame_idx in range(total_frames):
                current_time = frame_idx / fps

                # Localiza o sinal ativo no tempo atual
                active_sign: tuple[str, str, float] | None = None
                for s_start, s_end, sign_id, src_text in timeline:
                    if s_start <= current_time <= s_end:
                        duration_s = max(0.01, s_end - s_start)
                        progress = (current_time - s_start) / duration_s
                        active_sign = (sign_id, src_text, progress)
                        break

                # Interpola a pose esquelética 3D
                if active_sign is not None:
                    sign_id, _src_text, progress = active_sign
                    target_pose = get_sign_pose(sign_id, progress)
                    # Transição suave de entrada e saída do sinal
                    blend = math.sin(progress * math.pi)
                    current_pose = POSE_REST.lerp(target_pose, blend)
                else:
                    # Movimento suave de respiração no repouso
                    idle_breath = math.sin(current_time * 2.0) * 0.005
                    current_pose = BodyPose3D(
                        left_elbow=POSE_REST.left_elbow + Vec3(0, idle_breath * 0.5, 0),
                        left_wrist=POSE_REST.left_wrist + Vec3(0, idle_breath, 0),
                        right_elbow=POSE_REST.right_elbow + Vec3(0, idle_breath * 0.5, 0),
                        right_wrist=POSE_REST.right_wrist + Vec3(0, idle_breath, 0),
                        left_hand=POSE_REST.left_hand,
                        right_hand=POSE_REST.right_hand,
                    )

                # Renderiza o buffer de pixels RGB24
                frame_bytes = self._render_frame(w, h, current_pose, active_sign)
                proc.stdin.write(frame_bytes)

            proc.stdin.close()
            proc.wait()
            if proc.returncode != 0:
                stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
                raise LibrasRenderError(f"FFmpeg falhou na renderização 3D ({proc.returncode}): {stderr}")
        except Exception as error:
            proc.kill()
            raise LibrasRenderError(f"erro durante a renderização 3D: {error}") from error

        return destination

    def _render_frame(
        self,
        w: int,
        h: int,
        pose: BodyPose3D,
        active_sign: tuple[str, str, float] | None,
    ) -> bytes:
        """Gera os pixels 3D da cena (avatar anatômico, articulações, mãos e interface)."""
        buffer = bytearray(w * h * 3)

        # 1. Fundo moderno com gradiente sutil de estúdio
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

        # Lista de primitivos 3D para ordenar por profundidade (Z-sort)
        draw_list: list[tuple[float, str, Any]] = []

        # Posições de referência do tórax e cabeça
        torso_center = Vec3(0.0, 0.12, 0.0)
        neck_pos = Vec3(0.0, 0.32, 0.0)
        head_pos = Vec3(0.0, 0.44, 0.0)
        l_shoulder = Vec3(-0.20, 0.26, 0.0)
        r_shoulder = Vec3(0.20, 0.26, 0.0)

        # 1. Tronco / Camisa do Intérprete (3D Box/Cylinder)
        self._add_box_3d(draw_list, torso_center, Vec3(0.42, 0.36, 0.22), SHIRT_BASE)
        # 2. Pescoço (3D Cylinder)
        self._add_cylinder_3d(draw_list, neck_pos + Vec3(0, -0.06, 0), neck_pos + Vec3(0, 0.04, 0), 0.065, SKIN_BASE)
        # 3. Cabeça (3D Ellipsoid com rosto)
        self._add_head_3d(draw_list, head_pos, pose)
        # 4. Ombros e Braços
        # Braço Esquerdo
        self._add_sphere_3d(draw_list, l_shoulder, 0.06, SHIRT_LIGHT)
        self._add_cylinder_3d(draw_list, l_shoulder, pose.left_elbow, 0.052, SHIRT_BASE)
        self._add_sphere_3d(draw_list, pose.left_elbow, 0.052, SHIRT_LIGHT)
        self._add_cylinder_3d(draw_list, pose.left_elbow, pose.left_wrist, 0.045, SKIN_BASE)
        self._add_sphere_3d(draw_list, pose.left_wrist, 0.042, SKIN_BASE)
        self._add_hand_3d(draw_list, pose.left_wrist, is_right=False, hand_pose=pose.left_hand)

        # Braço Direito
        self._add_sphere_3d(draw_list, r_shoulder, 0.06, SHIRT_LIGHT)
        self._add_cylinder_3d(draw_list, r_shoulder, pose.right_elbow, 0.052, SHIRT_BASE)
        self._add_sphere_3d(draw_list, pose.right_elbow, 0.052, SHIRT_LIGHT)
        self._add_cylinder_3d(draw_list, pose.right_elbow, pose.right_wrist, 0.045, SKIN_BASE)
        self._add_sphere_3d(draw_list, pose.right_wrist, 0.042, SKIN_BASE)
        self._add_hand_3d(draw_list, pose.right_wrist, is_right=True, hand_pose=pose.right_hand)

        # Ordena primitivos de trás para frente (Painter's Algorithm no espaço da câmera)
        draw_list.sort(key=lambda item: item[0], reverse=True)

        # Rasteriza primitivos 3D na tela
        for _depth, shape_type, params in draw_list:
            if shape_type == "sphere":
                self._draw_sphere(buffer, w, h, params)
            elif shape_type == "capsule":
                self._draw_capsule(buffer, w, h, params)
            elif shape_type == "poly":
                self._draw_poly(buffer, w, h, params)

        # Interface gráfica de Acessibilidade sobreposta
        self._draw_ui_overlay(buffer, w, h, active_sign)

        return bytes(buffer)

    def _add_sphere_3d(self, draw_list: list, center: Vec3, radius: float, color: Color) -> None:
        p_proj = self.camera.project(center, 1000, 1000)
        if p_proj is not None:
            depth = p_proj[2]
            draw_list.append((depth, "sphere", (center, radius, color)))

    def _add_cylinder_3d(self, draw_list: list, p1: Vec3, p2: Vec3, radius: float, color: Color) -> None:
        mid = p1.lerp(p2, 0.5)
        p_proj = self.camera.project(mid, 1000, 1000)
        if p_proj is not None:
            depth = p_proj[2]
            draw_list.append((depth, "capsule", (p1, p2, radius, color)))

    def _add_box_3d(self, draw_list: list, center: Vec3, size: Vec3, color: Color) -> None:
        # Aproxima o tronco como uma cápsula estilizada volumétrica
        p_top = center + Vec3(0, size.y * 0.35, 0)
        p_bot = center - Vec3(0, size.y * 0.35, 0)
        self._add_cylinder_3d(draw_list, p_top, p_bot, size.x * 0.45, color)

    def _add_head_3d(self, draw_list: list, center: Vec3, pose: BodyPose3D) -> None:
        # Rotação da cabeça
        rot = pose.head_rotation
        head_c = center + Vec3(rot.x * 0.05, rot.y * 0.05, 0.0)

        # Cabelo (topo/trás)
        self._add_sphere_3d(draw_list, head_c + Vec3(0, 0.03, -0.02), 0.125, HAIR_COLOR)
        # Rosto (esfera base)
        self._add_sphere_3d(draw_list, head_c, 0.118, SKIN_BASE)

        # Olhos, sobrancelhas e boca
        eye_y = head_c.y + 0.015
        eye_z = head_c.z + 0.105
        # Olho esquerdo e direito
        self._add_sphere_3d(draw_list, Vec3(head_c.x - 0.042, eye_y, eye_z), 0.022, EYE_WHITE)
        self._add_sphere_3d(draw_list, Vec3(head_c.x + 0.042, eye_y, eye_z), 0.022, EYE_WHITE)
        # Pupilas
        self._add_sphere_3d(draw_list, Vec3(head_c.x - 0.042, eye_y, eye_z + 0.012), 0.011, PUPIL_COLOR)
        self._add_sphere_3d(draw_list, Vec3(head_c.x + 0.042, eye_y, eye_z + 0.012), 0.011, PUPIL_COLOR)

        # Sobrancelhas (expressivas para Libras)
        brow_y = eye_y + 0.032 + pose.eyebrow_raise * 0.015
        self._add_cylinder_3d(draw_list, Vec3(head_c.x - 0.065, brow_y, eye_z + 0.005), Vec3(head_c.x - 0.020, brow_y + 0.005, eye_z + 0.005), 0.006, HAIR_COLOR)
        self._add_cylinder_3d(draw_list, Vec3(head_c.x + 0.020, brow_y + 0.005, eye_z + 0.005), Vec3(head_c.x + 0.065, brow_y, eye_z + 0.005), 0.006, HAIR_COLOR)

        # Nariz
        self._add_sphere_3d(draw_list, Vec3(head_c.x, eye_y - 0.028, eye_z + 0.025), 0.016, SKIN_SHADOW)

        # Boca
        mouth_y = eye_y - 0.060
        self._add_cylinder_3d(draw_list, Vec3(head_c.x - 0.028, mouth_y, eye_z + 0.01), Vec3(head_c.x + 0.028, mouth_y, eye_z + 0.01), 0.009, LIP_COLOR)

    def _add_hand_3d(self, draw_list: list, wrist: Vec3, is_right: bool, hand_pose: Any) -> None:
        """Gera a palma e os 5 dedos articulados em 3D."""
        dir_mult = 1.0 if is_right else -1.0
        palm_center = wrist + Vec3(0.02 * dir_mult, 0.04, 0.04)

        # Palma da mão
        self._add_sphere_3d(draw_list, palm_center, 0.038, SKIN_BASE)

        # Base dos 5 dedos (Polegar, Indicador, Médio, Anelar, Mínimo)
        finger_spreads = [
            (-0.025 * dir_mult, -0.01, hand_pose.thumb),    # Polegar
            (-0.015 * dir_mult, 0.032, hand_pose.index),    # Indicador
            (0.000, 0.036, hand_pose.middle),               # Médio
            (0.015 * dir_mult, 0.032, hand_pose.ring),      # Anelar
            (0.025 * dir_mult, 0.024, hand_pose.pinky),     # Mínimo
        ]

        for fx, fy, flex in finger_spreads:
            f_base = palm_center + Vec3(fx, fy, 0.01)
            # Dobra do dedo (cinemática de flexão)
            curl_z = (1.0 - flex) * 0.035 - flex * 0.015
            curl_y = (1.0 - flex) * 0.030 - flex * 0.010
            f_tip = f_base + Vec3(fx * 0.4, curl_y, curl_z)

            # Falange proximal e distal
            self._add_cylinder_3d(draw_list, f_base, f_tip, 0.011, SKIN_BASE)
            self._add_sphere_3d(draw_list, f_tip, 0.010, SKIN_SHADOW)

    def _draw_sphere(self, buffer: bytearray, w: int, h: int, params: tuple) -> None:
        center, radius, base_color = params
        proj = self.camera.project(center, w, h)
        if proj is None:
            return

        sx, sy, depth = proj
        # Raio em pixels projetado
        pixel_r = max(1, round(radius * w / (depth * math.tan(self.camera.fov_rad / 2.0))))

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
                    # Cálculo de normal esférica para iluminação Phong 3D
                    nz = math.sqrt(max(0.0, 1.0 - dist_sq / r_sq))
                    nx = dx / pixel_r
                    ny = -dy / pixel_r
                    normal = Vec3(nx, ny, nz).normalize()

                    shaded = self._shade_color(base_color, normal)
                    idx = row_idx + px * 3
                    buffer[idx] = shaded[0]
                    buffer[idx + 1] = shaded[1]
                    buffer[idx + 2] = shaded[2]

    def _draw_capsule(self, buffer: bytearray, w: int, h: int, params: tuple) -> None:
        p1, p2, radius, base_color = params
        dist = (p2 - p1).length()
        steps = max(2, min(8, round(dist / (radius * 0.9))))
        for i in range(steps + 1):
            t = i / steps
            p = p1.lerp(p2, t)
            self._draw_sphere(buffer, w, h, (p, radius, base_color))


    def _draw_poly(self, buffer: bytearray, w: int, h: int, params: tuple) -> None:
        pass

    def _draw_ui_overlay(
        self,
        buffer: bytearray,
        w: int,
        h: int,
        active_sign: tuple[str, str, float] | None,
    ) -> None:
        """Desenha a moldura de estúdio e badges de sinalização."""
        # Moldura externa em tom azul elétrico suave
        border_thickness = 4
        for x in range(w):
            for y in range(border_thickness):
                self._put_pixel(buffer, w, h, x, y, 65, 72, 104)
                self._put_pixel(buffer, w, h, x, h - 1 - y, 65, 72, 104)
        for y in range(h):
            for x in range(border_thickness):
                self._put_pixel(buffer, w, h, x, y, 65, 72, 104)
                self._put_pixel(buffer, w, h, w - 1 - x, y, 65, 72, 104)

        # Faixa superior de cabeçalho
        header_h = 44
        for y in range(border_thickness, header_h):
            for x in range(border_thickness, w - border_thickness):
                self._put_pixel(buffer, w, h, x, y, 22, 26, 40)

        # Painel inferior de Glosa e Legenda
        footer_h = 130
        footer_y = h - footer_h - border_thickness
        for y in range(footer_y, h - border_thickness):
            for x in range(border_thickness, w - border_thickness):
                self._put_pixel(buffer, w, h, x, y, 18, 22, 34)

        # Indicador de sinal ativo (pulso colorido ciano/esmeralda no rodapé)
        if active_sign is not None:
            sign_id, _, progress = active_sign
            bar_w = round((w - 40) * progress)
            for x in range(20, 20 + bar_w):
                for y in range(footer_y + 4, footer_y + 8):
                    self._put_pixel(buffer, w, h, x, y, 115, 218, 202)

    def _put_pixel(self, buffer: bytearray, w: int, h: int, x: int, y: int, r: int, g: int, b: int) -> None:
        if 0 <= x < w and 0 <= y < h:
            idx = (y * w + x) * 3
            buffer[idx] = r
            buffer[idx + 1] = g
            buffer[idx + 2] = b
