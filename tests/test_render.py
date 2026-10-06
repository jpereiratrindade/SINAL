from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sinal.libras.ir import build_ir
from sinal.media.subtitles import SubtitleCue
from sinal.render.synthetic import SyntheticPlaceholderRenderer


class RenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cues = [
            SubtitleCue(1, 0.0, 2.0, "Olá mundo"),
            SubtitleCue(2, 3.0, 5.0, "Acessibilidade Libras"),
        ]
        self.doc = build_ir(self.cues, ["OLA MUNDO", "ACESSIBILIDADE LIBRAS"], translator="test", automatic=True)

    @patch("sinal.render.synthetic.run_ffmpeg")
    def test_synthetic_renderer_builds_ffmpeg_filter_and_runs(self, mock_ffmpeg) -> None:
        renderer = SyntheticPlaceholderRenderer()
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = Path(tmp_dir) / "avatar.mp4"
            dest = renderer.render(self.doc, output_file, duration=5.0)

            self.assertEqual(dest, output_file)
            self.assertTrue(mock_ffmpeg.called)
            args = mock_ffmpeg.call_args[0][0]
            self.assertIn("-filter_complex_script", args)
            self.assertIn("color=c=0x16161e:s=640x1080:r=30:d=5.000", " ".join(args))

    def test_invalid_parameters_raise_error(self) -> None:
        renderer = SyntheticPlaceholderRenderer()
        with self.assertRaises(ValueError):
            renderer.render(self.doc, width=-100)
        with self.assertRaises(ValueError):
            renderer.render(self.doc, duration=-5.0)


if __name__ == "__main__":
    unittest.main()
