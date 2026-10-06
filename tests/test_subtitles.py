from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sinal.media.probe import MediaInfo, SubtitleStream
from sinal.media.subtitles import (
    NoSubtitleStreamError,
    extract_subtitles,
    parse_srt,
    timestamp_to_seconds,
)


class SubtitleTests(unittest.TestCase):
    def test_parse_srt_with_bom_crlf_and_multiline_text(self) -> None:
        content = (
            "\ufeff1\r\n00:00:01,250 --> 00:00:03,000\r\nBom dia.\r\nTudo bem?\r\n"
            "\r\n2\r\n00:01:00.000 --> 00:01:02.500 align:start\r\nSim.\r\n"
        )
        cues = parse_srt(content)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0].text, "Bom dia.\nTudo bem?")
        self.assertEqual(cues[0].start_seconds, 1.25)
        self.assertEqual(cues[1].end_seconds, 62.5)

    def test_timestamp_validation(self) -> None:
        self.assertEqual(timestamp_to_seconds("01:02:03,004"), 3723.004)
        with self.assertRaises(ValueError):
            timestamp_to_seconds("00:99:00,000")

    @patch("sinal.media.subtitles.run_ffmpeg")
    @patch("sinal.media.subtitles.inspect_media")
    def test_extract_uses_absolute_ffprobe_stream_index(self, inspect, ffmpeg) -> None:
        inspect.return_value = MediaInfo(
            path=Path("input.mkv"),
            duration_seconds=2.0,
            format_name="matroska",
            videos=(),
            audios=(),
            subtitles=(SubtitleStream(3, "subrip", "por", None, True, False),),
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.srt"
            result = extract_subtitles("input.mkv", output)

        self.assertEqual(result, output)
        arguments = ffmpeg.call_args.args[0]
        self.assertEqual(arguments[arguments.index("-map") + 1], "0:3")
        self.assertIn("srt", arguments)

    @patch("sinal.media.subtitles.inspect_media")
    def test_extract_reports_absent_subtitle(self, inspect) -> None:
        inspect.return_value = MediaInfo(
            Path("input.mp4"), 1.0, "mp4", (), (), ()
        )
        with self.assertRaises(NoSubtitleStreamError):
            extract_subtitles("input.mp4")


if __name__ == "__main__":
    unittest.main()

