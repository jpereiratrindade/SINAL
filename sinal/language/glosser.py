"""Conversor baseado em regras de Português para Glosas de Libras."""

from __future__ import annotations

import re
import unicodedata

# Palavras funcionais em Português que não têm correspondência direta de sinal em Libras
STOPWORDS_PT = {
    "o", "a", "os", "as",
    "um", "uma", "uns", "umas",
    "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas",
    "por", "pelo", "pela", "pelos", "pelas",
    "com", "para", "pra", "pro", "pras", "pros",
    "ao", "aos", "a", "as",
    "e", "que",
}

EXACT_MAP = {
    "é": "SER",
    "eh": "SER",
    "são": "SER",
    "não": "NAO",
}

# Mapeamentos léxicos e lematizações frequentes após normalização sem acentos
LEXICON_MAP = {
    "sao": "SER",
    "foi": "PASSADO",
    "era": "PASSADO",
    "estou": "ESTAR",
    "esta": "ESTAR",
    "estao": "ESTAR",
    "nao": "NAO",
    "muito": "MUITO",
    "mais": "MAIS",
    "obrigado": "OBRIGADO",
    "obrigada": "OBRIGADO",
    "ola": "OLA",
    "oi": "OI",
    "tchau": "TCHAU",
    "bem-vindo": "BEM-VINDO",
    "bem-vinda": "BEM-VINDO",
}


def _normalize_token(word: str) -> str:
    """Remove acentos e converte para maiúsculas."""
    nfkd = unicodedata.normalize("NFKD", word)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_text.upper()


def pt_to_libras_gloss(text: str) -> str:
    """Converte uma oração em português para estrutura de glosas em Libras.

    Aplica remoção de artigos e preposições, lematização básica e convenção
    em caixa alta adotada para sinais de Libras.
    """
    cleaned = text.strip()
    if not cleaned:
        return ""

    # Extrai tokens alfanuméricos
    raw_tokens = re.findall(r"[\w-]+", cleaned.lower())
    if not raw_tokens:
        return ""

    gloss_tokens: list[str] = []
    for raw in raw_tokens:
        if raw in EXACT_MAP:
            gloss_tokens.append(EXACT_MAP[raw])
            continue

        # Normalização sem acentos para comparação
        clean_raw = "".join(
            c for c in unicodedata.normalize("NFKD", raw) if not unicodedata.combining(c)
        )
        if clean_raw in STOPWORDS_PT:
            continue

        if clean_raw in LEXICON_MAP:
            mapped = LEXICON_MAP[clean_raw]
            if mapped:
                gloss_tokens.append(mapped)
        else:
            gloss_tokens.append(_normalize_token(raw))

    # Se todos os tokens eram stopwords, preserva as palavras originais normalizadas
    if not gloss_tokens:
        gloss_tokens = [_normalize_token(t) for t in raw_tokens]

    return " ".join(gloss_tokens)
