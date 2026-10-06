from __future__ import annotations

import unittest

from sinal.language.glosser import pt_to_libras_gloss
from sinal.libras.translator import RuleBasedLibrasTranslator
from sinal.media.subtitles import SubtitleCue


class GlosserTests(unittest.TestCase):
    def test_stopwords_removal_and_uppercase_glosses(self) -> None:
        text = "complexo, antigo e cheio de vida."
        gloss = pt_to_libras_gloss(text)
        self.assertEqual(gloss, "COMPLEXO ANTIGO CHEIO VIDA")

    def test_lexicon_mapping(self) -> None:
        text = "Olá, o Pampa está vivo!"
        gloss = pt_to_libras_gloss(text)
        self.assertEqual(gloss, "OLA PAMPA ESTAR VIVO")

    def test_rule_based_translator_generates_ir_with_signs(self) -> None:
        cues = [
            SubtitleCue(1, 0.0, 2.0, "O Pampa é complexo."),
        ]
        doc = RuleBasedLibrasTranslator().translate(cues)
        self.assertEqual(doc["review"]["status"], "machine-generated")
        self.assertEqual(doc["utterances"][0]["translation"]["status"], "machine-generated")
        signs = doc["utterances"][0]["signs"]
        self.assertEqual([s["id"] for s in signs], ["PAMPA", "SER", "COMPLEXO"])
        self.assertEqual(len(doc["utterances"][0]["gaps"]), 0)


if __name__ == "__main__":
    unittest.main()
