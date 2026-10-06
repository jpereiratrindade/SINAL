# LIBRAS-IR

## Papel

LIBRAS-IR é o contrato serializável entre tradução linguística e movimento ou
renderização. Ele existe para que trocar VLibras por um motor próprio não exija
alterar mídia, transcrição ou análise do português.

O exemplo abaixo é arquitetural, não uma recomendação linguística. O esquema
formal e o validador pertencem à Fase 3.

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
    "status": "machine-generated"
  },
  "utterances": [
    {
      "source": "Amanhã teremos aula às oito horas.",
      "source_timing": {"start": 12.4, "end": 15.9},
      "semantic": {
        "topic": "AULA",
        "time": "AMANHÃ",
        "time_detail": "OITO-HORAS"
      },
      "signs": [
        {"id": "AMANHA", "start": 12.4, "duration": 0.7, "confidence": null},
        {"id": "AULA", "start": 13.1, "duration": 0.8, "confidence": null}
      ],
      "non_manual": {
        "eyebrows": null,
        "eyes": null,
        "mouth": null,
        "head": null,
        "gaze": null,
        "body": null
      }
    }
  ]
}
```

## Invariantes planejadas

- `schema` e versão semântica são obrigatórios;
- intervalos e durações são não negativos e finitos;
- uma unidade temporal não termina antes de começar;
- sinais desconhecidos não são inventados: são representados como lacuna
  explícita, soletração quando decidida pelo tradutor ou erro revisável;
- marcadores manuais e não manuais são dados linguísticos;
- confiança ausente é diferente de confiança máxima;
- `review.status` aceita inicialmente `machine-generated`, `human-reviewed`,
  `human-corrected` ou `approved`;
- metadados identificam fonte, gerador, tradutor e caráter automático.

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

