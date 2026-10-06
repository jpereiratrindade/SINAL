from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sinal.media.probe import AudioStream, MediaInfo, VideoStream
from sinal.transcription.base import TranscriptionError
from sinal.transcription.mock import MockTranscriber
from sinal.transcription.whisper import WhisperTranscriber


class TranscriptionTests(unittest.TestCase):
    @patch("sinal.transcription.mock.inspect_media")
    def test_mock_transcriber_creates_uniform_cues(self, mock_inspect) -> None:
        mock_inspect.return_value = MediaInfo(
            path=Path("dummy.mp4"),
            duration_seconds=12.0,
            format_name="mp4",
            videos=(VideoStream(0, "h264", 1920, 1080, None, True),),
            audios=(AudioStream(1, "aac", 2, 48000, "por", True),),
            subtitles=(),
        )
        transcriber = MockTranscriber()
        cues = transcriber.transcribe("dummy.mp4")

        self.assertEqual(len(cues), 3)
        self.assertEqual(cues[0].start_seconds, 0.0)
        self.assertEqual(cues[0].end_seconds, 4.0)
        self.assertEqual(cues[2].end_seconds, 12.0)

    def test_whisper_transcriber_raises_clear_error_when_packages_missing(self) -> None:
        transcriber = WhisperTranscriber()
        with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp:
            with patch.dict("sys.modules", {"faster_whisper": None, "whisper": None}):
                with self.assertRaises(TranscriptionError) as ctx:
                    transcriber.transcribe(tmp.name)
                self.assertIn("faster-whisper", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
