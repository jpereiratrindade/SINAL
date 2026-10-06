from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sinal.media.prepare import prepare_media
from sinal.media.probe import MediaInfo, VideoStream


class PrepareMediaTests(unittest.TestCase):
    @staticmethod
    def media_info(duration: float = 10.0) -> MediaInfo:
        return MediaInfo(
            Path("video.mp4"),
            duration,
            "mov,mp4",
            (VideoStream(0, "av1", 1920, 1080, None, True),),
            (),
            (),
        )

    @patch("sinal.media.prepare.run_ffmpeg")
    @patch("sinal.media.prepare.inspect_media")
    def test_prepares_mp4_with_mov_text_without_reencoding(self, inspect, ffmpeg) -> None:
        inspect.return_value = self.media_info()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            subtitles = root / "video.srt"
            subtitles.write_text(
                "1\n00:00:00,000 --> 00:00:09,500\nOlá.\n", encoding="utf-8"
            )
            destination = root / "prepared.mp4"
            result = prepare_media(source, subtitles, destination)

        self.assertEqual(result, destination)
        arguments = ffmpeg.call_args.args[0]
        self.assertEqual(arguments[arguments.index("-c:v") + 1], "copy")
        self.assertEqual(arguments[arguments.index("-c:a") + 1], "copy")
        self.assertEqual(arguments[arguments.index("-c:s") + 1], "mov_text")
        self.assertIn("language=por", arguments)

    @patch("sinal.media.prepare.run_ffmpeg")
    @patch("sinal.media.prepare.inspect_media")
    def test_rejects_srt_that_outlasts_video(self, inspect, ffmpeg) -> None:
        inspect.return_value = self.media_info(5.0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            subtitles = root / "video.srt"
            subtitles.write_text(
                "1\n00:00:00,000 --> 00:00:12,000\nOlá.\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "mesma versão"):
                prepare_media(source, subtitles, root / "prepared.mp4")
        ffmpeg.assert_not_called()


if __name__ == "__main__":
    unittest.main()
