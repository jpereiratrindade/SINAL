# Arquitetura do SINAL

## Objetivo e limites atuais

O SINAL transforma fontes em português brasileiro em uma representação visual
em Libras, mantendo independentes quatro conceitos: conteúdo, tradução,
movimento e avatar. A primeira entrega cobre apenas constituição e mídia.

```text
Input → Media → Transcription → Language → LIBRAS-IR → Render → Compose
          ▲                         │           ▲
          └──── Fases 0 e 1 ────────┘           └─ backend substituível
```

Não há microserviços no MVP. O processo é offline, local e organizado como um
pacote Python com portas pequenas para ferramentas externas.

## Componentes

| Camada | Responsabilidade | Estado |
|---|---|---|
| `cli` | comandos e apresentação de erros/resultados | Fase 1 |
| `media` | FFprobe, FFmpeg, streams, SRT e áudio | Fase 1 |
| `transcription` | áudio → segmentos pt-BR com tempo | Fase 2 |
| `language` | normalização, segmentação e tradução | Fase 3+ |
| `libras` | modelo, validação, léxico e LIBRAS-IR | Fase 3 |
| `render` | interface e adapters de avatar | Fase 4+ |
| `compose` | overlay/side-by-side e sincronização | Fase 6 |
| `pipeline` | prioridade de fontes e orquestração | Fase 2+ |
| `config` | configuração central imutável | base inicial |

`media/ffmpeg.py` é a única fronteira de subprocessos da Fase 1. Ela não usa
shell, captura diagnóstico e normaliza falhas. As outras partes recebem modelos
tipados e podem substituir essa fronteira em testes.

## Dependências

### Obrigatórias na Fase 1

- Python 3.12+: CLI, modelos, parser SRT e orquestração;
- FFprobe: metadados e enumeração de streams;
- FFmpeg: extrações e conversão de codecs de legenda textual.

Não há dependência Python de runtime. `pytest` é opcional para desenvolvimento;
os testes também executam com `unittest`.

### Dependências candidatas, ainda não adicionadas

- `faster-whisper`, apenas na Fase 2 e como backend local de `Transcriber`;
- VLibras, após validar API local, formatos, distribuição e licença;
- JSON Schema para validação do LIBRAS-IR, quando o esquema 0.1.0 for codificado.

## Regras entre camadas

1. Mídia não conhece Whisper, Libras ou renderização.
2. Tradução recebe segmentos textuais temporizados, não arquivos de vídeo.
3. Renderização recebe LIBRAS-IR validado, não texto português cru.
4. O compositor recebe mídia renderizada e timelines; não traduz.
5. Serviços externos nunca são habilitados implicitamente.
6. Todo artefato automático registra origem, versão e estado de revisão.

## Riscos técnicos

| Risco | Consequência | Mitigação proposta |
|---|---|---|
| VLibras não oferecer API local estável | adapter frágil | prova de conceito isolada e contrato próprio |
| legenda bitmap | não há texto extraível | detectar codec, avisar e futuramente oferecer OCR explícito |
| timestamps inconsistentes | dessincronização | preservar timeline de origem e validar intervalos |
| ASR em pt-BR variável | erros linguísticos em cascata | priorizar legenda e preservar confiança/revisão |
| diferença de duração entre fala e Libras | avatar fora do segmento | timeline de sinais independente e políticas de ajuste |
| tradução automática inadequada | conteúdo incorreto ou ofensivo | não prometer equivalência, revisão humana e proveniência |
| variação regional da Libras | escolha lexical inadequada | metadados de variante e léxico extensível |
| dependências pesadas/GPU | instalação difícil | backends opcionais e mocks no pipeline |
| licença incompatível | impede distribuição conjunta | decisão de licença somente após auditoria |

## Pontos de integração com VLibras

A investigação da Fase 4 deverá responder:

- existe API/CLI local suportada e qual contrato recebe texto ou glosas?;
- tradução e animação são separáveis?;
- como expressões não manuais, tempo e sinais ausentes são reportados?;
- avatar pode ser renderizado sem rede e com fundo apropriado à composição?;
- dicionário, modelos e binários podem ser redistribuídos sob quais licenças?;
- é possível associar entradas/saídas à proveniência e versão do backend?;

O adapter previsto converte `LIBRAS-IR ↔ formato VLibras`. Recursos não
representáveis geram aviso ou erro; não são descartados silenciosamente. O
pipeline dependerá da interface `LibrasRenderer`, nunca de tipos do VLibras.

## Decisões registradas

- [ADR-0001: LIBRAS-IR como fronteira](ADR/0001-libras-ir-boundary.md)
- [ADR-0002: FFmpeg e FFprobe por subprocesso](ADR/0002-ffmpeg-subprocess.md)
- [ADR-0003: processamento local-first](ADR/0003-local-first.md)
- [ADR-0004: VLibras isolado por adapter](ADR/0004-vlibras-adapter.md)
- [ADR-0005: licença temporariamente não definida](ADR/0005-license-pending.md)

