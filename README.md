# SINAL

**Sistema Inteligente de Acessibilidade Narrativa em Libras**

O SINAL é uma arquitetura local-first para transformar conteúdo audiovisual em
uma representação linguística e corporal de Libras. O projeto separa extração
de conteúdo, transcrição, tradução, LIBRAS-IR, movimento, renderização e
composição. Ele não trata Libras como substituição palavra por palavra do
português.

> Estado atual: pipeline de mídia (Fases 0 e 1) e primeiro marco do LIBRAS-IR
> (Fase 3). Ainda não há transcrição nem geração do vídeo do avatar; a tradução
> automática requer uma instância VLibras configurada e revisão humana. Um vídeo
> de avatar já sincronizado pode ser composto sobre a mídia.

## O que já funciona

- inspeção de vídeo, áudio e legendas com FFprobe;
- seleção do stream padrão de áudio ou legenda;
- extração de legendas textuais incorporadas para SRT;
- validação de um SRT externo e incorporação como faixa selecionável em MP4;
- parser SRT com timestamps e texto multilinha;
- geração e validação do LIBRAS-IR 0.1.0;
- mock honesto, que registra tradução pendente sem inventar sinais;
- adapter opcional para o endpoint de tradução de uma instância VLibras API;
- composição FFmpeg de um avatar já renderizado e sincronizado;
- extração de áudio PCM mono/16 kHz disponível como API para a futura Fase 2;
- saída humana ou JSON no comando de inspeção;
- erros explícitos quando FFmpeg, arquivo, áudio ou legenda não estão disponíveis.

## Requisitos

- Linux;
- Python 3.12 ou posterior;
- FFmpeg e FFprobe acessíveis no `PATH`.

No Fedora:

```bash
sudo dnf install ffmpeg
```

No Debian/Ubuntu:

```bash
sudo apt install ffmpeg
```

## Instalação para desenvolvimento

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Sem instalar, também é possível executar a partir da raiz do repositório:

```bash
python -m sinal --version
```

## Uso

Inspecionar os streams:

```bash
sinal inspect video.mp4
sinal inspect video.mp4 --json
sinal --verbose inspect video.mp4
```

Extrair a primeira legenda padrão (ou a primeira disponível):

```bash
sinal extract-subtitles video.mp4
```

Isso produz `video.srt`. Para escolher um stream pelo índice mostrado no
`inspect`, definir outro destino ou substituir um arquivo existente:

```bash
sinal extract-subtitles video.mkv --stream 3 --output legenda.srt --overwrite
```

Se não houver legenda, o CLI retorna código 2 e informa:

```text
No subtitle stream found.
```

Preparar um vídeo e um SRT fornecidos separadamente:

```bash
sinal process video.mp4 --srt video.srt --output video-sinal.mp4
```

O comando valida a linha do tempo e incorpora o SRT como uma faixa `mov_text`
sem recodificar o vídeo ou o áudio. Ele prepara a fonte para as fases seguintes;
a versão atual ainda não traduz nem renderiza Libras.

Gerar o intermediário de forma segura, registrando as lacunas sem fingir uma
tradução:

```bash
sinal build-ir video.srt --engine mock --output video.libras-ir.json
sinal validate-ir video.libras-ir.json
```

Para uma instância VLibras API instalada e controlada por você:

```bash
sinal build-ir video.srt --engine vlibras \
  --endpoint http://127.0.0.1:3000 \
  --allow-network \
  --output video.libras-ir.json
```

`--allow-network` é obrigatório porque o texto das legendas será enviado ao
endpoint. A glosa retornada é automática, recebe temporização estimada e exige
revisão humana; este comando ainda não produz o vídeo do avatar.

Quando um renderer produzir um `avatar.mp4` com a mesma timeline da origem, o
SINAL valida as durações e cria o vídeo final preservando áudio e legendas:

```bash
sinal compose video-sinal.mp4 \
  --avatar avatar.mp4 \
  --position bottom-right \
  --output video-final.mp4
```

O avatar pode ocupar de 0 a 100% da largura com `--scale` (padrão `0.28`). O
compositor não aceita silenciosamente timelines diferentes.

O Whisper não é executado nesta fase.

## Testes

Os testes usam `unittest` da biblioteca padrão e também são descobertos pelo
Pytest:

```bash
python -m unittest discover -s tests -v
# ou, após instalar o extra dev:
pytest
```

## Arquitetura e princípios

```text
fonte audiovisual
       │
       ▼
texto pt-BR ──► análise/tradução ──► LIBRAS-IR
                                      │
                         ┌────────────┼────────────┐
                         ▼            ▼            ▼
                       sinais       corpo         face
                         └────────────┼────────────┘
                                      ▼
                             renderer substituível
                                      ▼
                              composição de vídeo
```

O LIBRAS-IR é o contrato obrigatório entre a camada linguística e os
renderizadores. VLibras será um backend por adaptador, nunca uma dependência
espalhada pelo sistema. Veja [Arquitetura](docs/ARCHITECTURE.md),
[LIBRAS-IR](docs/LIBRAS_IR.md), [Pipeline](docs/PIPELINE.md) e
[Roadmap](docs/ROADMAP.md).

## Limitações atuais

- legendas bitmap (PGS, VobSub etc.) não podem ser convertidas para texto sem OCR;
- o parser SRT não tenta corrigir arquivos estruturalmente inválidos;
- arquivos com múltiplas legendas exigem `--stream` quando a seleção padrão não
  for a desejada;
- a configuração TOML é um contrato inicial e ainda não é carregada pelo CLI;
- o adapter VLibras traduz texto em glosa, mas a geração/renderização pública de
  vídeo do avatar ainda não está integrada;
- tradução automática não garante equivalência com interpretação humana.

## Ética e revisão

Conteúdo automático deverá ser identificado, registrar confiança e proveniência
e permanecer revisável por pessoas. O projeto não inventará sinais ausentes e
deverá ser validado com participação de pessoas surdas e especialistas em
Libras.

## Licença

A licença aberta ainda será escolhida após análise das dependências e da
integração com VLibras. Até essa decisão, consulte o arquivo `LICENSE`: não há
permissão de uso ou redistribuição implícita.
