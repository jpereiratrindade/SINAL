from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from sinal.cli.main import main
from sinal.media.probe import AudioStream, MediaInfo, SubtitleStream, VideoStream
from sinal.media.subtitles import NoSubtitleStreamError


class CliTests(unittest.TestCase):
    @staticmethod
    def media_info() -> MediaInfo:
        return MediaInfo(
            Path("video.mp4"),
            154.0,
            "mov,mp4",
            (VideoStream(0, "h264", 1920, 1080, None, True),),
            (AudioStream(1, "aac", 2, 48000, "por", True),),
            (SubtitleStream(2, "subrip", "por", None, True, False),),
        )

    @patch("sinal.cli.main.inspect_media")
    def test_inspect_human_output(self, inspect) -> None:
        inspect.return_value = self.media_info()
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["inspect", "video.mp4"])
        self.assertEqual(status, 0)
        rendered = output.getvalue()
        self.assertIn("SINAL 0.1.0", rendered)
        self.assertIn("resolution: 1920x1080", rendered)
        self.assertIn("stream: 2", rendered)
        self.assertIn("language: por", rendered)

    @patch("sinal.cli.main.inspect_media")
    def test_inspect_json_output(self, inspect) -> None:
        inspect.return_value = self.media_info()
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["inspect", "video.mp4", "--json"])
        document = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(document["subtitles"][0]["codec"], "subrip")

    @patch("sinal.cli.main.extract_subtitles")
    def test_no_subtitle_message(self, extract) -> None:
        extract.side_effect = NoSubtitleStreamError("No subtitle stream found.")
        error = io.StringIO()
        with redirect_stderr(error):
            status = main(["extract-subtitles", "video.mp4"])
        self.assertEqual(status, 2)
        self.assertEqual(error.getvalue().strip(), "No subtitle stream found.")

    @patch("sinal.cli.main.prepare_media")
    def test_process_accepts_video_and_external_srt(self, prepare) -> None:
        prepare.return_value = Path("prepared.mp4")
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(
                [
                    "process",
                    "video.mp4",
                    "--srt",
                    "captions.srt",
                    "--output",
                    "prepared.mp4",
                ]
            )
        self.assertEqual(status, 0)
        prepare.assert_called_once_with(
            Path("video.mp4"),
            Path("captions.srt"),
            Path("prepared.mp4"),
            language="por",
            overwrite=False,
        )
        self.assertIn("Media prepared: prepared.mp4", output.getvalue())


if __name__ == "__main__":
    unittest.main()
