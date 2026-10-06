"""Construção, validação e serialização do LIBRAS-IR 0.1.0."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from sinal import __version__
from sinal.media.subtitles import SubtitleCue


SCHEMA_NAME = "sinal.libras-ir"
SCHEMA_VERSION = "0.1.0"
REVIEW_STATUSES = {
    "machine-generated",
    "translation-pending",
    "human-reviewed",
    "human-corrected",
    "approved",
}
NON_MANUAL_FIELDS = ("eyebrows", "eyes", "mouth", "head", "gaze", "body")


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} deve ser numérico")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{field} deve ser finito e não negativo")
    return parsed


def build_ir(
    cues: list[SubtitleCue],
    glosses: list[str | None],
    *,
    translator: str,
    automatic: bool,
) -> dict[str, Any]:
    """Cria LIBRAS-IR preservando a linha do tempo e lacunas explícitas."""

    if len(cues) != len(glosses):
        raise ValueError("cada legenda deve possuir um resultado de tradução")

    utterances: list[dict[str, Any]] = []
    translated = True
    for cue, raw_gloss in zip(cues, glosses):
        gloss = raw_gloss.strip() if raw_gloss else ""
        tokens = gloss.split()
        duration = cue.end_seconds - cue.start_seconds
        signs: list[dict[str, Any]] = []
        if tokens:
            slot = duration / len(tokens)
            for position, token in enumerate(tokens):
                start = cue.start_seconds + position * slot
                sign_duration = (
                    cue.end_seconds - start if position == len(tokens) - 1 else slot
                )
                signs.append(
                    {
                        "id": token,
                        "start": start,
                        "duration": sign_duration,
                        "confidence": None,
                        "timing_source": "estimated-uniform",
                    }
                )
        else:
            translated = False

        utterance: dict[str, Any] = {
            "source": cue.text,
            "source_timing": {
                "start": cue.start_seconds,
                "end": cue.end_seconds,
            },
            "semantic": {},
            "translation": {
                "gloss": gloss or None,
                "status": "machine-generated" if gloss else "pending",
            },
            "signs": signs,
            "non_manual": {field: None for field in NON_MANUAL_FIELDS},
            "gaps": [],
        }
        if not gloss:
            utterance["gaps"].append(
                {
                    "source": cue.text,
                    "reason": "translation-not-run",
                    "review_required": True,
                }
            )
        utterances.append(utterance)

    document: dict[str, Any] = {
        "schema": SCHEMA_NAME,
        "version": SCHEMA_VERSION,
        "source_language": "pt-BR",
        "target_language": "libras-BR",
        "metadata": {
            "generated_by": "SINAL",
            "generator_version": __version__,
            "source": "subtitle",
            "translator": translator,
            "automatic": automatic,
        },
        "review": {
            "status": "machine-generated" if translated else "translation-pending"
        },
        "utterances": utterances,
    }
    validate_ir(document)
    return document


def validate_ir(document: object) -> None:
    """Valida as invariantes essenciais do LIBRAS-IR sem dependência externa."""

    if not isinstance(document, dict):
        raise ValueError("LIBRAS-IR deve ser um objeto JSON")
    if document.get("schema") != SCHEMA_NAME:
        raise ValueError(f"schema deve ser {SCHEMA_NAME!r}")
    if document.get("version") != SCHEMA_VERSION:
        raise ValueError(f"versão LIBRAS-IR incompatível: {document.get('version')!r}")
    if document.get("source_language") != "pt-BR":
        raise ValueError("source_language deve ser 'pt-BR'")
    if document.get("target_language") != "libras-BR":
        raise ValueError("target_language deve ser 'libras-BR'")

    metadata = document.get("metadata")
    if not isinstance(metadata, dict) or not metadata.get("translator"):
        raise ValueError("metadata.translator é obrigatório")
    for field in ("generated_by", "generator_version", "source"):
        if not isinstance(metadata.get(field), str) or not metadata[field].strip():
            raise ValueError(f"metadata.{field} é obrigatório")
    if not isinstance(metadata.get("automatic"), bool):
        raise ValueError("metadata.automatic deve ser booleano")
    review = document.get("review")
    if not isinstance(review, dict) or review.get("status") not in REVIEW_STATUSES:
        raise ValueError("review.status é inválido")
    utterances = document.get("utterances")
    if not isinstance(utterances, list):
        raise ValueError("utterances deve ser uma lista")

    previous_start = -1.0
    for index, utterance in enumerate(utterances, start=1):
        prefix = f"utterances[{index - 1}]"
        if not isinstance(utterance, dict):
            raise ValueError(f"{prefix} deve ser um objeto")
        if not isinstance(utterance.get("source"), str) or not utterance["source"].strip():
            raise ValueError(f"{prefix}.source é obrigatório")
        timing = utterance.get("source_timing")
        if not isinstance(timing, dict):
            raise ValueError(f"{prefix}.source_timing é obrigatório")
        start = _finite_number(timing.get("start"), f"{prefix}.source_timing.start")
        end = _finite_number(timing.get("end"), f"{prefix}.source_timing.end")
        if end < start:
            raise ValueError(f"{prefix}: intervalo de origem invertido")
        if start < previous_start:
            raise ValueError(f"{prefix}: linha do tempo fora de ordem")
        previous_start = start

        signs = utterance.get("signs")
        if not isinstance(signs, list):
            raise ValueError(f"{prefix}.signs deve ser uma lista")
        translation = utterance.get("translation")
        if not isinstance(translation, dict):
            raise ValueError(f"{prefix}.translation é obrigatória")
        translation_status = translation.get("status")
        gloss = translation.get("gloss")
        if translation_status not in {"pending", "machine-generated"}:
            raise ValueError(f"{prefix}.translation.status é inválido")
        if gloss is not None and (not isinstance(gloss, str) or not gloss.strip()):
            raise ValueError(f"{prefix}.translation.gloss é inválida")
        if translation_status == "pending" and gloss is not None:
            raise ValueError(f"{prefix}: tradução pendente não pode possuir glosa")
        if translation_status == "machine-generated" and gloss is None:
            raise ValueError(f"{prefix}: tradução automática requer glosa")
        if not isinstance(utterance.get("semantic"), dict):
            raise ValueError(f"{prefix}.semantic deve ser um objeto")

        previous_sign_start = start
        for sign_index, sign in enumerate(signs):
            sign_prefix = f"{prefix}.signs[{sign_index}]"
            if not isinstance(sign, dict) or not str(sign.get("id", "")).strip():
                raise ValueError(f"{sign_prefix}.id é obrigatório")
            sign_start = _finite_number(sign.get("start"), f"{sign_prefix}.start")
            sign_duration = _finite_number(
                sign.get("duration"), f"{sign_prefix}.duration"
            )
            if sign_start < previous_sign_start:
                raise ValueError(f"{sign_prefix}: sinais fora de ordem")
            previous_sign_start = sign_start
            if sign_start < start or sign_start + sign_duration > end + 1e-6:
                raise ValueError(f"{sign_prefix} ultrapassa o intervalo de origem")
            confidence = sign.get("confidence")
            if confidence is not None:
                confidence_value = _finite_number(
                    confidence, f"{sign_prefix}.confidence"
                )
                if confidence_value > 1:
                    raise ValueError(f"{sign_prefix}.confidence deve estar entre 0 e 1")
            if not isinstance(sign.get("timing_source"), str):
                raise ValueError(f"{sign_prefix}.timing_source é obrigatório")

        non_manual = utterance.get("non_manual")
        if not isinstance(non_manual, dict) or any(
            field not in non_manual for field in NON_MANUAL_FIELDS
        ):
            raise ValueError(f"{prefix}.non_manual está incompleto")
        gaps = utterance.get("gaps")
        if not isinstance(gaps, list):
            raise ValueError(f"{prefix}.gaps deve ser uma lista")
        for gap_index, gap in enumerate(gaps):
            gap_prefix = f"{prefix}.gaps[{gap_index}]"
            if not isinstance(gap, dict):
                raise ValueError(f"{gap_prefix} deve ser um objeto")
            if not isinstance(gap.get("reason"), str) or not gap["reason"].strip():
                raise ValueError(f"{gap_prefix}.reason é obrigatório")
            if not isinstance(gap.get("review_required"), bool):
                raise ValueError(f"{gap_prefix}.review_required deve ser booleano")


def write_ir(
    document: dict[str, Any], output_path: str | Path, *, overwrite: bool = False
) -> Path:
    destination = Path(output_path)
    validate_ir(document)
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"arquivo de saída já existe: {destination}; use --overwrite para substituir"
        )
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"diretório de saída não encontrado: {destination.parent}")
    destination.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return destination


def load_ir(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"LIBRAS-IR não encontrado: {source}")
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON LIBRAS-IR inválido: {error}") from error
    validate_ir(document)
    return document
