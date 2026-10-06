from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from sinal.libras.ir import build_ir
from sinal.media.subtitles import SubtitleCue
from sinal.render.math3d import Camera3D, Vec3
from sinal.render.poses import get_sign_pose
from sinal.render.three_d import ThreeDLibrasRenderer
from sinal.render.base import LibrasRenderError
from sinal.animation.motion import MotionLibrary, MotionProvenance


class ThreeDTests(unittest.TestCase):
    def test_math3d_vector_and_camera_projection(self) -> None:
        v1 = Vec3(1.0, 2.0, 3.0)
        v2 = Vec3(4.0, 5.0, 6.0)
        self.assertEqual(v1 + v2, Vec3(5.0, 7.0, 9.0))
        self.assertEqual(v1.dot(v2), 32.0)

        cam = Camera3D()
        proj = cam.project(Vec3(0.0, 0.25, 0.0), 640, 480)
        self.assertIsNotNone(proj)
        assert proj is not None
        sx, sy, depth = proj
        self.assertAlmostEqual(sx, 320.0, delta=10.0)
        self.assertAlmostEqual(sy, 240.0, delta=30.0)
        self.assertGreater(depth, 0.0)

    def test_pose_dictionary_retrieval(self) -> None:
        pose_vida = get_sign_pose("VIDA")
        self.assertGreater(pose_vida.right_wrist.y, 0.1)
        self.assertEqual(pose_vida.right_hand.thumb, 0.0)

    @patch("sinal.render.three_d.subprocess.Popen")
    def test_three_d_renderer_invokes_ffmpeg_rawvideo(self, mock_popen) -> None:
        from unittest.mock import MagicMock
        proc = MagicMock()
        proc.stdin = MagicMock()
        proc.returncode = 0
        mock_popen.return_value = proc

        cues = [SubtitleCue(1, 0.0, 1.0, "Olá")]
        doc = build_ir(cues, ["OLA"], translator="test", automatic=True)

        renderer = ThreeDLibrasRenderer(
            default_width=160,
            default_height=240,
            allow_unreviewed_preview=True,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "avatar_3d.mp4"
            dest = renderer.render(doc, out_file, duration=0.1, fps=10)
            self.assertEqual(dest, out_file)
            self.assertTrue(proc.stdin.write.called)

    @patch("sinal.render.three_d.subprocess.Popen")
    def test_three_d_renderer_blocks_unreviewed_motion_before_ffmpeg(self, mock_popen) -> None:
        cues = [SubtitleCue(1, 0.0, 1.0, "Olá")]
        doc = build_ir(cues, ["OLA"], translator="test", automatic=True)

        with self.assertRaisesRegex(LibrasRenderError, "renderização bloqueada"):
            ThreeDLibrasRenderer().render(doc, duration=0.1, fps=10)

        mock_popen.assert_not_called()

    @patch("sinal.render.three_d.subprocess.Popen")
    def test_three_d_renderer_remains_preview_even_with_reviewed_motion(self, mock_popen) -> None:
        doc = build_ir(
            [SubtitleCue(1, 0.0, 1.0, "Olá")],
            ["OLA"],
            translator="reviewed-test",
            automatic=False,
        )
        doc["review"]["status"] = "approved"
        library = MotionLibrary()
        prototype = library.get("OLA")
        assert prototype is not None
        library.register(
            replace(
                prototype,
                provenance=MotionProvenance(
                    source="test corpus",
                    source_version="1",
                    review_status="approved",
                    reviewer="Libras specialist",
                    reviewed_at="2026-10-06",
                ),
            )
        )

        with self.assertRaisesRegex(LibrasRenderError, "renderer procedural"):
            ThreeDLibrasRenderer(motion_library=library).render(doc, duration=0.1)

        mock_popen.assert_not_called()



if __name__ == "__main__":
    unittest.main()
