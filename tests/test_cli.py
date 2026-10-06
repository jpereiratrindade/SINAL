from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
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

    def test_build_and_validate_mock_ir(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            srt = root / "captions.srt"
            destination = root / "captions.libras-ir.json"
            srt.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nOlá.\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with redirect_stdout(output):
                build_status = main(
                    [
                        "build-ir",
                        str(srt),
                        "--engine",
                        "mock",
                        "--output",
                        str(destination),
                    ]
                )
                validate_status = main(["validate-ir", str(destination)])

        self.assertEqual(build_status, 0)
        self.assertEqual(validate_status, 0)
        self.assertIn("Translation pending", output.getvalue())
        self.assertIn("Valid LIBRAS-IR 0.1.0", output.getvalue())

    def test_vlibras_requires_explicit_network_permission(self) -> None:
        with TemporaryDirectory() as directory:
            srt = Path(directory) / "captions.srt"
            srt.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nOlá.\n",
                encoding="utf-8",
            )
            error = io.StringIO()
            with redirect_stderr(error):
                status = main(["build-ir", str(srt), "--engine", "vlibras"])

        self.assertEqual(status, 1)
        self.assertIn("requer --allow-network", error.getvalue())

    @patch("sinal.cli.main.compose_libras_video")
    def test_compose_accepts_a_synchronized_avatar_video(self, compose) -> None:
        compose.return_value = Path("final.mp4")
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(
                [
                    "compose",
                    "prepared.mp4",
                    "--avatar",
                    "avatar.mp4",
                    "--output",
                    "final.mp4",
                    "--position",
                    "bottom-left",
                ]
            )

        self.assertEqual(status, 0)
        compose.assert_called_once_with(
            Path("prepared.mp4"),
            Path("avatar.mp4"),
            Path("final.mp4"),
            position="bottom-left",
            scale=0.28,
            margin=24,
            overwrite=False,
        )
        self.assertIn("Libras video composed: final.mp4", output.getvalue())


if __name__ == "__main__":
    unittest.main()
