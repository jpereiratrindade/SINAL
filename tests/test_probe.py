from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from sinal.media.probe import format_duration, inspect_media


class ProbeTests(unittest.TestCase):
    @patch("sinal.media.probe.run_ffprobe")
    def test_probe_video_audio_and_subtitle(self, ffprobe) -> None:
        ffprobe.return_value = {
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "disposition": {"default": 1},
                },
                {
                    "index": 1,
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "channels": 2,
                    "sample_rate": "48000",
                    "tags": {"language": "por"},
                    "disposition": {"default": 1},
                },
                {
                    "index": 2,
                    "codec_type": "subtitle",
                    "codec_name": "subrip",
                    "tags": {"language": "por", "title": "Libras source"},
                    "disposition": {"default": 1, "forced": 0},
                },
            ],
            "format": {"format_name": "mov,mp4", "duration": "154.2"},
        }

        info = inspect_media(Path("video.mp4"))

        self.assertEqual(info.primary_video.codec, "h264")
        self.assertEqual((info.primary_video.width, info.primary_video.height), (1920, 1080))
        self.assertEqual(info.primary_audio.language, "por")
        self.assertEqual(info.subtitles[0].index, 2)
        self.assertTrue(info.has_audio)
        self.assertTrue(info.has_subtitles)
        self.assertEqual(format_duration(info.duration_seconds), "00:02:34")

    @patch("sinal.media.probe.run_ffprobe")
    def test_missing_optional_metadata_is_tolerated(self, ffprobe) -> None:
        ffprobe.return_value = {
            "streams": [{"index": 0, "codec_type": "video"}],
            "format": {},
        }
        info = inspect_media("minimal.mkv")
        self.assertEqual(info.primary_video.codec, "unknown")
        self.assertIsNone(info.duration_seconds)
        self.assertEqual(format_duration(None), "unknown")


if __name__ == "__main__":
    unittest.main()

