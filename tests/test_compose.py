from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sinal.compose.video import compose_libras_video
from sinal.media.probe import AudioStream, MediaInfo, SubtitleStream, VideoStream


class ComposeTests(unittest.TestCase):
    @staticmethod
    def info(path: Path, duration: float, width: int, height: int) -> MediaInfo:
        return MediaInfo(
            path,
            duration,
            "mov,mp4",
            (VideoStream(0, "h264", width, height, None, True),),
            (AudioStream(1, "aac", 2, 48000, "por", True),),
            (SubtitleStream(2, "mov_text", "por", None, True, False),),
        )

    @patch("sinal.compose.video.run_ffmpeg")
    @patch("sinal.compose.video.inspect_media")
    def test_overlays_synchronized_avatar_and_preserves_streams(
        self, inspect, ffmpeg
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            avatar = root / "avatar.mp4"
            source.write_bytes(b"source")
            avatar.write_bytes(b"avatar")
            inspect.side_effect = [
                self.info(source, 10.0, 1920, 1080),
                self.info(avatar, 10.0, 640, 1080),
            ]

            destination = compose_libras_video(
                source, avatar, root / "final.mp4", position="bottom-left"
            )

        self.assertEqual(destination.name, "final.mp4")
        arguments = ffmpeg.call_args.args[0]
        graph = arguments[arguments.index("-filter_complex") + 1]
        self.assertIn("overlay=x=24:y=H-h-24", graph)
        self.assertIn("0:a?", arguments)
        self.assertIn("0:s?", arguments)
        self.assertEqual(arguments[arguments.index("-c:s") + 1], "mov_text")

    @patch("sinal.compose.video.run_ffmpeg")
    @patch("sinal.compose.video.inspect_media")
    def test_rejects_an_avatar_with_a_different_timeline(self, inspect, ffmpeg) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            avatar = root / "avatar.mp4"
            source.write_bytes(b"source")
            avatar.write_bytes(b"avatar")
            inspect.side_effect = [
                self.info(source, 10.0, 1920, 1080),
                self.info(avatar, 5.0, 640, 1080),
            ]

            with self.assertRaisesRegex(ValueError, "compartilhar a timeline"):
                compose_libras_video(source, avatar, root / "final.mp4")

        ffmpeg.assert_not_called()


if __name__ == "__main__":
    unittest.main()
