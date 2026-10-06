# Roadmap

## Fase 0 — Constituição (concluída neste marco)

- estrutura do pacote e CLI;
- documentação de arquitetura, pipeline, LIBRAS-IR e decisões;
- configuração inicial e testes;
- análise de dependências, riscos e integração com VLibras.

## Fase 1 — Media Pipeline (concluída neste marco)

- inspeção FFprobe tipada;
- detecção de vídeo, áudio e legendas;
- parser de SRT e timestamps;
- extração de legenda incorporada;
- preparação da extração PCM para ASR;
- comandos `inspect` e `extract-subtitles`.

Critério de saída: testes unitários e validação com mídia sintética contendo
vídeo, áudio e legenda textual.

## Fase 2 — Speech-to-Text

- contrato `Transcriber` e resultado temporizado;
- adapter local para `faster-whisper`;
- escolha de modelo/configuração sem download implícito durante o pipeline;
- SRT e JSON intermediários;
- mocks e testes sem GPU.

## Fase 3 — LIBRAS-IR (núcleo implementado)

- JSON Schema 0.1.0 e validador;
- segmentos, semântica, sinais e marcadores não manuais;
- proveniência, confiança e revisão;
- `MockLibrasTranslator` para desenvolver o pipeline sem alegar tradução real.

Pendente nesta fase: editor/fluxo de revisão humana e enriquecimento semântico
e não manual além dos campos reservados no contrato.

## Fase 4 — Pesquisa e adapter VLibras (em andamento)

- contrato textual oficial auditado e adapter HTTP configurável implementado;
- verificar implantação local completa, licença dos componentes e cobertura;
- protótipo isolado de renderização quando o Video Core estiver disponível;
- mapa explícito entre recursos do LIBRAS-IR e do backend;
- decisão documentada de empacotamento e fallback.

## Fases 5 e 6 — Render e composição (compositor overlay implementado)

- contrato `LibrasRenderer`, mock e backend escolhido;
- `avatar.mp4` com timeline registrada;
- overlay nos quatro cantos por FFmpeg, com validação de timeline (implementado);
- side-by-side por FFmpeg;
- `final.mp4` sem descartar intermediários.

## Depois do MVP

Somente após o pipeline offline estar validado: avatar próprio, movimento
esquelético detalhado, revisão humana assistida e, por último, estudo de tempo
real. Treinamento próprio, mobile e arquitetura distribuída não pertencem ao
primeiro ciclo.
