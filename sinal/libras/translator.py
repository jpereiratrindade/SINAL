"""Contratos e adapters de tradução para LIBRAS-IR."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from sinal.libras.ir import build_ir
from sinal.media.subtitles import SubtitleCue


class LibrasTranslationError(RuntimeError):
    """Falha observável de um backend de tradução."""


class LibrasTranslator(Protocol):
    def translate(self, cues: list[SubtitleCue]) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class MockLibrasTranslator:
    """Produz lacunas explícitas; nunca simula uma tradução para Libras."""

    def translate(self, cues: list[SubtitleCue]) -> dict[str, object]:
        return build_ir(
            cues,
            [None] * len(cues),
            translator="mock",
            automatic=True,
        )


@dataclass(frozen=True, slots=True)
class VlibrasHttpTranslator:
    """Adapter para uma instância VLibras API explicitamente configurada."""

    endpoint: str = "http://127.0.0.1:3000"
    timeout_seconds: float = 30.0

    def _translate_text(self, text: str) -> str:
        url = urljoin(self.endpoint.rstrip("/") + "/", "translate")
        request = Request(
            url,
            data=json.dumps({"text": text}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "text/plain"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                content = response.read().decode("utf-8").strip()
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace").strip()
            raise LibrasTranslationError(
                f"VLibras respondeu HTTP {error.code}: {detail or error.reason}"
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise LibrasTranslationError(
                f"não foi possível acessar VLibras em {url}: {error}"
            ) from error

        if not content:
            raise LibrasTranslationError("VLibras retornou uma tradução vazia")
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return content
        if isinstance(payload, dict) and isinstance(payload.get("traducao"), str):
            translation = payload["traducao"].strip()
            if translation:
                return translation
            raise LibrasTranslationError("VLibras retornou uma tradução vazia")
        raise LibrasTranslationError("VLibras retornou um formato desconhecido")

    def translate(self, cues: list[SubtitleCue]) -> dict[str, object]:
        glosses = [self._translate_text(cue.text) for cue in cues]
        return build_ir(
            cues,
            glosses,
            translator="vlibras-http",
            automatic=True,
        )
