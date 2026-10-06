# LIBRAS-IR

## Papel

LIBRAS-IR é o contrato serializável entre tradução linguística e movimento ou
renderização. Ele existe para que trocar VLibras por um motor próprio não exija
alterar mídia, transcrição ou análise do português.

O exemplo abaixo é arquitetural, não uma recomendação linguística. O esquema
formal está em `sinal/libras/schema/libras-ir-0.1.0.json` e as invariantes
temporais também são verificadas pelo validador Python.

```json
{
  "schema": "sinal.libras-ir",
  "version": "0.1.0",
  "source_language": "pt-BR",
  "target_language": "libras-BR",
  "metadata": {
    "generated_by": "SINAL",
    "generator_version": "0.1.0",
    "source": "subtitle",
    "translator": "mock",
    "automatic": true
  },
  "review": {
    "status": "translation-pending"
  },
  "utterances": [
    {
      "source": "Amanhã teremos aula às oito horas.",
      "source_timing": {"start": 12.4, "end": 15.9},
      "semantic": {},
      "translation": {
        "gloss": null,
        "status": "pending"
      },
      "signs": [],
      "non_manual": {
        "eyebrows": null,
        "eyes": null,
        "mouth": null,
        "head": null,
        "gaze": null,
        "body": null
      },
      "gaps": [
        {
          "source": "Amanhã teremos aula às oito horas.",
          "reason": "translation-not-run",
          "review_required": true
        }
      ]
    }
  ]
}
```

## Invariantes implementadas

- `schema` e versão semântica são obrigatórios;
- intervalos e durações são não negativos e finitos;
- uma unidade temporal não termina antes de começar;
- sinais desconhecidos não são inventados: são representados como lacuna
  explícita, soletração quando decidida pelo tradutor ou erro revisável;
- marcadores manuais e não manuais são dados linguísticos;
- confiança ausente é diferente de confiança máxima;
- `review.status` também distingue `translation-pending` de conteúdo
  `machine-generated`, `human-reviewed`, `human-corrected` ou `approved`;
- metadados identificam fonte, gerador, tradutor e caráter automático.

## CLI

```bash
sinal build-ir legenda.srt --engine mock --output legenda.libras-ir.json
sinal validate-ir legenda.libras-ir.json
```

O motor `mock` nunca cria glosas ou sinais falsos. Para cada legenda ele gera
uma lacuna revisável com `translation-not-run`. O motor `vlibras` somente é
chamado com `--allow-network` e um endpoint explícito; seus sinais recebem
`timing_source: estimated-uniform`, pois o tradutor textual não fornece o tempo
individual de cada sinal.

## Evolução corporal

O modelo deverá comportar cabeça, olhar, sobrancelhas, olhos, boca, tronco,
ombros, cotovelos, punhos, mãos, orientação de palma, localização, trajetória e
configuração de dedos. Um modelo futuro pode usar 21 pontos por mão sem mudar o
contrato entre as grandes camadas.

## Versionamento

Mudança incompatível incrementa a versão principal. Campos novos opcionais
incrementam a versão secundária; correções documentais e de validação que não
alterem documentos válidos incrementam patch. Renderers declaram as versões que
aceitam e devem falhar claramente diante de versão incompatível.
