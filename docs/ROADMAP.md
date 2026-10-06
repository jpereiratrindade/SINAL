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

## Fase 2 — Speech-to-Text (implementada)

- contrato `Transcriber` e resultado temporizado;
- adapter local para Whisper (`faster-whisper` / `openai-whisper`);
- mock transcriber para execução sem GPU ou dependências extras;
- escrita e exportação de SRT;
- comando CLI `sinal transcribe`.

## Fase 3 — LIBRAS-IR (núcleo implementado)

- JSON Schema 0.1.0 e validador estrito;
- segmentos, semântica, sinais e marcadores não manuais;
- proveniência, confiança e revisão;
- `MockLibrasTranslator` e `VlibrasHttpTranslator`;
- comandos CLI `sinal build-ir` e `sinal validate-ir`.

## Fase 4 — Pesquisa e adapter VLibras (em andamento)

- contrato textual oficial auditado e adapter HTTP configurável implementado;
- verificação de implantação local completa e licença dos componentes;
- fallback e isolamento via LIBRAS-IR mantidos.

## Fases 5 e 6 — Render e composição (parcial)

- contrato `LibrasRenderer`, preview sintético e preview procedural;
- auditoria fail-closed de revisão, proveniência e cobertura de movimentos;
- compositor FFmpeg com suporte aos 4 cantos (`sinal compose`);
- preservação de canais de áudio e legendas.

Pendente para produção:

- integrar um corpus/catálogo de movimentos revisado por especialistas em Libras;
- obter e integrar uma malha SINA rigada que corresponda ao conceito visual;
- validar o resultado com pessoas surdas e especialistas;
- somente então habilitar `sinal process --render` como fluxo publicável.

## Depois do MVP

Somente após o pipeline offline estar validado: avatar próprio, movimento
esquelético detalhado, revisão humana assistida e, por último, estudo de tempo
real. Treinamento próprio, mobile e arquitetura distribuída não pertencem ao
primeiro ciclo.
