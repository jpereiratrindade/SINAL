"""Auditoria fail-closed antes de apresentar uma animação como Libras."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sinal.animation.motion import MotionLibrary
from sinal.libras.ir import validate_ir
from sinal.render.base import LibrasRenderError


REVIEWED_DOCUMENT_STATUSES = frozenset({"human-reviewed", "human-corrected", "approved"})


@dataclass(frozen=True)
class RenderIssue:
    code: str
    message: str
    utterance_index: int | None = None
    sign_index: int | None = None
    sign_id: str | None = None

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"code": self.code, "message": self.message}
        if self.utterance_index is not None:
            result["utterance_index"] = self.utterance_index
        if self.sign_index is not None:
            result["sign_index"] = self.sign_index
        if self.sign_id is not None:
            result["sign_id"] = self.sign_id
        return result


@dataclass(frozen=True)
class RenderReadinessReport:
    total_signs: int
    covered_signs: int
    issues: tuple[RenderIssue, ...]

    @property
    def ready(self) -> bool:
        return not self.issues and self.total_signs > 0

    def as_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "total_signs": self.total_signs,
            "covered_signs": self.covered_signs,
            "issues": [issue.as_dict() for issue in self.issues],
        }


def audit_render_readiness(
    document: dict[str, Any], motion_library: MotionLibrary
) -> RenderReadinessReport:
    """Verifica tradução, lacunas, cobertura e revisão dos movimentos."""
    validate_ir(document)
    issues: list[RenderIssue] = []
    total_signs = 0
    covered_signs = 0

    review_status = document.get("review", {}).get("status")
    if review_status not in REVIEWED_DOCUMENT_STATUSES:
        issues.append(
            RenderIssue(
                "document-not-human-reviewed",
                "a tradução precisa de revisão humana em Libras antes da renderização",
            )
        )

    for utterance_index, utterance in enumerate(document.get("utterances", [])):
        for gap in utterance.get("gaps", []):
            if gap.get("review_required", False):
                issues.append(
                    RenderIssue(
                        "unresolved-translation-gap",
                        f"lacuna de tradução não resolvida: {gap.get('reason', 'sem motivo')}",
                        utterance_index=utterance_index,
                    )
                )

        signs = utterance.get("signs", [])
        if not signs:
            issues.append(
                RenderIssue(
                    "utterance-without-signs",
                    "enunciado sem sinais renderizáveis",
                    utterance_index=utterance_index,
                )
            )
        for sign_index, sign in enumerate(signs):
            total_signs += 1
            sign_id = str(sign.get("id", "")).upper().strip()
            motion = motion_library.get(sign_id)
            if motion is None:
                issues.append(
                    RenderIssue(
                        "missing-motion",
                        f"não existe movimento cadastrado para {sign_id}",
                        utterance_index,
                        sign_index,
                        sign_id,
                    )
                )
            elif not motion.provenance.is_reviewed:
                issues.append(
                    RenderIssue(
                        "unreviewed-motion",
                        f"o movimento de {sign_id} não possui revisão humana rastreável",
                        utterance_index,
                        sign_index,
                        sign_id,
                    )
                )
            else:
                covered_signs += 1

    if total_signs == 0:
        issues.append(RenderIssue("empty-timeline", "o documento não contém sinais"))

    return RenderReadinessReport(total_signs, covered_signs, tuple(issues))


def require_render_ready(
    document: dict[str, Any], motion_library: MotionLibrary
) -> RenderReadinessReport:
    report = audit_render_readiness(document, motion_library)
    if report.ready:
        return report

    unique_missing = sorted(
        {issue.sign_id for issue in report.issues if issue.sign_id is not None}
    )
    details = ", ".join(unique_missing[:12])
    if len(unique_missing) > 12:
        details += f" (+{len(unique_missing) - 12})"
    suffix = f" Sinais afetados: {details}." if details else ""
    raise LibrasRenderError(
        "renderização bloqueada: o conteúdo não está pronto para ser "
        f"apresentado como Libras ({len(report.issues)} problema(s)).{suffix} "
        "Use `sinal audit-render` para o relatório completo."
    )

