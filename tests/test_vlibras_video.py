from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sinal.libras.ir import build_ir
from sinal.media.probe import MediaInfo, VideoStream
from sinal.media.subtitles import SubtitleCue
from sinal.render.base import LibrasRenderError
from sinal.render.vlibras import (
    VlibrasCaptureResult,
    VlibrasWebRenderer,
    VlibrasWebRuntime,
    libras_ir_to_gloss_text,
    read_render_provenance,
)


class VlibrasWebTests(unittest.TestCase):
    def document(self) -> dict:
        return build_ir(
            [
                SubtitleCue(1, 1.25, 3.5, "Olá, mundo"),
                SubtitleCue(2, 4.0, 5.0, "Bom dia"),
            ],
            ["OLA MUNDO", "BOM_DIA"],
            translator="vlibras-http",
            automatic=True,
        )

    def test_ir_glosses_are_joined_without_inventing_motion(self) -> None:
        self.assertEqual(libras_ir_to_gloss_text(self.document()), "OLA MUNDO BOM_DIA")

    def test_rule_based_pregloss_is_rejected(self) -> None:
        document = build_ir(
            [SubtitleCue(1, 0.0, 1.0, "Olá")],
            ["OLA"],
            translator="rule-based",
            automatic=True,
        )
        with self.assertRaisesRegex(LibrasRenderError, "pré-glosas"):
            libras_ir_to_gloss_text(document)

    @patch.dict("os.environ", {"XDG_DATA_HOME": "/definitely/missing"}, clear=True)
    def test_runtime_requires_explicit_official_checkout(self) -> None:
        with self.assertRaisesRegex(LibrasRenderError, "SINAL_VLIBRAS_WEB_ROOT"):
            VlibrasWebRuntime.from_environment()

    @patch("sinal.render.vlibras.inspect_media")
    @patch("sinal.render.vlibras.run_ffmpeg")
    @patch("sinal.render.vlibras.detect_video_encoder", return_value=("mpeg4", ["-q:v", "3"]))
    def test_renderer_writes_natural_video_and_provenance(
        self, _detect, run_ffmpeg, inspect_media
    ) -> None:
        runtime = MagicMock()
        runtime.version = "7.12.2"
        inspect_media.return_value = MediaInfo(
            path=Path("avatar.mp4"),
            duration_seconds=9.56,
            format_name="mp4",
            videos=(VideoStream(0, "mpeg4", 800, 600, None, True),),
            audios=(),
            subtitles=(),
        )

        def capture(_gloss, directory, **_kwargs):
            recording = directory / "capture.webm"
            recording.write_bytes(b"webm")
            return VlibrasCaptureResult(recording, 5.3, 9.6, 5, 5)

        runtime.capture.side_effect = capture

        def encode(arguments):
            Path(arguments[-1]).write_bytes(b"mp4")

        run_ffmpeg.side_effect = encode
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "avatar.mp4"
            result = VlibrasWebRenderer(runtime, avatar="hosana").render(
                self.document(), destination
            )
            provenance = read_render_provenance(destination)

        self.assertEqual(result, destination)
        self.assertEqual(provenance["renderer"], "vlibras-web-player")
        self.assertEqual(provenance["avatar"], "hosana")
        self.assertEqual(provenance["completed_signs"], 5)
        self.assertFalse(provenance["timeline_synchronized"])
        self.assertEqual(provenance["speed_policy"], "natural-no-retiming")

    @patch("sinal.render.vlibras.inspect_media")
    @patch("sinal.render.vlibras.run_ffmpeg")
    @patch("sinal.render.vlibras.detect_video_encoder", return_value=("mpeg4", []))
    def test_requested_timeline_blocks_retimming_but_preserves_video(
        self, _detect, run_ffmpeg, inspect_media
    ) -> None:
        runtime = MagicMock()
        runtime.version = "7.12.2"
        def capture(_gloss, directory, **_kwargs):
            recording = directory / "capture.webm"
            recording.write_bytes(b"webm")
            return VlibrasCaptureResult(recording, 1.0, 9.0, 2, 2)

        runtime.capture.side_effect = capture
        run_ffmpeg.side_effect = lambda arguments: Path(arguments[-1]).write_bytes(b"mp4")
        inspect_media.return_value = MediaInfo(
            path=Path("avatar.mp4"),
            duration_seconds=9.0,
            format_name="mp4",
            videos=(VideoStream(0, "mpeg4", 640, 1080, None, True),),
            audios=(),
            subtitles=(),
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "avatar.mp4"
            with self.assertRaisesRegex(LibrasRenderError, "composição foi bloqueada"):
                VlibrasWebRenderer(runtime).render(
                    self.document(), destination, duration=5.0
                )
            self.assertTrue(destination.is_file())
            provenance = json.loads(
                destination.with_suffix(".mp4.provenance.json").read_text(encoding="utf-8")
            )
        self.assertFalse(provenance["timeline_synchronized"])


if __name__ == "__main__":
    unittest.main()
