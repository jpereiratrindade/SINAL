from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sinal.media.probe import AudioStream, MediaInfo, VideoStream
from sinal.media.subtitles import SubtitleCue
from sinal.pipeline.runner import run_pipeline


class PipelineTests(unittest.TestCase):
    @patch("sinal.pipeline.runner.compose_libras_video")
    @patch("sinal.pipeline.runner.render_libras")
    @patch("sinal.pipeline.runner.prepare_media")
    @patch("sinal.pipeline.runner.load_srt")
    @patch("sinal.pipeline.runner.inspect_media")
    def test_run_pipeline_end_to_end(
        self,
        mock_inspect,
        mock_load_srt,
        mock_prepare,
        mock_render,
        mock_compose,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            media_path = Path(tmp_dir) / "video.mp4"
            media_path.write_bytes(b"dummy")
            srt_path = Path(tmp_dir) / "video.srt"
            srt_path.write_text("1\n00:00:00,000 --> 00:00:02,000\nOla\n", encoding="utf-8")

            mock_inspect.return_value = MediaInfo(
                path=media_path,
                duration_seconds=2.0,
                format_name="mp4",
                videos=(VideoStream(0, "h264", 1920, 1080, None, True),),
                audios=(AudioStream(1, "aac", 2, 48000, "por", True),),
                subtitles=(),
            )
            mock_load_srt.return_value = [SubtitleCue(1, 0.0, 2.0, "Ola")]
            mock_prepare.return_value = Path(tmp_dir) / "video.prepared.mp4"
            mock_render.return_value = Path(tmp_dir) / "video.avatar.mp4"
            mock_compose.return_value = Path(tmp_dir) / "video.final.mp4"

            res = run_pipeline(
                media_path,
                srt_path=srt_path,
                render=True,
                overwrite=True,
            )

            self.assertTrue(mock_prepare.called)
            self.assertTrue(mock_render.called)
            self.assertTrue(mock_compose.called)
            self.assertEqual(res.final_video, Path(tmp_dir) / "video.final.mp4")


if __name__ == "__main__":
    unittest.main()
