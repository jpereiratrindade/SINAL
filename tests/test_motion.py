"""Testes unitários para a arquitetura de SignMotion, CoarticulationTimeline e eliminação do hash."""

import unittest

from sinal.animation.motion import (
    Keyframe,
    SignMotion,
    MotionLibrary,
    CoarticulationTimeline,
    SignTimelineItem,
    POSE_NEUTRAL_SIGNING_SPACE,
)
from sinal.render.poses import POSE_REST, BodyPose3D, HandPose
from sinal.render.math3d import Vec3


class MotionTests(unittest.TestCase):
    def test_motion_library_samples_registered_sign(self) -> None:
        lib = MotionLibrary()
        self.assertTrue(lib.has_motion("OLA"))
        pose_mid, found = lib.sample_or_neutral("OLA", 0.5)
        self.assertTrue(found)
        self.assertIsInstance(pose_mid, BodyPose3D)
        # Verifica que o braço está levantado para o aceno
        self.assertGreater(pose_mid.right_wrist.y, 0.3)

    def test_unregistered_signs_do_not_use_hash_invention(self) -> None:
        lib = MotionLibrary()
        self.assertFalse(lib.has_motion("PALAVRA_INEXISTENTE_XYZ"))
        pose, found = lib.sample_or_neutral("PALAVRA_INEXISTENTE_XYZ", 0.5)
        self.assertFalse(found)
        # Deve retornar o espaço neutro honesto de sinalização sem flutuações randômicas
        self.assertEqual(pose.left_wrist, POSE_NEUTRAL_SIGNING_SPACE.left_wrist)
        self.assertEqual(pose.right_wrist, POSE_NEUTRAL_SIGNING_SPACE.right_wrist)

    def test_coarticulation_smoothly_chains_adjacent_signs_without_falling_to_rest(self) -> None:
        lib = MotionLibrary()
        items = [
            SignTimelineItem(start=1.0, end=1.8, sign_id="OLA", source_text="Olá"),
            SignTimelineItem(start=2.0, end=2.8, sign_id="PAMPA", source_text="Pampa"),
        ]
        timeline = CoarticulationTimeline(items, lib)

        # Durante o intervalo (gap de 0.2s entre 1.8 e 2.0s), a pose deve transicionar
        # diretamente entre o final de OLA e o início de PAMPA, sem cair para o repouso.
        pose_in_gap, active = timeline.get_pose_at(1.9)
        self.assertIsNone(active)  # Transição entre sinais
        # A mão direita deve permanecer no espaço de sinalização (y > 0.0)
        self.assertGreater(pose_in_gap.right_wrist.y, 0.1)

    def test_pause_longer_than_threshold_returns_to_rest(self) -> None:
        lib = MotionLibrary()
        items = [
            SignTimelineItem(start=1.0, end=1.5, sign_id="OLA", source_text="Olá"),
            SignTimelineItem(start=5.0, end=5.5, sign_id="PAMPA", source_text="Pampa"),
        ]
        timeline = CoarticulationTimeline(items, lib)

        # Em t = 3.0s (meio de uma pausa longa de 3.5s), deve estar no repouso
        pose_in_long_pause, active = timeline.get_pose_at(3.0)
        self.assertIsNone(active)
        self.assertLess(pose_in_long_pause.right_wrist.y, 0.0)


if __name__ == "__main__":
    unittest.main()
