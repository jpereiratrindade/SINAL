from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sinal.animation.motion import MotionLibrary
from sinal.libras.ir import build_ir
from sinal.media.subtitles import SubtitleCue
from sinal.render.readiness import audit_render_readiness


def _pose() -> dict[str, object]:
    return {
        "left_elbow": [-0.24, -0.02, 0.12],
        "left_wrist": [-0.12, 0.08, 0.24],
        "right_elbow": [0.24, -0.02, 0.12],
        "right_wrist": [0.12, 0.08, 0.24],
        "left_hand": {"thumb": 0.2, "index": 0.2, "middle": 0.2, "ring": 0.2, "pinky": 0.2},
        "right_hand": {"thumb": 0.2, "index": 0.2, "middle": 0.2, "ring": 0.2, "pinky": 0.2},
    }


def _catalog() -> dict[str, object]:
    return {
        "schema": "sinal.motion-catalog",
        "version": "1.0.0",
        "language": "libras-BR",
        "source": {
            "name": "Laboratório de Libras de teste",
            "version": "2026.1",
            "url": "https://example.invalid/catalog",
        },
        "review": {
            "status": "approved",
            "reviewer": "Especialista Libras",
            "reviewed_at": "2026-10-06",
        },
        "motions": [
            {
                "id": "OLA",
                "description": "Movimento revisado para teste",
                "dominant_hand": "right",
                "keyframes": [
                    {"time": 0.0, "pose": _pose()},
                    {"time": 1.0, "pose": _pose()},
                ],
            }
        ],
    }


class RenderReadinessTests(unittest.TestCase):
    def test_reviewed_document_and_catalog_are_renderable(self) -> None:
        document = build_ir(
            [SubtitleCue(1, 0.0, 1.0, "Olá")],
            ["OLA"],
            translator="reviewed-test",
            automatic=False,
        )
        document["review"]["status"] = "approved"

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "motions.json"
            path.write_text(json.dumps(_catalog()), encoding="utf-8")
            report = audit_render_readiness(document, MotionLibrary.from_catalog(path))

        self.assertTrue(report.ready)
        self.assertEqual(report.covered_signs, 1)
        self.assertEqual(report.issues, ())

    def test_machine_translation_and_prototype_motion_are_blocked(self) -> None:
        document = build_ir(
            [SubtitleCue(1, 0.0, 1.0, "Olá")],
            ["OLA"],
            translator="automatic-test",
            automatic=True,
        )
        report = audit_render_readiness(document, MotionLibrary())

        self.assertFalse(report.ready)
        self.assertEqual(
            {issue.code for issue in report.issues},
            {"document-not-human-reviewed", "unreviewed-motion"},
        )

    def test_missing_motion_is_reported_without_neutral_fallback_claim(self) -> None:
        document = build_ir(
            [SubtitleCue(1, 0.0, 1.0, "Mundo")],
            ["MUNDO"],
            translator="reviewed-test",
            automatic=False,
        )
        document["review"]["status"] = "approved"
        report = audit_render_readiness(document, MotionLibrary(include_prototypes=False))

        self.assertFalse(report.ready)
        self.assertEqual(report.issues[0].code, "missing-motion")
        self.assertEqual(report.issues[0].sign_id, "MUNDO")


if __name__ == "__main__":
    unittest.main()
