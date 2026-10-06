"""Arquitetura de movimento temporal (SignMotion), keyframes e coarticulação de Libras."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Sequence

from sinal.render.math3d import Vec3
from sinal.render.poses import BodyPose3D, HandPose, POSE_REST


@dataclass(frozen=True)
class Keyframe:
    """Um ponto de controle temporal dentro de um sinal."""
    time: float  # Fração relativa no intervalo do sinal [0.0, 1.0]
    pose: BodyPose3D
    ease: str = "cubic"  # "linear", "cubic", "hold"


@dataclass
class SignMotion:
    """Representação articulatória temporal completa de um sinal em Libras."""
    id: str
    description: str
    keyframes: list[Keyframe]
    is_two_handed: bool = False
    dominant_hand: str = "right"  # "right", "left", "both"

    def sample(self, progress: float) -> BodyPose3D:
        """Amostra a pose interpolada para uma posição temporal [0.0, 1.0]."""
        if not self.keyframes:
            return POSE_REST

        progress = max(0.0, min(1.0, progress))

        # Se antes do primeiro ou depois do último keyframe
        if progress <= self.keyframes[0].time:
            return self.keyframes[0].pose
        if progress >= self.keyframes[-1].time:
            return self.keyframes[-1].pose

        # Encontra o segmento [k0, k1]
        for i in range(len(self.keyframes) - 1):
            k0 = self.keyframes[i]
            k1 = self.keyframes[i + 1]
            if k0.time <= progress <= k1.time:
                seg_duration = max(1e-5, k1.time - k0.time)
                t = (progress - k0.time) / seg_duration
                return k0.pose.lerp(k1.pose, t)

        return self.keyframes[-1].pose


# Pose neutra no espaço de sinalização (signing space) para sinais sem motion cadastrado
# Braços confortavelmente posicionados à frente do tronco, sem inventar movimentos aleatórios.
POSE_NEUTRAL_SIGNING_SPACE = BodyPose3D(
    left_elbow=Vec3(-0.24, -0.02, 0.12),
    left_wrist=Vec3(-0.12, 0.08, 0.24),
    right_elbow=Vec3(0.24, -0.02, 0.12),
    right_wrist=Vec3(0.12, 0.08, 0.24),
    left_hand=HandPose(0.2, 0.2, 0.2, 0.2, 0.2),
    right_hand=HandPose(0.2, 0.2, 0.2, 0.2, 0.2),
    head_rotation=Vec3(0.0, 0.0, 0.0),
    eyebrow_raise=0.0,
)


class MotionLibrary:
    """Catálogo estruturado de clipes de movimento (SignMotion) de Libras."""

    def __init__(self) -> None:
        self._motions: dict[str, SignMotion] = {}
        self._register_canonical_motions()

    def register(self, motion: SignMotion) -> None:
        self._motions[motion.id.upper()] = motion

    def get(self, sign_id: str) -> SignMotion | None:
        return self._motions.get(sign_id.upper().strip())

    def has_motion(self, sign_id: str) -> bool:
        return sign_id.upper().strip() in self._motions

    def sample_or_neutral(self, sign_id: str, progress: float) -> tuple[BodyPose3D, bool]:
        """Amostra o movimento se catalogado; caso contrário, retorna espaço neutro honesto."""
        clean = sign_id.upper().strip()
        motion = self.get(clean)
        if motion is not None:
            return (motion.sample(progress), True)
        return (POSE_NEUTRAL_SIGNING_SPACE, False)

    def _register_canonical_motions(self) -> None:
        """Registra sinais canônicos com trajetórias temporais multi-keyframe."""

        # 1. OLÁ / TCHAU (Preparação -> Levantamento -> Aceno duplo -> Posição estável)
        self.register(
            SignMotion(
                id="OLA",
                description="Aceno com a mão aberta ao lado da têmpora",
                dominant_hand="right",
                keyframes=[
                    Keyframe(0.0, BodyPose3D(
                        left_elbow=Vec3(-0.28, -0.05, 0.05), left_wrist=Vec3(-0.22, -0.26, 0.12),
                        right_elbow=Vec3(0.26, 0.08, 0.12), right_wrist=Vec3(0.20, 0.22, 0.22),
                        right_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0), eyebrow_raise=0.3,
                    )),
                    Keyframe(0.3, BodyPose3D(
                        left_elbow=Vec3(-0.28, -0.05, 0.05), left_wrist=Vec3(-0.22, -0.26, 0.12),
                        right_elbow=Vec3(0.32, 0.20, 0.16), right_wrist=Vec3(0.28, 0.44, 0.26),
                        right_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0), eyebrow_raise=0.6,
                    )),
                    Keyframe(0.65, BodyPose3D(
                        left_elbow=Vec3(-0.28, -0.05, 0.05), left_wrist=Vec3(-0.22, -0.26, 0.12),
                        right_elbow=Vec3(0.30, 0.18, 0.16), right_wrist=Vec3(0.22, 0.42, 0.26),
                        right_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0), eyebrow_raise=0.5,
                    )),
                    Keyframe(1.0, BodyPose3D(
                        left_elbow=Vec3(-0.28, -0.05, 0.05), left_wrist=Vec3(-0.22, -0.26, 0.12),
                        right_elbow=Vec3(0.32, 0.20, 0.16), right_wrist=Vec3(0.26, 0.40, 0.24),
                        right_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0), eyebrow_raise=0.3,
                    )),
                ],
            )
        )

        # 2. OI (Configuração manual 'Y' com rotação do punho)
        self.register(
            SignMotion(
                id="OI",
                description="Mão em Y com movimento circular próximo ao rosto",
                dominant_hand="right",
                keyframes=[
                    Keyframe(0.0, BodyPose3D(
                        left_elbow=Vec3(-0.28, -0.05, 0.05), left_wrist=Vec3(-0.22, -0.26, 0.12),
                        right_elbow=Vec3(0.26, 0.10, 0.14), right_wrist=Vec3(0.18, 0.28, 0.22),
                        right_hand=HandPose(0.0, 1.0, 1.0, 1.0, 0.0), eyebrow_raise=0.4,
                    )),
                    Keyframe(0.5, BodyPose3D(
                        left_elbow=Vec3(-0.28, -0.05, 0.05), left_wrist=Vec3(-0.22, -0.26, 0.12),
                        right_elbow=Vec3(0.30, 0.16, 0.16), right_wrist=Vec3(0.24, 0.40, 0.26),
                        right_hand=HandPose(0.0, 1.0, 1.0, 1.0, 0.0), eyebrow_raise=0.5,
                    )),
                    Keyframe(1.0, BodyPose3D(
                        left_elbow=Vec3(-0.28, -0.05, 0.05), left_wrist=Vec3(-0.22, -0.26, 0.12),
                        right_elbow=Vec3(0.28, 0.14, 0.15), right_wrist=Vec3(0.20, 0.36, 0.24),
                        right_hand=HandPose(0.0, 1.0, 1.0, 1.0, 0.0), eyebrow_raise=0.2,
                    )),
                ],
            )
        )

        # 3. COMPLEXO (Movimento entrelaçado e convergente das duas mãos)
        self.register(
            SignMotion(
                id="COMPLEXO",
                description="Mãos entrelaçadas em movimento ondulatório",
                is_two_handed=True,
                keyframes=[
                    Keyframe(0.0, BodyPose3D(
                        left_elbow=Vec3(-0.22, -0.02, 0.14), left_wrist=Vec3(-0.10, 0.06, 0.28),
                        right_elbow=Vec3(0.22, -0.02, 0.14), right_wrist=Vec3(0.10, 0.06, 0.28),
                        left_hand=HandPose(0.3, 0.4, 0.4, 0.4, 0.4), right_hand=HandPose(0.3, 0.4, 0.4, 0.4, 0.4),
                    )),
                    Keyframe(0.5, BodyPose3D(
                        left_elbow=Vec3(-0.20, 0.04, 0.18), left_wrist=Vec3(-0.04, 0.16, 0.32),
                        right_elbow=Vec3(0.20, 0.04, 0.18), right_wrist=Vec3(0.04, 0.16, 0.32),
                        left_hand=HandPose(0.5, 0.7, 0.7, 0.7, 0.7), right_hand=HandPose(0.5, 0.7, 0.7, 0.7, 0.7),
                        head_rotation=Vec3(0.04, -0.04, 0.0),
                    )),
                    Keyframe(1.0, BodyPose3D(
                        left_elbow=Vec3(-0.22, 0.00, 0.16), left_wrist=Vec3(-0.08, 0.10, 0.30),
                        right_elbow=Vec3(0.22, 0.00, 0.16), right_wrist=Vec3(0.08, 0.10, 0.30),
                        left_hand=HandPose(0.3, 0.5, 0.5, 0.5, 0.5), right_hand=HandPose(0.3, 0.5, 0.5, 0.5, 0.5),
                    )),
                ],
            )
        )

        # 4. VIDA / VIVER (Movimento ascendente no peito com palmas abertas)
        self.register(
            SignMotion(
                id="VIDA",
                description="Mãos em L no peito subindo em direção aos ombros",
                is_two_handed=True,
                keyframes=[
                    Keyframe(0.0, BodyPose3D(
                        left_elbow=Vec3(-0.22, -0.04, 0.15), left_wrist=Vec3(-0.12, 0.04, 0.26),
                        right_elbow=Vec3(0.22, -0.04, 0.15), right_wrist=Vec3(0.12, 0.04, 0.26),
                        left_hand=HandPose(0.0, 0.0, 1.0, 1.0, 1.0), right_hand=HandPose(0.0, 0.0, 1.0, 1.0, 1.0),
                        eyebrow_raise=0.2,
                    )),
                    Keyframe(1.0, BodyPose3D(
                        left_elbow=Vec3(-0.24, 0.08, 0.18), left_wrist=Vec3(-0.10, 0.24, 0.28),
                        right_elbow=Vec3(0.24, 0.08, 0.18), right_wrist=Vec3(0.10, 0.24, 0.28),
                        left_hand=HandPose(0.0, 0.0, 1.0, 1.0, 1.0), right_hand=HandPose(0.0, 0.0, 1.0, 1.0, 1.0),
                        eyebrow_raise=0.4,
                    )),
                ],
            )
        )

        # 5. PAMPA (Expansão horizontal das palmas indicando planície aberta)
        self.register(
            SignMotion(
                id="PAMPA",
                description="Palmas abertas voltadas para baixo expandindo lateralmente",
                is_two_handed=True,
                keyframes=[
                    Keyframe(0.0, BodyPose3D(
                        left_elbow=Vec3(-0.20, 0.00, 0.15), left_wrist=Vec3(-0.08, 0.08, 0.26),
                        right_elbow=Vec3(0.20, 0.00, 0.15), right_wrist=Vec3(0.08, 0.08, 0.26),
                        left_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0), right_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0),
                    )),
                    Keyframe(1.0, BodyPose3D(
                        left_elbow=Vec3(-0.34, 0.02, 0.16), left_wrist=Vec3(-0.30, 0.10, 0.28),
                        right_elbow=Vec3(0.34, 0.02, 0.16), right_wrist=Vec3(0.30, 0.10, 0.28),
                        left_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0), right_hand=HandPose(0.0, 0.0, 0.0, 0.0, 0.0),
                    )),
                ],
            )
        )

        # 6. GRANDE (Arco expansivo amplo para os lados)
        self.register(
            SignMotion(
                id="GRANDE",
                description="Mãos em C abrindo em arco largo",
                is_two_handed=True,
                keyframes=[
                    Keyframe(0.0, BodyPose3D(
                        left_elbow=Vec3(-0.22, 0.02, 0.16), left_wrist=Vec3(-0.08, 0.14, 0.28),
                        right_elbow=Vec3(0.22, 0.02, 0.16), right_wrist=Vec3(0.08, 0.14, 0.28),
                        left_hand=HandPose(0.4, 0.4, 0.4, 0.4, 0.4), right_hand=HandPose(0.4, 0.4, 0.4, 0.4, 0.4),
                        eyebrow_raise=0.3,
                    )),
                    Keyframe(1.0, BodyPose3D(
                        left_elbow=Vec3(-0.35, 0.10, 0.20), left_wrist=Vec3(-0.32, 0.22, 0.32),
                        right_elbow=Vec3(0.35, 0.10, 0.20), right_wrist=Vec3(0.32, 0.22, 0.32),
                        left_hand=HandPose(0.3, 0.3, 0.3, 0.3, 0.3), right_hand=HandPose(0.3, 0.3, 0.3, 0.3, 0.3),
                        eyebrow_raise=0.6,
                    )),
                ],
            )
        )


@dataclass
class SignTimelineItem:
    """Um item de sinal na linha do tempo com temporalidade e metadados."""
    start: float
    end: float
    sign_id: str
    source_text: str
    motion: SignMotion | None = None


class CoarticulationTimeline:
    """Solver de coarticulação e continuidade de movimento para o avatar."""

    def __init__(self, items: Sequence[SignTimelineItem], motion_library: MotionLibrary | None = None) -> None:
        self.items = sorted(items, key=lambda x: x.start)
        self.lib = motion_library or MotionLibrary()
        self.max_pause_coarticulation = 0.35  # segundos

    def get_pose_at(self, current_time: float) -> tuple[BodyPose3D, tuple[str, str, float] | None]:
        """Calcula a pose contínua interpolada no instante especificado."""
        if not self.items:
            return (self._idle_pose(current_time), None)

        # 1. Antes do primeiro sinal
        if current_time < self.items[0].start:
            t_to_first = self.items[0].start - current_time
            if t_to_first <= 0.4:
                # Transição suave de subida do REPOUSO para o início do primeiro sinal
                progress = 1.0 - (t_to_first / 0.4)
                target_pose, _ = self.lib.sample_or_neutral(self.items[0].sign_id, 0.0)
                return (POSE_REST.lerp(target_pose, progress), None)
            return (self._idle_pose(current_time), None)

        # 2. Depois do último sinal
        if current_time > self.items[-1].end:
            t_after_last = current_time - self.items[-1].end
            if t_after_last <= 0.4:
                # Transição suave de descida para o REPOUSO
                progress = t_after_last / 0.4
                last_pose, _ = self.lib.sample_or_neutral(self.items[-1].sign_id, 1.0)
                return (last_pose.lerp(POSE_REST, progress), None)
            return (self._idle_pose(current_time), None)

        # 3. Durante um sinal ativo
        for idx, item in enumerate(self.items):
            if item.start <= current_time <= item.end:
                duration = max(0.01, item.end - item.start)
                progress = (current_time - item.start) / duration
                pose, is_cat = self.lib.sample_or_neutral(item.sign_id, progress)
                active_info = (item.sign_id, item.source_text, progress)
                return (pose, active_info)

            # 4. Intervalo / Transição entre dois sinais consecutivos
            if idx < len(self.items) - 1:
                next_item = self.items[idx + 1]
                if item.end < current_time < next_item.start:
                    gap = next_item.start - item.end
                    rel_t = (current_time - item.end) / gap

                    pose_a, _ = self.lib.sample_or_neutral(item.sign_id, 1.0)
                    pose_b, _ = self.lib.sample_or_neutral(next_item.sign_id, 0.0)

                    if gap <= self.max_pause_coarticulation:
                        # Coarticulação fluida direta: mão vai de A para B no espaço de sinalização
                        # sem cair para o repouso!
                        return (pose_a.lerp(pose_b, rel_t), None)
                    else:
                        # Pausa longa: transiciona para repouso e depois sobe para o próximo
                        if rel_t < 0.5:
                            return (pose_a.lerp(POSE_REST, rel_t * 2.0), None)
                        else:
                            return (POSE_REST.lerp(pose_b, (rel_t - 0.5) * 2.0), None)

        return (self._idle_pose(current_time), None)

    def _idle_pose(self, t: float) -> BodyPose3D:
        """Micro-respiração sutil no repouso."""
        breath = math.sin(t * 2.0) * 0.004
        return BodyPose3D(
            left_elbow=POSE_REST.left_elbow + Vec3(0, breath * 0.5, 0),
            left_wrist=POSE_REST.left_wrist + Vec3(0, breath, 0),
            right_elbow=POSE_REST.right_elbow + Vec3(0, breath * 0.5, 0),
            right_wrist=POSE_REST.right_wrist + Vec3(0, breath, 0),
            left_hand=POSE_REST.left_hand,
            right_hand=POSE_REST.right_hand,
        )
