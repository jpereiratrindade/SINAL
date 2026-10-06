from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sinal.media.audio import NoAudioStreamError, extract_audio
from sinal.media.probe import AudioStream, MediaInfo


class AudioTests(unittest.TestCase):
    @patch("sinal.media.audio.run_ffmpeg")
    @patch("sinal.media.audio.inspect_media")
    def test_extract_audio_produces_mono_16khz_pcm(self, inspect, ffmpeg) -> None:
        inspect.return_value = MediaInfo(
            Path("input.mp4"),
            1.0,
            "mp4",
            (),
            (AudioStream(1, "aac", 2, 48_000, "por", True),),
            (),
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "speech.wav"
            extract_audio("input.mp4", output)

        arguments = ffmpeg.call_args.args[0]
        self.assertEqual(arguments[arguments.index("-map") + 1], "0:1")
        self.assertEqual(arguments[arguments.index("-ar") + 1], "16000")
        self.assertEqual(arguments[arguments.index("-ac") + 1], "1")
        self.assertIn("pcm_s16le", arguments)

    @patch("sinal.media.audio.inspect_media")
    def test_extract_audio_requires_audio_stream(self, inspect) -> None:
        inspect.return_value = MediaInfo(Path("silent.mp4"), 1.0, "mp4", (), (), ())
        with self.assertRaises(NoAudioStreamError):
            extract_audio("silent.mp4")


if __name__ == "__main__":
    unittest.main()

