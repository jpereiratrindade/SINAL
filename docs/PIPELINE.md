# Pipeline

## Prioridade da fonte textual

```text
SRT/VTT fornecido explicitamente
             │ ausente/inválido
             ▼
legenda ou Closed Caption incorporado
             │ ausente/inválido
             ▼
transcrição local do áudio
```

O ASR não deve executar quando já existir legenda válida, salvo solicitação
explícita. Na Fase 1, a ausência de legenda termina com uma mensagem; não aciona
Whisper.

## Fluxo da Fase 1

```text
arquivo ─► FFprobe ─► MediaInfo
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
      saída inspect          stream de legenda
                                      │
                                      ▼
                              FFmpeg ─► .srt
```

Os índices usados em `-map 0:N` são índices absolutos retornados pelo FFprobe.
O stream marcado como padrão vence; sem marca, vence o primeiro da categoria.

Quando vídeo e SRT chegam separados, `sinal process VIDEO --srt LEGENDA`
valida que a legenda não ultrapassa a duração da mídia e cria um MP4 com faixa
`mov_text`. Essa preparação não executa tradução ou renderização de Libras.

## Artefatos futuros

Quando o pipeline completo existir, `keep_intermediate` preservará:

```text
output/
├── source.json
├── transcription.srt
├── transcription.json
├── normalized.json
├── libras-ir.json
├── avatar.mp4
└── final.mp4
```

Cada unidade carregará tempo de origem. As timelines de origem, linguística,
sinais e render serão distintas, permitindo pausas, mudança de velocidade e
reagrupamento sem falsificar a equivalência de duração entre fala e Libras.

## Falhas e observabilidade

- arquivo ou executável ausente: falha explícita antes do processamento;
- FFprobe inválido: falha de inspeção com diagnóstico;
- sem legenda: código 2 e `No subtitle stream found.`;
- saída já existente: proteção contra sobrescrita, exceto com `--overwrite`;
- legenda bitmap: FFmpeg reportará que não pode convertê-la para SubRip;
- logs usam o prefixo `[SINAL][camada]` e são separados da saída de dados.
