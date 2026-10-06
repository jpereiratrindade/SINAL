"""Definição anatômica e modelo 3D da SINA — Avatar Oficial do SINAL."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from sinal.render.math3d import Vec3, Camera3D
from sinal.render.poses import BodyPose3D, HandPose, POSE_REST


# Cores anatômicas e de vestimenta da SINA
SINA_SKIN = (226, 176, 146)
SINA_SKIN_SHADOW = (185, 136, 108)
SINA_BLOUSE = (28, 38, 58)
SINA_BLOUSE_HIGHLIGHT = (42, 56, 82)
SINA_HAIR = (26, 20, 18)
SINA_LIPS = (195, 118, 112)
SINA_EYE_SCLERA = (245, 245, 248)
SINA_EYE_IRIS = (52, 34, 24)
SINA_EYE_PUPIL = (12, 10, 10)
SINA_EYEBROW = (32, 24, 20)


@dataclass
class SinaAnatomy:
    """Proporções anatômicas naturais da SINA (em metros no espaço local)."""
    # Cabeça e Pescoço
    head_center: Vec3 = Vec3(0.0, 0.46, 0.0)
    head_radii: Vec3 = Vec3(0.082, 0.105, 0.092)  # Forma oval esbelta
    neck_base: Vec3 = Vec3(0.0, 0.28, 0.0)
    neck_top: Vec3 = Vec3(0.0, 0.38, 0.0)
    neck_radius: float = 0.038
    hair_bun_center: Vec3 = Vec3(0.0, 0.48, -0.09)
    hair_bun_radius: float = 0.052

    # Tronco (Blusa de intérprete elegante)
    torso_top: Vec3 = Vec3(0.0, 0.28, 0.0)
    torso_bottom: Vec3 = Vec3(0.0, -0.12, 0.0)
    chest_width: float = 0.155
    waist_width: float = 0.125
    torso_depth: float = 0.095

    # Ombros e Braços esguios
    shoulder_left: Vec3 = Vec3(-0.165, 0.26, 0.0)
    shoulder_right: Vec3 = Vec3(0.165, 0.26, 0.0)
    arm_radius_upper: float = 0.034
    arm_radius_elbow: float = 0.029
    arm_radius_forearm: float = 0.026
    wrist_radius: float = 0.020


class SinaAvatarModel:
    """Gerador de geometria e renderização anatômica da SINA."""

    def __init__(self, anatomy: SinaAnatomy | None = None) -> None:
        self.anatomy = anatomy or SinaAnatomy()

    def build_scene_primitives(self, pose: BodyPose3D) -> list[tuple[float, str, Any]]:
        """Gera a lista de elementos anatômicos 3D ordenados por profundidade."""
        draw_list: list[tuple[float, str, Any]] = []
        a = self.anatomy

        # 1. Tronco anatômico (cintura esbelta e contorno de blusa)
        self._add_slender_torso(draw_list, a)

        # 2. Pescoço gracioso e clavícula
        self._add_smooth_cylinder(draw_list, Vec3(0.0, 0.27, 0.0), Vec3(0.0, 0.39, 0.0), 0.033, SINA_SKIN, SINA_SKIN_SHADOW)

        # 3. Cabeça, Cabelo preso em coque e Face expressiva (MNM)
        self._add_sina_head(draw_list, a, pose)

        # 4. Braço Esquerdo (Ombro, Bíceps, Cotovelo, Antebraço esguio e Pulso)
        self._add_articulated_arm(
            draw_list,
            shoulder=a.shoulder_left,
            elbow=pose.left_elbow,
            wrist=pose.left_wrist,
            is_right=False,
            hand_pose=pose.left_hand,
        )

        # 5. Braço Direito
        self._add_articulated_arm(
            draw_list,
            shoulder=a.shoulder_right,
            elbow=pose.right_elbow,
            wrist=pose.right_wrist,
            is_right=True,
            hand_pose=pose.right_hand,
        )

        # Ordena de trás para frente (Z menor = mais ao fundo = desenhado primeiro)
        draw_list.sort(key=lambda item: item[0])
        return draw_list

    def _add_slender_torso(self, draw_list: list, a: SinaAnatomy) -> None:
        """Adiciona tronco com silhueta feminina natural e blusa de intérprete."""
        # Peito
        chest_pos = Vec3(0.0, 0.16, 0.0)
        draw_list.append((
            chest_pos.z,
            "ellipsoid",
            (chest_pos, Vec3(a.chest_width, 0.12, a.torso_depth), SINA_BLOUSE, SINA_BLOUSE_HIGHLIGHT),
        ))
        # Cintura/Abdômen
        waist_pos = Vec3(0.0, 0.02, 0.0)
        draw_list.append((
            waist_pos.z,
            "ellipsoid",
            (waist_pos, Vec3(a.waist_width, 0.11, a.torso_depth * 0.9), SINA_BLOUSE, SINA_BLOUSE_HIGHLIGHT),
        ))
        # Quadril superior
        hips_pos = Vec3(0.0, -0.09, 0.0)
        draw_list.append((
            hips_pos.z,
            "ellipsoid",
            (hips_pos, Vec3(a.chest_width * 0.95, 0.08, a.torso_depth * 0.95), SINA_BLOUSE, SINA_BLOUSE_HIGHLIGHT),
        ))

    def _add_sina_head(self, draw_list: list, a: SinaAnatomy, pose: BodyPose3D) -> None:
        """Adiciona cabeça oval, coque, olhos expressivos, sobrancelhas e lábios."""
        h_pos = a.head_center
        rot = pose.head_rotation

        # Coque elegante na nuca (hair bun)
        draw_list.append((
            a.hair_bun_center.z - 0.02,
            "sphere",
            (a.hair_bun_center, a.hair_bun_radius, SINA_HAIR, SINA_HAIR),
        ))

        # Cabelo superior/lateral
        hair_top = h_pos + Vec3(0.0, 0.03, -0.02)
        draw_list.append((
            hair_top.z - 0.01,
            "ellipsoid",
            (hair_top, Vec3(0.088, 0.095, 0.095), SINA_HAIR, SINA_HAIR),
        ))

        # Cabeça / Rosto oval
        draw_list.append((
            h_pos.z,
            "ellipsoid",
            (h_pos, a.head_radii, SINA_SKIN, SINA_SKIN_SHADOW),
        ))

        # Queixo delicado
        chin_pos = h_pos + Vec3(0.0, -0.085, 0.035)
        draw_list.append((
            chin_pos.z + 0.01,
            "sphere",
            (chin_pos, 0.028, SINA_SKIN, SINA_SKIN_SHADOW),
        ))

        # Nariz esbelto
        nose_pos = h_pos + Vec3(0.0, -0.01, 0.092)
        draw_list.append((
            nose_pos.z + 0.02,
            "sphere",
            (nose_pos, 0.012, SINA_SKIN, SINA_SKIN_SHADOW),
        ))

        # Olhos expressivos (Esquerdo e Direito)
        eye_y = h_pos.y + 0.018
        eye_z = h_pos.z + 0.082
        for side, eye_x in [("L", -0.034), ("R", 0.034)]:
            eye_center = Vec3(eye_x, eye_y, eye_z)
            # Esclera (Branco do olho)
            draw_list.append((
                eye_center.z + 0.02,
                "ellipsoid",
                (eye_center, Vec3(0.014, 0.009, 0.008), SINA_EYE_SCLERA, SINA_EYE_SCLERA),
            ))
            # Íris e Pupila
            iris_center = eye_center + Vec3(0.0, 0.0, 0.005)
            draw_list.append((
                iris_center.z + 0.03,
                "sphere",
                (iris_center, 0.0065, SINA_EYE_IRIS, SINA_EYE_PUPIL),
            ))

        # Sobrancelhas (MNM: erguimento expressivo)
        brow_y = eye_y + 0.022 + pose.eyebrow_raise * 0.012
        brow_z = eye_z + 0.006
        for side, brow_x in [("L", -0.035), ("R", 0.035)]:
            brow_pos = Vec3(brow_x, brow_y, brow_z)
            draw_list.append((
                brow_pos.z + 0.04,
                "ellipsoid",
                (brow_pos, Vec3(0.018, 0.004, 0.004), SINA_EYEBROW, SINA_EYEBROW),
            ))

        # Lábios e Boca expressiva
        mouth_y = h_pos.y - 0.052
        mouth_z = h_pos.z + 0.082
        mouth_pos = Vec3(0.0, mouth_y, mouth_z)
        lip_h = 0.006 + pose.mouth_open * 0.008
        draw_list.append((
            mouth_pos.z + 0.03,
            "ellipsoid",
            (mouth_pos, Vec3(0.020, lip_h, 0.006), SINA_LIPS, SINA_LIPS),
        ))

    def _add_articulated_arm(
        self,
        draw_list: list,
        shoulder: Vec3,
        elbow: Vec3,
        wrist: Vec3,
        is_right: bool,
        hand_pose: HandPose,
    ) -> None:
        """Gera braço com musculatura suave, manga escura e mãos detalhadas."""
        a = self.anatomy

        # Ombro com contorno suave de manga
        draw_list.append((
            shoulder.z,
            "sphere",
            (shoulder, a.arm_radius_upper * 1.05, SINA_BLOUSE, SINA_BLOUSE_HIGHLIGHT),
        ))

        # Braço superior (Manga da blusa)
        self._add_smooth_cylinder(draw_list, shoulder, elbow, a.arm_radius_upper, SINA_BLOUSE, SINA_BLOUSE_HIGHLIGHT)

        # Cotovelo
        draw_list.append((
            elbow.z,
            "sphere",
            (elbow, a.arm_radius_elbow, SINA_BLOUSE, SINA_BLOUSE_HIGHLIGHT),
        ))

        # Antebraço (Manga ou pele com formato afilado em direção ao punho)
        self._add_smooth_cylinder(draw_list, elbow, wrist, a.arm_radius_forearm, SINA_SKIN, SINA_SKIN_SHADOW)

        # Punho delicado
        draw_list.append((
            wrist.z,
            "sphere",
            (wrist, a.wrist_radius, SINA_SKIN, SINA_SKIN_SHADOW),
        ))

        # Mão detalhada com 5 dedos esguios e oposição real
        self._add_sina_hand(draw_list, wrist, is_right, hand_pose)

    def _add_sina_hand(
        self,
        draw_list: list,
        wrist: Vec3,
        is_right: bool,
        hand_pose: HandPose,
    ) -> None:
        """Adiciona mão feminina anatômica com 5 dedos individuais e falanges."""
        sign = 1.0 if is_right else -1.0
        palm_center = wrist + Vec3(sign * 0.018, 0.038, 0.022)

        # Palma da mão (fina e esbelta)
        draw_list.append((
            palm_center.z,
            "ellipsoid",
            (palm_center, Vec3(0.024, 0.030, 0.012), SINA_SKIN, SINA_SKIN_SHADOW),
        ))

        # Definição dos 5 dedos com comprimentos e ângulos anatômicos
        finger_specs = [
            ("thumb", hand_pose.thumb, Vec3(sign * 0.016, 0.010, 0.012), 0.028, 0.0070),
            ("index", hand_pose.index, Vec3(sign * 0.012, 0.032, 0.006), 0.038, 0.0060),
            ("middle", hand_pose.middle, Vec3(sign * 0.003, 0.035, 0.006), 0.042, 0.0062),
            ("ring", hand_pose.ring, Vec3(-sign * 0.006, 0.032, 0.005), 0.037, 0.0058),
            ("pinky", hand_pose.pinky, Vec3(-sign * 0.014, 0.026, 0.004), 0.029, 0.0050),
        ]

        for name, curl, base_offset, length, radius in finger_specs:
            base_pos = palm_center + base_offset
            if name == "thumb":
                # Polegar em oposição natural
                angle = (1.0 - curl) * 0.7 - 0.2
                tip_offset = Vec3(
                    sign * math.cos(angle) * length,
                    math.sin(angle) * length,
                    (1.0 - curl) * 0.018 + 0.004,
                )
            else:
                # 4 dedos com flexão realista das 3 falanges
                curl_angle = curl * (math.pi * 0.65)
                forward = math.cos(curl_angle) * length
                down = math.sin(curl_angle) * (length * 0.8)
                tip_offset = Vec3(0.0, forward, -down)

            tip_pos = base_pos + tip_offset

            # Falange proximal e distal contínua
            mid_pos = base_pos.lerp(tip_pos, 0.55)
            self._add_smooth_cylinder(draw_list, base_pos, mid_pos, radius, SINA_SKIN, SINA_SKIN_SHADOW)
            self._add_smooth_cylinder(draw_list, mid_pos, tip_pos, radius * 0.85, SINA_SKIN, SINA_SKIN_SHADOW)
            draw_list.append((
                tip_pos.z + 0.001,
                "sphere",
                (tip_pos, radius * 0.82, SINA_SKIN, SINA_SKIN_SHADOW),
            ))

    def _add_smooth_cylinder(
        self,
        draw_list: list,
        p0: Vec3,
        p1: Vec3,
        radius: float,
        color_base: tuple[int, int, int],
        color_highlight: tuple[int, int, int],
    ) -> None:
        """Adiciona cápsula/cilindro cônico contínuo."""
        mid = (p0 + p1) * 0.5
        draw_list.append((
            mid.z,
            "capsule",
            (p0, p1, radius, color_base, color_highlight),
        ))
