"""Dicionário de poses anatômicas e configurações de mão para Libras 3D."""

from __future__ import annotations

from dataclasses import dataclass
from sinal.render.math3d import Vec3


@dataclass(frozen=True)
class HandPose:
    """Configuração de flexão dos 5 dedos (0.0 = aberto, 1.0 = fechado)."""
    thumb: float = 0.0
    index: float = 0.0
    middle: float = 0.0
    ring: float = 0.0
    pinky: float = 0.0


@dataclass(frozen=True)
class BodyPose3D:
    """Pose completa do avatar no espaço 3D (em coordenadas locais ao tórax)."""
    # Posições de juntas
    left_elbow: Vec3
    left_wrist: Vec3
    right_elbow: Vec3
    right_wrist: Vec3

    # Configuração dos dedos
    left_hand: HandPose = HandPose()
    right_hand: HandPose = HandPose()

    # Rotação da cabeça (em radianos: yaw, pitch, roll)
    head_rotation: Vec3 = Vec3(0.0, 0.0, 0.0)

    # Marcadores faciais (0.0 a 1.0)
    eyebrow_raise: float = 0.0
    mouth_open: float = 0.0

    def lerp(self, other: BodyPose3D, t: float) -> BodyPose3D:
        """Interpolação linear suave entre duas poses anatômicas."""
        # Suavização cúbica (Ease In Out)
        st = t * t * (3.0 - 2.0 * t)

        return BodyPose3D(
            left_elbow=self.left_elbow.lerp(other.left_elbow, st),
            left_wrist=self.left_wrist.lerp(other.left_wrist, st),
            right_elbow=self.right_elbow.lerp(other.right_elbow, st),
            right_wrist=self.right_wrist.lerp(other.right_wrist, st),
            left_hand=HandPose(
                thumb=self.left_hand.thumb + (other.left_hand.thumb - self.left_hand.thumb) * st,
                index=self.left_hand.index + (other.left_hand.index - self.left_hand.index) * st,
                middle=self.left_hand.middle + (other.left_hand.middle - self.left_hand.middle) * st,
                ring=self.left_hand.ring + (other.left_hand.ring - self.left_hand.ring) * st,
                pinky=self.left_hand.pinky + (other.left_hand.pinky - self.left_hand.pinky) * st,
            ),
            right_hand=HandPose(
                thumb=self.right_hand.thumb + (other.right_hand.thumb - self.right_hand.thumb) * st,
                index=self.right_hand.index + (other.right_hand.index - self.right_hand.index) * st,
                middle=self.right_hand.middle + (other.right_hand.middle - self.right_hand.middle) * st,
                ring=self.right_hand.ring + (other.right_hand.ring - self.right_hand.ring) * st,
                pinky=self.right_hand.pinky + (other.right_hand.pinky - self.right_hand.pinky) * st,
            ),
            head_rotation=self.head_rotation.lerp(other.head_rotation, st),
            eyebrow_raise=self.eyebrow_raise + (other.eyebrow_raise - self.eyebrow_raise) * st,
            mouth_open=self.mouth_open + (other.mouth_open - self.mouth_open) * st,
        )


# Pose de repouso neutro (braços relaxados ao lado do corpo)
POSE_REST = BodyPose3D(
    left_elbow=Vec3(-0.28, -0.05, 0.05),
    left_wrist=Vec3(-0.22, -0.26, 0.12),
    right_elbow=Vec3(0.28, -0.05, 0.05),
    right_wrist=Vec3(0.22, -0.26, 0.12),
    left_hand=HandPose(0.3, 0.3, 0.3, 0.3, 0.3),
    right_hand=HandPose(0.3, 0.3, 0.3, 0.3, 0.3),
)

