from __future__ import annotations

import unittest
from unittest.mock import patch

from sinal.libras.translator import VlibrasHttpTranslator
from sinal.media.subtitles import SubtitleCue


class _Response:
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return b"OLA MUNDO"


class LibrasTranslatorTests(unittest.TestCase):
    @patch("sinal.libras.translator.urlopen", return_value=_Response())
    def test_vlibras_adapter_maps_plain_gloss_response(self, urlopen) -> None:
        translator = VlibrasHttpTranslator(endpoint="http://127.0.0.1:3000")
        document = translator.translate(
            [SubtitleCue(1, 0.0, 2.0, "Olá, mundo.")]
        )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:3000/translate")
        self.assertEqual(document["utterances"][0]["translation"]["gloss"], "OLA MUNDO")
        self.assertEqual(document["metadata"]["translator"], "vlibras-http")


if __name__ == "__main__":
    unittest.main()
