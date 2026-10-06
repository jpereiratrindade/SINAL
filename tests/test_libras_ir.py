from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from sinal.libras.ir import build_ir, load_ir, validate_ir, write_ir
from sinal.libras.translator import MockLibrasTranslator
from sinal.media.subtitles import SubtitleCue


class LibrasIrTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cues = [
            SubtitleCue(1, 1.0, 3.0, "Olá, mundo."),
            SubtitleCue(2, 4.0, 5.0, "Tudo bem?"),
        ]

    def test_mock_records_pending_translation_without_inventing_signs(self) -> None:
        document = MockLibrasTranslator().translate(self.cues)

        self.assertEqual(document["review"]["status"], "translation-pending")
        self.assertEqual(document["metadata"]["translator"], "mock")
        self.assertEqual(document["utterances"][0]["signs"], [])
        self.assertEqual(
            document["utterances"][0]["gaps"][0]["reason"],
            "translation-not-run",
        )

    def test_glosses_create_estimated_sign_timing(self) -> None:
        document = build_ir(
            self.cues[:1],
            ["OLA MUNDO"],
            translator="test",
            automatic=True,
        )

        signs = document["utterances"][0]["signs"]
        self.assertEqual(document["review"]["status"], "machine-generated")
        self.assertEqual([sign["id"] for sign in signs], ["OLA", "MUNDO"])
        self.assertEqual([sign["duration"] for sign in signs], [1.0, 1.0])
        self.assertTrue(all(sign["timing_source"] == "estimated-uniform" for sign in signs))

    def test_validator_rejects_sign_outside_source_interval(self) -> None:
        document = build_ir(
            self.cues[:1], ["OLA"], translator="test", automatic=True
        )
        invalid = deepcopy(document)
        invalid["utterances"][0]["signs"][0]["duration"] = 3.0

        with self.assertRaisesRegex(ValueError, "ultrapassa"):
            validate_ir(invalid)

    def test_write_and_load_round_trip(self) -> None:
        document = MockLibrasTranslator().translate(self.cues)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "captions.libras-ir.json"
            write_ir(document, destination)
            loaded = load_ir(destination)

        self.assertEqual(loaded, document)


if __name__ == "__main__":
    unittest.main()