# Poses específicas para sinais de Libras
LIBRAS_POSES: dict[str, BodyPose3D] = {
    "REST": POSE_REST,
    "OLA": BodyPose3D(
        left_elbow=Vec3(-0.28, -0.05, 0.05),
        left_wrist=Vec3(-0.22, -0.26, 0.12),
        right_elbow=Vec3(0.32, 0.18, 0.15),
        right_wrist=Vec3(0.26, 0.42, 0.28),
        right_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0),
        eyebrow_raise=0.6,
        mouth_open=0.2,
    ),
    "OI": BodyPose3D(
        left_elbow=Vec3(-0.28, -0.05, 0.05),
        left_wrist=Vec3(-0.22, -0.26, 0.12),
        right_elbow=Vec3(0.30, 0.15, 0.15),
        right_wrist=Vec3(0.22, 0.38, 0.25),
        right_hand=HandPose(0.0, 0.0, 1.0, 1.0, 0.0),  # Configuração em 'Y' / 'Oi'
        eyebrow_raise=0.5,
    ),
    "COMPLEXO": BodyPose3D(
        left_elbow=Vec3(-0.22, 0.02, 0.16),
        left_wrist=Vec3(-0.06, 0.12, 0.32),
        right_elbow=Vec3(0.22, 0.02, 0.16),
        right_wrist=Vec3(0.06, 0.12, 0.32),
        left_hand=HandPose(0.4, 0.6, 0.6, 0.6, 0.6),
        right_hand=HandPose(0.4, 0.6, 0.6, 0.6, 0.6),
        head_rotation=Vec3(0.05, -0.05, 0.0),
    ),
    "ANTIGO": BodyPose3D(
        left_elbow=Vec3(-0.28, -0.05, 0.05),
        left_wrist=Vec3(-0.22, -0.26, 0.12),
        right_elbow=Vec3(0.32, 0.18, 0.15),
        right_wrist=Vec3(0.24, 0.36, -0.05),  # Mão apontando para trás (passado)
        right_hand=HandPose(0.1, 0.1, 0.1, 0.1, 0.1),
        head_rotation=Vec3(-0.08, 0.0, 0.0),
    ),
    "CHEIO": BodyPose3D(
        left_elbow=Vec3(-0.20, -0.02, 0.15),
        left_wrist=Vec3(-0.05, 0.08, 0.28),
        right_elbow=Vec3(0.24, 0.08, 0.20),
        right_wrist=Vec3(0.02, 0.22, 0.32),
        left_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0),  # Palma aberta base
        right_hand=HandPose(0.6, 0.6, 0.6, 0.6, 0.6),  # Mão em concha cheia
    ),
    "VIDA": BodyPose3D(
        left_elbow=Vec3(-0.24, 0.05, 0.18),
        left_wrist=Vec3(-0.10, 0.20, 0.30),
        right_elbow=Vec3(0.24, 0.05, 0.18),
        right_wrist=Vec3(0.10, 0.20, 0.30),
        left_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0),  # Mãos em L/abertas no peito
        right_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0),
        eyebrow_raise=0.4,
    ),
    "PAMPA": BodyPose3D(
        left_elbow=Vec3(-0.32, 0.02, 0.15),
        left_wrist=Vec3(-0.28, 0.10, 0.26),
        right_elbow=Vec3(0.32, 0.02, 0.15),
        right_wrist=Vec3(0.28, 0.10, 0.26),
        left_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0),  # Planície aberta
        right_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0),
    ),
    "PARECE": BodyPose3D(
        left_elbow=Vec3(-0.28, -0.05, 0.05),
        left_wrist=Vec3(-0.22, -0.26, 0.12),
        right_elbow=Vec3(0.26, 0.14, 0.18),
        right_wrist=Vec3(0.16, 0.32, 0.28),  # Perto dos olhos/têmpora
        right_hand=HandPose(0.2, 0.0, 0.8, 0.8, 0.8),  # Indicador/visão
        eyebrow_raise=0.5,
    ),
    "VAZIO": BodyPose3D(
        left_elbow=Vec3(-0.20, -0.04, 0.12),
        left_wrist=Vec3(-0.08, -0.02, 0.22),
        right_elbow=Vec3(0.30, 0.02, 0.16),
        right_wrist=Vec3(0.22, 0.04, 0.28),
        right_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0),
        head_rotation=Vec3(0.06, 0.02, 0.0),
    ),
    "ESTAR": BodyPose3D(
        left_elbow=Vec3(-0.22, -0.02, 0.14),
        left_wrist=Vec3(-0.14, 0.04, 0.26),
        right_elbow=Vec3(0.22, -0.02, 0.14),
        right_wrist=Vec3(0.14, 0.04, 0.26),
        left_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0),
        right_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0),
    ),
    "SER": BodyPose3D(
        left_elbow=Vec3(-0.28, -0.05, 0.05),
        left_wrist=Vec3(-0.22, -0.26, 0.12),
        right_elbow=Vec3(0.22, 0.02, 0.16),
        right_wrist=Vec3(0.10, 0.15, 0.30),
        right_hand=HandPose(0.8, 0.0, 1.0, 1.0, 1.0),  # Indicador estendido
    ),
}


def get_sign_pose(sign_id: str, phase: float = 0.5) -> BodyPose3D:
    """Retorna a pose 3D correspondente a um sinal de Libras."""
    clean_id = sign_id.upper().strip()
    if clean_id in LIBRAS_POSES:
        base_pose = LIBRAS_POSES[clean_id]
        # Pequena dinâmica de oscilação do sinal ao longo da duração
        dyn = (phase - 0.5) * 0.04
        return BodyPose3D(
            left_elbow=base_pose.left_elbow + Vec3(0, dyn * 0.5, 0),
            left_wrist=base_pose.left_wrist + Vec3(0, dyn, 0),
            right_elbow=base_pose.right_elbow + Vec3(0, dyn * 0.5, 0),
            right_wrist=base_pose.right_wrist + Vec3(0, dyn, 0),
            left_hand=base_pose.left_hand,
            right_hand=base_pose.right_hand,
            head_rotation=base_pose.head_rotation,
            eyebrow_raise=base_pose.eyebrow_raise,
            mouth_open=base_pose.mouth_open,
        )

    # Para sinais não catalogados: mantém postura neutra no espaço de sinalização
    # sem inventar movimentos aleatórios arbitrários via hash.
    return BodyPose3D(
        left_elbow=Vec3(-0.24, -0.02, 0.12),
        left_wrist=Vec3(-0.12, 0.08, 0.24),
        right_elbow=Vec3(0.24, -0.02, 0.12),
        right_wrist=Vec3(0.12, 0.08, 0.24),
        left_hand=HandPose(0.2, 0.2, 0.2, 0.2, 0.2),
        right_hand=HandPose(0.2, 0.2, 0.2, 0.2, 0.2),
    )
